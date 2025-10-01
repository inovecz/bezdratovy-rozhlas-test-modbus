"""Demonstration helpers for the JSVV client library.

Usage examples:

    python3 jsvv_examples.py parse-frame "SIREN 1 180 CRC 1A2B"
    python3 jsvv_examples.py build-frame SIREN 1 180
    python3 jsvv_examples.py verbal-info 3 --voice female

The script focuses on offline tooling (frame parsing, CRC handling, asset lookup)
so it can be used without a live KPPS connected.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jsvv import JSVVClient, JSVVError  # noqa: E402  (defer import until path adjusted)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Examples built on top of the jsvv helper")
    sub = parser.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse-frame", help="Parse a raw ASCII frame and render JSON payload")
    parse_cmd.add_argument("frame", help="Raw frame, e.g. 'SIREN 1 180 CRC 004B'")
    parse_cmd.add_argument("--network-id", type=int, default=1, help="Network identifier")
    parse_cmd.add_argument("--vyc-id", type=int, default=1, help="VyC identifier")
    parse_cmd.add_argument("--kpps-address", default="0x0001", help="KPPS address (hex or string)")
    parse_cmd.add_argument("--operator-id", type=int, help="Optional operator id")
    parse_cmd.add_argument("--timestamp", type=int, help="Force payload timestamp")
    parse_cmd.add_argument("--skip-crc", action="store_true", help="Skip CRC validation")
    parse_cmd.add_argument("--pretty", action="store_true", help="Pretty-print resulting JSON")

    build_cmd = sub.add_parser("build-frame", help="Build a frame from MID and tokens")
    build_cmd.add_argument("mid", help="Message identifier")
    build_cmd.add_argument("params", nargs="*", help="Optional parameters")
    build_cmd.add_argument("--no-crc", action="store_true", help="Build frame without CRC")

    audio_cmd = sub.add_parser("verbal-info", help="Locate on-disk audio asset for a slot")
    audio_cmd.add_argument("slot", type=int, help="Slot number (1-20)")
    audio_cmd.add_argument("--voice", default="male", help="Voice preference (male/female)")

    return parser.parse_args()


def run_parse(args: argparse.Namespace) -> int:
    frame = JSVVClient.parse_frame(args.frame, validate_crc=not args.skip_crc)
    payload = frame.to_json(
        network_id=args.network_id,
        vyc_id=args.vyc_id,
        kpps_address=args.kpps_address,
        operator_id=args.operator_id,
        timestamp=args.timestamp,
    )

    indent = 2 if args.pretty else None
    print(json.dumps(payload, indent=indent))

    client = JSVVClient.from_defaults()
    client.validate_and_track(
        frame,
        network_id=args.network_id,
        vyc_id=args.vyc_id,
        kpps_address=args.kpps_address,
        operator_id=args.operator_id,
        timestamp=payload["timestamp"],
    )
    is_duplicate = not client.validate_and_track(
        frame,
        network_id=args.network_id,
        vyc_id=args.vyc_id,
        kpps_address=args.kpps_address,
        operator_id=args.operator_id,
        timestamp=payload["timestamp"],
    )
    if is_duplicate:
        print("Duplicate detected on repeated evaluation (within dedup window)")
    return 0


def run_build(args: argparse.Namespace) -> int:
    frame = JSVVClient.build_frame(args.mid, args.params, include_crc=not args.no_crc)
    print(frame.rstrip("\n"))
    return 0


def run_verbal(args: argparse.Namespace) -> int:
    client = JSVVClient.from_defaults()
    try:
        path = client.get_verbal_asset(args.slot, voice=args.voice)
    except JSVVError as exc:
        print(f"Unable to resolve asset: {exc}")
        return 1
    print(str(path))
    return 0


def main() -> None:
    args = parse_args()
    if args.command == "parse-frame":
        raise SystemExit(run_parse(args))
    if args.command == "build-frame":
        raise SystemExit(run_build(args))
    if args.command == "verbal-info":
        raise SystemExit(run_verbal(args))
    raise SystemExit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
