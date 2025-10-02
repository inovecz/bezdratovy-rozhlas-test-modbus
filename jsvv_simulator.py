"""Simulate JSVV hardware frames and feed them into the client library.

When a VERBAL command is encountered the simulator prints the resolved audio
asset path so you can verify playback routing without touching the filesystem
manually.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jsvv import JSVVClient, JSVVError  # noqa: E402
from jsvv.simulator import JSVVSimulator, SCENARIOS, SimulationEvent  # noqa: E402

from modbus_audio import ModbusAudioClient, ModbusAudioError, SerialSettings  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JSVV hardware simulator")
    parser.add_argument("--network-id", type=int, default=1)
    parser.add_argument("--vyc-id", type=int, default=1)
    parser.add_argument("--kpps-address", default="0x0001")
    parser.add_argument("--operator-id", type=int)
    parser.add_argument("--modbus-port", help="Serial port used to drive real Modbus streaming during simulation")
    parser.add_argument("--modbus-baudrate", type=int, default=57600)
    parser.add_argument("--modbus-parity", default="N")
    parser.add_argument("--modbus-stopbits", type=int, default=1)
    parser.add_argument("--modbus-bytesize", type=int, default=8)
    parser.add_argument("--modbus-timeout", type=float, default=1.0)
    parser.add_argument("--modbus-method", default="rtu")
    parser.add_argument("--modbus-unit-id", type=int, default=1)
    parser.add_argument("--modbus-zones", type=int, nargs="*", help="Optional destination zones to configure before playback")
    parser.add_argument(
        "--modbus-hold-seconds",
        type=float,
        default=5.0,
        help="Seconds to keep TxControl active when no player command is provided",
    )
    parser.add_argument(
        "--modbus-player",
        nargs="+",
        help="Optional external player command (e.g. --modbus-player afplay)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List built-in scenarios")

    scenario_cmd = sub.add_parser("scenario", help="Run a named scenario")
    scenario_cmd.add_argument("name", choices=sorted(SCENARIOS.keys()))
    scenario_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON payloads")

    emit_cmd = sub.add_parser("emit", help="Emit a single frame with parameters")
    emit_cmd.add_argument("mid", help="Message identifier, e.g. SIREN")
    emit_cmd.add_argument("params", nargs="*", help="Optional parameters")
    emit_cmd.add_argument("--priority", help="Override payload priority")
    emit_cmd.add_argument("--timestamp", type=int, help="Override payload timestamp")
    emit_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON payload")

    frame_cmd = sub.add_parser("frame", help="Decode a raw JSVV frame string")
    frame_cmd.add_argument("frame", nargs="+", help="Raw frame tokens (quote the whole string if it contains spaces)")
    frame_cmd.add_argument("--skip-crc", action="store_true", help="Skip CRC validation during parsing")
    frame_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON payload")

    return parser.parse_args()


def build_simulator(args: argparse.Namespace) -> JSVVSimulator:
    return JSVVSimulator(
        network_id=args.network_id,
        vyc_id=args.vyc_id,
        kpps_address=args.kpps_address,
        operator_id=args.operator_id,
    )


class ModbusPlaybackBridge:
    """Forward VERBAL/STOP commands to the Modbus audio transmitter."""

    def __init__(
        self,
        settings: SerialSettings,
        unit_id: int,
        zones: list[int] | None,
        hold_seconds: float,
        player_command: list[str] | None,
    ) -> None:
        self._client = ModbusAudioClient(settings=settings, unit_id=unit_id)
        self._zones = zones
        self._hold_seconds = hold_seconds
        self._player_command = player_command
        self._connected = False

    def close(self) -> None:
        if self._connected:
            self._client.close()
            self._connected = False

    def _ensure_connected(self) -> None:
        if not self._connected:
            self._client.connect()
            self._connected = True

    def handle(self, result: dict[str, object]) -> None:
        payload = result.get("json")
        if not isinstance(payload, dict):
            return
        command = payload.get("command")
        if command == "VERBAL_INFO":
            asset = result.get("asset") if isinstance(result.get("asset"), str) else None
            try:
                self._handle_verbal(asset)
            except ModbusAudioError as exc:
                print(f"# Modbus error during VERBAL_INFO handling: {exc}")
        elif command == "STOP":
            try:
                self._ensure_connected()
                self._client.stop_stream()
            except ModbusAudioError as exc:
                print(f"# Modbus error while stopping stream: {exc}")

    def _handle_verbal(self, asset_path: str | None) -> None:
        self._ensure_connected()
        zones = self._zones if self._zones else None
        self._client.start_stream(zones=zones)
        try:
            if self._player_command and asset_path:
                try:
                    subprocess.run([*self._player_command, asset_path], check=False)
                except OSError as exc:
                    print(f"# unable to run player '{self._player_command[0]}': {exc}")
                    time.sleep(max(0.0, self._hold_seconds))
            else:
                time.sleep(max(0.0, self._hold_seconds))
        finally:
            self._client.stop_stream()


def build_modbus_bridge(args: argparse.Namespace) -> ModbusPlaybackBridge | None:
    if not args.modbus_port:
        return None
    settings = SerialSettings(
        port=args.modbus_port,
        method=args.modbus_method,
        baudrate=args.modbus_baudrate,
        parity=args.modbus_parity,
        stopbits=args.modbus_stopbits,
        bytesize=args.modbus_bytesize,
        timeout=args.modbus_timeout,
    )
    zones = list(args.modbus_zones) if args.modbus_zones else None
    return ModbusPlaybackBridge(
        settings=settings,
        unit_id=args.modbus_unit_id,
        zones=zones,
        hold_seconds=args.modbus_hold_seconds,
        player_command=args.modbus_player,
    )


def run_list() -> int:
    for name in sorted(SCENARIOS.keys()):
        print(name)
    return 0


def run_scenario(args: argparse.Namespace) -> int:
    simulator = build_simulator(args)
    events = SCENARIOS[args.name]
    indent = 2 if args.pretty else None
    bridge = build_modbus_bridge(args)
    try:
        for result in simulator.run(events):
            print(result["raw"])
            print(json.dumps(result["json"], indent=indent))
            if result["note"]:
                print(f"# {result['note']}")
            if result.get("asset"):
                print(f"# verbal asset path: {result['asset']}")
            elif result.get("asset_error"):
                print(f"# verbal asset error: {result['asset_error']}")
            if result["duplicate"]:
                print("# duplicate within dedup window")
            if bridge is not None:
                bridge.handle(result)
            print()
    finally:
        if bridge is not None:
            bridge.close()
    return 0


def run_emit(args: argparse.Namespace) -> int:
    simulator = build_simulator(args)
    bridge = build_modbus_bridge(args)
    try:
        raw, payload, duplicate = simulator.emit(
            args.mid,
            args.params,
            priority=args.priority,
            timestamp=args.timestamp,
        )
    except JSVVError as exc:
        print(f"Error: {exc}")
        return 1
    indent = 2 if args.pretty else None
    print(raw)
    print(json.dumps(payload, indent=indent))
    if payload.get("command") == "VERBAL_INFO":
        slot = payload.get("params", {}).get("slot")
        voice = payload.get("params", {}).get("voice", "male")
        if isinstance(slot, int):
            try:
                asset_path = simulator.client.get_verbal_asset(slot, voice=voice)
            except JSVVError as exc:
                print(f"# verbal asset error: {exc}")
            else:
                print(f"# verbal asset path: {asset_path}")
                if bridge is not None:
                    bridge.handle(
                        {
                            "json": payload,
                            "asset": str(asset_path),
                            "duplicate": duplicate,
                            "note": None,
                        }
                    )
    if duplicate:
        print("# duplicate within dedup window")
    if bridge is not None:
        bridge.close()
    return 0


def run_frame(args: argparse.Namespace) -> int:
    raw_input = " ".join(args.frame)
    try:
        frame = JSVVClient.parse_frame(raw_input, validate_crc=not args.skip_crc)
    except JSVVError as exc:
        print(f"Error parsing frame: {exc}")
        return 1

    simulator = build_simulator(args)
    bridge = build_modbus_bridge(args)

    try:
        raw, payload, duplicate = simulator.emit(frame.mid, frame.params)
    except JSVVError as exc:
        print(f"Simulation error: {exc}")
        if bridge is not None:
            bridge.close()
        return 1

    indent = 2 if args.pretty else None
    print(raw)
    print(json.dumps(payload, indent=indent))
    asset_path = None
    if payload.get("command") == "VERBAL_INFO":
        params = payload.get("params", {})
        slot = params.get("slot") if isinstance(params, dict) else None
        voice = params.get("voice", "male") if isinstance(params, dict) else "male"
        if isinstance(slot, int):
            try:
                path = simulator.client.get_verbal_asset(slot, voice=voice)
            except JSVVError as exc:
                print(f"# verbal asset error: {exc}")
            else:
                asset_path = str(path)
                print(f"# verbal asset path: {asset_path}")
    if duplicate:
        print("# duplicate within dedup window")
    if bridge is not None:
        bridge.handle({"json": payload, "asset": asset_path, "duplicate": duplicate, "note": None})
        bridge.close()
    return 0


def main() -> None:
    args = parse_args()
    if args.command == "list":
        raise SystemExit(run_list())
    if args.command == "scenario":
        raise SystemExit(run_scenario(args))
    if args.command == "emit":
        raise SystemExit(run_emit(args))
    if args.command == "frame":
        raise SystemExit(run_frame(args))
    raise SystemExit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
