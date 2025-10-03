#!/usr/bin/env python3
"""Simple helper that toggles a relay via gpioset shell commands."""

from __future__ import annotations

import subprocess


CHIP = "gpiochip2"
PIN = 8


def _run_gpioset(level: int) -> None:
    command = ["gpioset", CHIP, f"{PIN}={level}"]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"gpioset failed with exit code {exc.returncode}") from exc


def main() -> None:
    _run_gpioset(1)
    input("Relé sepnuté. Stiskni Enter pro rozepnutí...")
    _run_gpioset(0)


if __name__ == "__main__":  # pragma: no cover - manual utility
    main()
