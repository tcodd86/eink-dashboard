"""Standalone diagnostic for the HAT's 4 physical buttons.

Neither the Waveshare user manual nor the spec sheet documents these buttons
(they only cover the 8-pin SPI interface). Run this on real hardware any
time you need to (re-)confirm the mapping -- e.g. on a different HAT unit:

    python3 button_test.py

Press each physical button top to bottom and note which GPIO number gets
printed for each. If the order doesn't match config.BUTTON_PINS
(button1..button4, top to bottom), edit config.py to match reality.

Reads pin numbers from config.BUTTON_PINS rather than hardcoding them here,
so this can't silently drift out of sync with config.py the way it did once
before.

Press Ctrl+C to exit.
"""

from __future__ import annotations

from signal import pause

from gpiozero import Button

import config

_BUTTON_ORDER = ["button1", "button2", "button3", "button4"]


def _make_handler(pin: int):
    def handler() -> None:
        print(f"Button on GPIO{pin} pressed")

    return handler


def main() -> None:
    buttons = []
    for name in _BUTTON_ORDER:
        pin = config.BUTTON_PINS[name]
        button = Button(pin, bounce_time=0.05)
        button.when_pressed = _make_handler(pin)
        buttons.append(button)

    expected = ", ".join(f"GPIO{config.BUTTON_PINS[name]}" for name in _BUTTON_ORDER)
    print("Press each physical button on the HAT, top to bottom.")
    print(f"Expected order (from config.py's BUTTON_PINS): {expected}.")
    print("If a different pin prints for a given physical button, update")
    print("BUTTON_PINS in config.py to match. Ctrl+C to exit.\n")

    try:
        pause()
    except KeyboardInterrupt:
        print("\nExiting.")


if __name__ == "__main__":
    main()
