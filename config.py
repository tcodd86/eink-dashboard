"""Hardcoded configuration for the e-ink dashboard.

Edit these values for your own setup. Nothing here talks to hardware directly.
"""

try:
    from config_local import LATITUDE, LONGITUDE
except ImportError as exc:
    raise ImportError(
        "config_local.py not found. Copy config_local.py.example to config_local.py "
        "and fill in your location's latitude/longitude (this file is gitignored -- "
        "it's kept out of version control since it reveals your approximate location)."
    ) from exc

# --- Location / weather -----------------------------------------------------
TEMP_UNIT = "fahrenheit"  # Open-Meteo accepts "celsius" or "fahrenheit"

WEATHER_REFRESH_SECONDS = 600  # how often to poll Open-Meteo in the background

# --- Mass readings -----------------------------------------------------------
READINGS_REFRESH_CHECK_SECONDS = 3600  # how often to check whether the date rolled over

# --- Latin word of the day -----------------------------------------------------
LATIN_WORD_REFRESH_CHECK_SECONDS = 3600  # how often to check whether the date rolled over

# --- Clock --------------------------------------------------------------------
# Home screen redraws every real minute boundary while it's on screen (see
# main.py._clock_loop) -- not a configurable interval, since a clock that
# updates on any cadence other than "aligned to the actual minute" would
# just be a different flavor of stale.
TIME_FORMAT = "%I:%M %p"  # 12-hour clock with AM/PM, e.g. "02:47 PM"
DATE_FORMAT = "%a, %b"  # day number is appended separately (see screens/home.py) to
# avoid relying on the non-portable %-d / %#d "no leading zero" strftime flag

# --- Idle timeout ---------------------------------------------------------------
# Any button press resets this, regardless of screen or whether it was a no-op.
IDLE_TIMEOUT_SECONDS = 300  # return to Home after this long without a button press
IDLE_TIMEOUT_CHECK_SECONDS = 15  # how often to check (just a polling granularity,
# not a precision guarantee -- the actual return can lag up to this long past
# IDLE_TIMEOUT_SECONDS)

# --- Buttons ------------------------------------------------------------------
# BCM GPIO pin numbers for the 4 physical buttons on the HAT, top to bottom.
# Verified with button_test.py on real hardware -- the reverse of the
# third-party writeup this was originally sourced from (button1/top is
# GPIO19, not GPIO5), because this panel is physically mounted buttons-on-
# the-right, upside down relative to the silkscreen's intended orientation
# (see the display rotation comment in main.py._push).
#
# Button meaning is context-dependent (see main.py):
#   On the Home screen:        1=7-Day Forecast 2=Hourly Forecast 3=Mass Readings menu 4=Latin Word
#   On the Forecast screen:    1=Back to Home   2/3/4=unused
#   On the Hourly Forecast:    1=Back to Home   2=Scroll up 3=Scroll down 4=unused
#   On the Mass Readings menu: 1=Back to Home   2=First Reading 3=Psalm 4=Gospel
#   On the Latin Word screen:  1=Back to Home   2/3/4=unused
#   On a reading screen:       1=Back to Home   2=Scroll up 3=Scroll down 4=Next reading
BUTTON_PINS = {
    "button1": 19,
    "button2": 13,
    "button3": 6,
    "button4": 5,
}

# Order buttons 2/3/4 cycle through from the Home screen, and that button4
# advances through while already viewing a reading.
READING_KEYS = ["first_reading", "psalm", "gospel"]

# --- Display --------------------------------------------------------------------
EPD_WIDTH = 176  # native controller width (portrait orientation)
EPD_HEIGHT = 264  # native controller height (portrait orientation)
