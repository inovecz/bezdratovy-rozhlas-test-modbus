#!/usr/bin/env python3
"""Simple helper to test a relay controlled via a GPIO line."""

import gpiod
from gpiod import line

CHIP = "/dev/gpiochip2"
PIN = 8  # BCM number of the GPIO driving the relay
ACTIVE_HIGH = True  # Flip to False if your relay triggers on low level

VALUE_ON = line.Value.ACTIVE if ACTIVE_HIGH else line.Value.INACTIVE
VALUE_OFF = line.Value.INACTIVE if ACTIVE_HIGH else line.Value.ACTIVE


def main() -> None:
    with gpiod.request_lines(
        CHIP,
        consumer="relay-toggle",
        config={PIN: gpiod.LineSettings(direction=line.Direction.OUTPUT)},
    ) as request:
        request.set_value(PIN, VALUE_ON)
        input("Relay energised. Press Enter to release...")
        request.set_value(PIN, VALUE_OFF)


if __name__ == "__main__":  # pragma: no cover - manual utility
    main()
