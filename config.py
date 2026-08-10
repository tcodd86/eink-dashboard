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

# --- Clock --------------------------------------------------------------------
CLOCK_REFRESH_SECONDS = 60  # redraw the Home screen this often while it's on screen
TIME_FORMAT = "%I:%M %p"  # 12-hour clock with AM/PM, e.g. "02:47 PM"
DATE_FORMAT = "%a, %b"  # day number is appended separately (see screens/home.py) to
# avoid relying on the non-portable %-d / %#d "no leading zero" strftime flag

# --- Buttons ------------------------------------------------------------------
# BCM GPIO pin numbers for the 4 physical buttons on the HAT, top to bottom.
# UNVERIFIED from Waveshare's own docs (their schematic PDF wasn't reachable) --
# sourced from a third-party writeup. Run button_test.py once on real hardware
# to confirm this mapping before trusting it; edit here if it's wrong.
#
# Button meaning is context-dependent (see main.py):
#   On the Home screen:    1=7-Day Forecast 2=First Reading 3=Psalm 4=Gospel
#   On the Forecast screen: 1=Back to Home  2/3/4=unused
#   On a reading screen:    1=Back to Home  2=Scroll up 3=Scroll down 4=Next reading
BUTTON_PINS = {
    "button1": 5,
    "button2": 6,
    "button3": 13,
    "button4": 19,
}

# Order buttons 2/3/4 cycle through from the Home screen, and that button4
# advances through while already viewing a reading.
READING_KEYS = ["first_reading", "psalm", "gospel"]

# --- Display --------------------------------------------------------------------
EPD_WIDTH = 176  # native controller width (portrait orientation)
EPD_HEIGHT = 264  # native controller height (portrait orientation)
