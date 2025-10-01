"""Command line interface for the Modbus audio helper library."""

from __future__ import annotations

import argparse
import json
from typing import Iterable

from .client import ModbusAudioClient, ModbusAudioError, SerialSettings


def int_from_string(value: str) -> int:
    """Parse integers in decimal or ``0x`` prefixed hexadecimal form."""

    return int(value, 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Utilities for VP_PRIJIMAC Modbus devices")
    parser.add_argument("--port", required=True, help="Serial port path, e.g. /dev/ttyUSB0 or COM3")
    parser.add_argument("--method", default="rtu", help="Modbus method (default: rtu)")
    parser.add_argument("--baudrate", type=int, default=9600, help="Serial baudrate (default: 9600)")
    parser.add_argument("--parity", default="E", help="Serial parity (default: E)")
    parser.add_argument("--stopbits", type=int, default=1, help="Serial stop bits (default: 1)")
    parser.add_argument("--bytesize", type=int, default=8, help="Serial byte size (default: 8)")
    parser.add_argument("--timeout", type=float, default=1.0, help="Read timeout in seconds (default: 1.0)")
    parser.add_argument("--unit-id", type=int, default=1, help="Modbus unit/slave id (default: 1)")

    sub = parser.add_subparsers(dest="command", required=True)

    info_cmd = sub.add_parser("info", help="Read a snapshot of useful registers")
    info_cmd.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")

    read_cmd = sub.add_parser("read", help="Read holding registers")
    read_cmd.add_argument("address", type=int_from_string, help="Starting register address (decimal or 0x prefixed)")
    read_cmd.add_argument("--count", type=int, default=1, help="Number of registers to read")

    write_cmd = sub.add_parser("write", help="Write a single holding register")
    write_cmd.add_argument("address", type=int_from_string, help="Register address (decimal or 0x prefixed)")
    write_cmd.add_argument("value", type=int_from_string, help="Value to write")

    start_cmd = sub.add_parser("start-audio", help="Configure route/zones and start audio streaming")
    start_cmd.add_argument(
        "--addresses",
        type=int_from_string,
        nargs="+",
        required=True,
        help="Sequence of hop addresses to populate into Addr0..Addr4",
    )
    start_cmd.add_argument(
        "--zones",
        type=int_from_string,
        nargs="*",
        help="Optional list of destination zones (fills 0x4030..0x4034)",
    )

    sub.add_parser("stop-audio", help="Stop audio streaming by writing 1 to TxControl")

    return parser


def run_command(args: argparse.Namespace) -> int:
    settings = SerialSettings(
        port=args.port,
        method=args.method,
        baudrate=args.baudrate,
        parity=args.parity,
        stopbits=args.stopbits,
        bytesize=args.bytesize,
        timeout=args.timeout,
    )

    try:
        with ModbusAudioClient(settings=settings, unit_id=args.unit_id) as client:
            if args.command == "info":
                data = client.get_device_info()
                indent = 2 if args.pretty else None
                print(json.dumps(data, indent=indent))
                return 0

            if args.command == "read":
                values = client.read_registers(args.address, args.count)
                print(json.dumps(values))
                return 0

            if args.command == "write":
                client.write_register(args.address, args.value)
                return 0

            if args.command == "start-audio":
                zones: Iterable[int] | None = args.zones if args.zones else None
                client.start_audio_stream(args.addresses, zones=zones)
                return 0

            if args.command == "stop-audio":
                client.stop_audio_stream()
                return 0

    except ModbusAudioError as exc:
        print(f"Error: {exc}")
        return 1

    return 0


def main() -> None:
    parser = build_parser()
    exit_code = run_command(parser.parse_args())
    raise SystemExit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    main()
