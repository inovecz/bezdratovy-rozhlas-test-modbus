"""Simulate JSVV hardware frames and feed them into the client library."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jsvv import JSVVError  # noqa: E402
from jsvv.simulator import JSVVSimulator, SCENARIOS, SimulationEvent  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JSVV hardware simulator")
    parser.add_argument("--network-id", type=int, default=1)
    parser.add_argument("--vyc-id", type=int, default=1)
    parser.add_argument("--kpps-address", default="0x0001")
    parser.add_argument("--operator-id", type=int)

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

    return parser.parse_args()


def build_simulator(args: argparse.Namespace) -> JSVVSimulator:
    return JSVVSimulator(
        network_id=args.network_id,
        vyc_id=args.vyc_id,
        kpps_address=args.kpps_address,
        operator_id=args.operator_id,
    )


def run_list() -> int:
    for name in sorted(SCENARIOS.keys()):
        print(name)
    return 0


def run_scenario(args: argparse.Namespace) -> int:
    simulator = build_simulator(args)
    events = SCENARIOS[args.name]
    indent = 2 if args.pretty else None
    for result in simulator.run(events):
        print(result["raw"])
        print(json.dumps(result["json"], indent=indent))
        if result["note"]:
            print(f"# {result['note']}")
        if result["duplicate"]:
            print("# duplicate within dedup window")
        print()
    return 0


def run_emit(args: argparse.Namespace) -> int:
    simulator = build_simulator(args)
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
    if duplicate:
        print("# duplicate within dedup window")
    return 0


def main() -> None:
    args = parse_args()
    if args.command == "list":
        raise SystemExit(run_list())
    if args.command == "scenario":
        raise SystemExit(run_scenario(args))
    if args.command == "emit":
        raise SystemExit(run_emit(args))
    raise SystemExit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
