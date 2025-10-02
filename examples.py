"""Demonstration script for the Modbus audio helper library.

Usage examples (adjust the constants below to match your setup):

    python3 examples.py inspect
    python3 examples.py set-frequency
    python3 examples.py play-demo
    python3 examples.py stop-demo

The script reuses the ``modbus_audio`` library and exposes a couple of
high-level scenarios that mirror the typical workflows when interacting with
VP_PRIJIMAC transmitters/receivers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from modbus_audio import ModbusAudioClient, ModbusAudioError, SerialSettings, constants
from modbus_audio.constants import TX_CONTROL


DEMO_ZONES = list(constants.DEFAULT_DESTINATION_ZONES)
DEMO_FREQUENCY = constants.DEFAULT_FREQUENCY
PRETTY_PRINT_INSPECT = True

SCAN_METHODS = [SerialSettings().method]
SCAN_BAUD_RATES = [constants.DEFAULT_BAUDRATE, 9600, 19200, 38400, 115200]
SCAN_PARITIES = [constants.DEFAULT_PARITY, "E", "O"]
SCAN_STOP_BITS = [constants.DEFAULT_STOPBITS, 2]
SCAN_UNIT_IDS = [constants.DEFAULT_UNIT_ID]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Examples built on top of modbus_audio")
    parser.add_argument(
        "action",
        choices=[
            "inspect",
            "set-frequency",
            "play-demo",
            "stop-demo",
            "read-tx-control",
            "probe",
            "auto-probe",
            "serial-number",
            "frequency",
            "dump-registers",
            "start-stream",
            "stop-stream",
        ],
        help="Which built-in scenario to execute",
    )
    return parser.parse_args()


def build_client() -> ModbusAudioClient:
    return ModbusAudioClient.from_defaults()


def probe_device() -> None:
    with build_client() as client:
        client.probe()


def read_serial_number_value() -> str:
    with build_client() as client:
        return client.read_serial_number()


def read_frequency_value() -> int:
    with build_client() as client:
        return client.read_frequency()


def read_tx_control_value() -> int:
    with build_client() as client:
        return client.read_register(constants.TX_CONTROL)


def start_streaming(zones: Iterable[int] | None = None) -> None:
    with build_client() as client:
        client.start_stream(zones=zones if zones is not None else DEMO_ZONES)


def stop_streaming() -> None:
    with build_client() as client:
        client.stop_stream()


def set_demo_frequency(value: int | None = None) -> None:
    with build_client() as client:
        client.write_frequency(DEMO_FREQUENCY if value is None else value)


def write_register(address: int, value: int) -> None:
    with build_client() as client:
        client.write_register(address, value)


def read_registers(address: int, count: int = 1) -> list[int]:
    with build_client() as client:
        return client.read_registers(address, count)


def dump_documented_registers() -> list[tuple[str, str, str, str]]:
    with build_client() as client:
        return client.dump_documented_registers()


def collect_device_info() -> dict[str, object]:
    with build_client() as client:
        return dict(client.get_device_info())


def run_inspect() -> int:
    try:
        info = collect_device_info()
    except ModbusAudioError as exc:
        print(f"Unable to collect device info: {exc}")
        return 1

    indent = 2 if PRETTY_PRINT_INSPECT else None
    print(json.dumps(info, indent=indent))
    return 0


def run_set_frequency() -> int:
    try:
        set_demo_frequency()
    except ModbusAudioError as exc:
        print(f"Unable to write frequency register 0x{constants.FREQUENCY_REGISTER:04X}: {exc}")
        return 1

    print(f"Register 0x{constants.FREQUENCY_REGISTER:04X} set to {DEMO_FREQUENCY}")
    return 0


def run_play_demo() -> int:
    try:
        start_streaming()
    except ModbusAudioError as exc:
        print(f"Failed to start demo stream: {exc}")
        return 1

    print(
        "Started audio stream with default route {route} and zones {zones}."
        .format(route=list(constants.DEFAULT_ROUTE), zones=DEMO_ZONES)
    )
    return 0


def run_stop_demo() -> int:
    try:
        stop_streaming()
    except ModbusAudioError as exc:
        print(f"Failed to stop streaming: {exc}")
        return 1

    print("Stopped audio stream (TxControl 0x4035 <- 1).")
    return 0


def run_read_tx_control() -> int:
    try:
        value = read_tx_control_value()
    except ModbusAudioError as exc:
        print(
            "Unable to read TxControl (0x4035). Many firmware builds expose this"
            " register as write-only; confirm the target device is the transmitter."
        )
        print(f"Underlying error: {exc}")
        return 1

    print(f"Register 0x{TX_CONTROL:04X} -> {value}")
    return 0


def run_probe() -> int:
    try:
        probe_device()
    except ModbusAudioError as exc:
        print(f"Probe failed: {exc}")
        return 1

    print("Probe succeeded: device responded")
    return 0


def run_serial_number() -> int:
    try:
        serial = read_serial_number_value()
    except ModbusAudioError as exc:
        print(f"Unable to read serial number: {exc}")
        return 1

    if not serial.strip("0"):
        print("Serial number register returned only zeroes")
        return 1

    print(f"Device serial number: {serial}")
    return 0


def run_auto_probe() -> int:
    """Try common serial configurations until one responds."""

    attempts = 0
    base_settings = SerialSettings()
    for method in SCAN_METHODS:
        for baudrate in SCAN_BAUD_RATES:
            for parity in SCAN_PARITIES:
                for stopbits in SCAN_STOP_BITS:
                    for unit_id in SCAN_UNIT_IDS:
                        attempts += 1
                        settings = SerialSettings(
                            port=base_settings.port,
                            method=method,
                            baudrate=baudrate,
                            parity=parity,
                            stopbits=stopbits,
                            bytesize=base_settings.bytesize,
                            timeout=base_settings.timeout,
                        )
                        try:
                            with ModbusAudioClient(settings=settings, unit_id=unit_id) as client:
                                client.probe()
                        except ModbusAudioError:
                            continue
                        except OSError as exc:
                            print(f"Serial error while opening port: {exc}")
                            return 1
                        else:
                            print(
                                "Probe succeeded",
                                f"method={method}",
                                f"baud={baudrate}",
                                f"parity={parity}",
                                f"stopbits={stopbits}",
                                f"unit_id={unit_id}",
                                f"attempt={attempts}",
                            )
                            return 0

    print(f"Probe failed after {attempts} combinations. Expand SCAN_* constant lists if needed.")
    return 1


def run_frequency() -> int:
    try:
        value = read_frequency_value()
    except ModbusAudioError as exc:
        print(f"Unable to read RF frequency (register 0x{constants.FREQUENCY_REGISTER:04X}): {exc}")
        return 1

    print(f"RF frequency register (0x{constants.FREQUENCY_REGISTER:04X}) -> {value}")
    return 0


def run_dump_registers() -> int:
    try:
        rows = dump_documented_registers()
    except ModbusAudioError as exc:
        print(f"Unable to dump registers: {exc}")
        return 1

    headers = ("Name", "Address", "Qty", "Value")
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(cell))

    def format_row(items: tuple[str, str, str, str]) -> str:
        return " | ".join(cell.ljust(col_widths[idx]) for idx, cell in enumerate(items))

    separator = "-+-".join("-" * width for width in col_widths)
    print(format_row(headers))
    print(separator)
    for row in rows:
        print(format_row(row))

    return 0


def run_start_stream() -> int:
    try:
        start_streaming()
    except ModbusAudioError as exc:
        print(f"Failed to start streaming: {exc}")
        return 1

    print("Streaming started (TxControl 0x4035 <- 2). Zones {zones} updated.".format(zones=DEMO_ZONES))
    return 0


def run_stop_stream() -> int:
    try:
        stop_streaming()
    except ModbusAudioError as exc:
        print(f"Failed to stop streaming: {exc}")
        return 1

    print("Streaming stopped (TxControl 0x4035 reset to 1).")
    return 0


def main() -> None:
    args = parse_args()

    if args.action == "auto-probe":
        code = run_auto_probe()

    elif args.action == "inspect":
        code = run_inspect()
    elif args.action == "set-frequency":
        code = run_set_frequency()
    elif args.action == "play-demo":
        code = run_play_demo()
    elif args.action == "stop-demo":
        code = run_stop_demo()
    elif args.action == "read-tx-control":
        code = run_read_tx_control()
    elif args.action == "probe":
        code = run_probe()
    elif args.action == "serial-number":
        code = run_serial_number()
    elif args.action == "frequency":
        code = run_frequency()
    elif args.action == "dump-registers":
        code = run_dump_registers()
    elif args.action == "start-stream":
        code = run_start_stream()
    elif args.action == "stop-stream":
        code = run_stop_stream()
    else:  # pragma: no cover - should not trigger due to argparse choices
        raise ModbusAudioError(f"Unsupported action: {args.action}")

    raise SystemExit(code)


if __name__ == "__main__":  # pragma: no cover
    main()
