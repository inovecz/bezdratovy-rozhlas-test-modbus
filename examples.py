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
from typing import Iterable
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from modbus_audio import ModbusAudioClient, ModbusAudioError, SerialSettings, constants
from modbus_audio.constants import TX_CONTROL


SERIAL_SETTINGS = SerialSettings(
    port="/dev/tty.usbserial-AV0K3CPZ",  # change to the serial port used on your system
    baudrate=57600,
    parity="N",
    stopbits=1,
    bytesize=8,
    timeout=1.0,
)
UNIT_ID = 1

DEMO_ROUTE = [1, 116, 225]
DEMO_ZONES = [22]
DEMO_FREQUENCY = 7100
FREQUENCY_REGISTER = 0x4024
PRETTY_PRINT_INSPECT = True

SCAN_METHODS = ["rtu"]
SCAN_BAUD_RATES = [9600, 19200, 38400, 57600, 115200]
SCAN_PARITIES = ["E", "N", "O"]
SCAN_STOP_BITS = [1, 2]
SCAN_UNIT_IDS = [1]


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
        ],
        help="Which built-in scenario to execute",
    )
    return parser.parse_args()


def build_client() -> ModbusAudioClient:
    return ModbusAudioClient(settings=SERIAL_SETTINGS, unit_id=UNIT_ID)


def run_inspect(client: ModbusAudioClient) -> int:
    info = client.get_device_info()
    indent = 2 if PRETTY_PRINT_INSPECT else None
    print(json.dumps(info, indent=indent))
    return 0


def run_set_frequency(client: ModbusAudioClient) -> int:
    client.write_register(FREQUENCY_REGISTER, DEMO_FREQUENCY)
    print(f"Register 0x{FREQUENCY_REGISTER:04X} set to {DEMO_FREQUENCY}")
    return 0


def run_play_demo(client: ModbusAudioClient, addresses: Iterable[int], zones: Iterable[int]) -> int:
    client.start_audio_stream(addresses, zones=zones)
    print(
        "Started audio stream with hop chain "
        f"{list(addresses)} and zones {list(zones)} (TxControl=2)."
    )
    return 0


def run_stop_demo(client: ModbusAudioClient) -> int:
    client.stop_audio_stream()
    print("Stopped audio stream (TxControl=1).")
    return 0


def run_read_tx_control(client: ModbusAudioClient) -> int:
    try:
        value = client.read_register(TX_CONTROL)
    except ModbusAudioError as exc:
        print(
            "Unable to read TxControl (0x5035). Many receiver firmware builds expose"
            " this register as write-only; try 0x4035 for RxControl or confirm the"
            " target device is the transmitter."
        )
        print(f"Underlying error: {exc}")
        return 1

    print(f"Register 0x{TX_CONTROL:04X} -> {value}")
    return 0


def run_probe(client: ModbusAudioClient) -> int:
    try:
        client.read_register(0x0000)
    except ModbusAudioError as exc:
        print(f"Probe failed: {exc}")
        return 1

    print("Probe succeeded: device responded")
    return 0


def run_serial_number(client: ModbusAudioClient) -> int:
    block = constants.DEVICE_INFO_REGISTERS["serial_number"]
    try:
        words = client.read_registers(block.start, block.quantity)
    except ModbusAudioError as exc:
        print(f"Unable to read serial number: {exc}")
        return 1

    serial = "".join(f"{word:04X}" for word in words)
    if not serial.strip("0"):
        print("Serial number register returned only zeroes")
        return 1

    print(f"Device serial number: {serial}")
    return 0


def run_auto_probe() -> int:
    """Try common serial configurations until one responds."""

    attempts = 0
    for method in SCAN_METHODS:
        for baudrate in SCAN_BAUD_RATES:
            for parity in SCAN_PARITIES:
                for stopbits in SCAN_STOP_BITS:
                    for unit_id in SCAN_UNIT_IDS:
                        attempts += 1
                        settings = SerialSettings(
                            port=SERIAL_SETTINGS.port,
                            method=method,
                            baudrate=baudrate,
                            parity=parity,
                            stopbits=stopbits,
                            bytesize=SERIAL_SETTINGS.bytesize,
                            timeout=SERIAL_SETTINGS.timeout,
                        )
                        try:
                            with ModbusAudioClient(settings=settings, unit_id=unit_id) as client:
                                client.read_register(0x0000)
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


def run_frequency(client: ModbusAudioClient) -> int:
    block = constants.DEVICE_INFO_REGISTERS["frequency"]
    try:
        value = client.read_register(block.start)
    except ModbusAudioError as exc:
        print(f"Unable to read RF frequency (register 0x{block.start:04X}): {exc}")
        return 1

    print(f"RF frequency register (0x{block.start:04X}) -> {value}")
    return 0


def run_dump_registers(client: ModbusAudioClient) -> int:
    rows: list[tuple[str, str, str, str]] = []

    for desc in constants.DOCUMENTED_REGISTERS:
        address = f"0x{desc.block.start:04X}"
        quantity = str(desc.block.quantity)

        if not desc.readable:
            rows.append((desc.name, address, quantity, "write-only"))
            continue

        try:
            values = client.read_registers(desc.block.start, desc.block.quantity)
        except ModbusAudioError as exc:
            rows.append((desc.name, address, quantity, f"error: {exc}"))
            continue

        if desc.block.quantity == 1:
            rendered = str(values[0])
        else:
            rendered = "[" + ", ".join(str(v) for v in values) + "]"

        rows.append((desc.name, address, quantity, rendered))

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


def main() -> None:
    args = parse_args()

    if args.action == "auto-probe":
        code = run_auto_probe()
        raise SystemExit(code)

    try:
        with build_client() as client:
            if args.action == "inspect":
                code = run_inspect(client)
            elif args.action == "set-frequency":
                code = run_set_frequency(client)
            elif args.action == "play-demo":
                code = run_play_demo(client, DEMO_ROUTE, DEMO_ZONES)
            elif args.action == "stop-demo":
                code = run_stop_demo(client)
            elif args.action == "read-tx-control":
                code = run_read_tx_control(client)
            elif args.action == "probe":
                code = run_probe(client)
            elif args.action == "serial-number":
                code = run_serial_number(client)
            elif args.action == "frequency":
                code = run_frequency(client)
            elif args.action == "dump-registers":
                code = run_dump_registers(client)
            else:  # pragma: no cover - should not trigger due to argparse choices
                raise ModbusAudioError(f"Unsupported action: {args.action}")
    except ModbusAudioError as exc:
        print(f"Error: {exc}")
        code = 1

    raise SystemExit(code)


if __name__ == "__main__":  # pragma: no cover
    main()
