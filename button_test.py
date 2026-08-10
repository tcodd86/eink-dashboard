"""Standalone diagnostic for the HAT's 4 physical buttons.

Neither the Waveshare user manual nor the spec sheet documents these buttons
(they only cover the 8-pin SPI interface), so the BUTTON_PINS mapping in
config.py is sourced from a third-party writeup, not Waveshare's own docs.
Run this once on real hardware before trusting it:

    python3 button_test.py

Press each physical button top to bottom and note which GPIO number gets
printed for each. If the order doesn't match config.BUTTON_PINS
(button1..button4, top to bottom), edit config.py to match reality.

Press Ctrl+C to exit.
"""

from __future__ import annotations

from signal import pause

from gpiozero import Button

CANDIDATE_PINS = [5, 6, 13, 19]


def _make_handler(pin: int):
    def handler() -> None:
        print(f"Button on GPIO{pin} pressed")

    return handler


def main() -> None:
    buttons = []
    for pin in CANDIDATE_PINS:
        button = Button(pin, bounce_time=0.05)
        button.when_pressed = _make_handler(pin)
        buttons.append(button)

    print("Press each physical button on the HAT, top to bottom.")
    print("Expected order: GPIO5, GPIO6, GPIO13, GPIO19.")
    print("If a different pin prints for a given physical button, update")
    print("BUTTON_PINS in config.py to match. Ctrl+C to exit.\n")

    try:
        pause()
    except KeyboardInterrupt:
        print("\nExiting.")


if __name__ == "__main__":
    main()
