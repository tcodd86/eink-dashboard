"""Entry point. Wires the 4 HAT buttons and background refresh timers to the
screen state machine, and pushes rendered screens to the e-Paper display.

Button behavior is context-dependent:
  On the Home screen:          1=7-Day Forecast 2=Hourly Forecast 3=Mass Readings menu 4=Latin Word
  On the Forecast screen:      1=Back to Home   2/3/4=unused
  On the Hourly Forecast:      1=Back to Home   2=Scroll up 3=Scroll down 4=unused
  On the Mass Readings menu:   1=Back to Home   2=First Reading 3=Psalm 4=Gospel
  On the Latin Word screen:    1=Back to Home   2/3/4=unused
  On a reading screen:         1=Back to Home   2=Scroll up 3=Scroll down 4=Next reading

Any screen other than Home auto-returns to Home after config.IDLE_TIMEOUT_SECONDS
without a button press (see _idle_timeout_loop).
"""

from __future__ import annotations

import datetime
import logging
import signal
import threading
import time

from gpiozero import Button
from PIL import Image

import config
from display.epd_driver import epd2in7
from screens import forecast, home, hourly_forecast, reading, readings_menu
from screens import latin_word as latin_word_screen
from sources.latin_word import LatinWordSource
from sources.mass_readings import MassReadingsSource
from sources.weather import WeatherSource

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class App:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stop = threading.Event()

        self._epd = epd2in7.EPD()
        self._weather = WeatherSource(config.LATITUDE, config.LONGITUDE, config.TEMP_UNIT)
        self._readings = MassReadingsSource()
        self._latin_word = LatinWordSource()
        self._buttons: list[Button] = []

        # "home", "forecast", "hourly_forecast", "readings_menu", "latin_word",
        # or one of config.READING_KEYS
        self._screen = "home"
        self._page = 0
        # time.monotonic(), not datetime.now(): immune to wall-clock jumps
        # (NTP sync, DST) that would otherwise throw off idle-timeout math.
        self._last_activity = time.monotonic()

    def start(self) -> None:
        signal.signal(signal.SIGTERM, self._handle_stop_signal)
        signal.signal(signal.SIGINT, self._handle_stop_signal)

        logger.info("Initializing e-Paper display")
        if self._epd.init() != 0:
            raise RuntimeError("e-Paper init failed")
        self._epd.Clear()

        logger.info("Fetching initial weather, readings, and Latin word")
        self._weather.refresh()
        self._readings.refresh()
        self._latin_word.refresh()

        self._setup_buttons()

        threading.Thread(target=self._weather_loop, daemon=True).start()
        threading.Thread(target=self._readings_loop, daemon=True).start()
        threading.Thread(target=self._latin_word_loop, daemon=True).start()
        threading.Thread(target=self._clock_loop, daemon=True).start()
        threading.Thread(target=self._idle_timeout_loop, daemon=True).start()

        with self._lock:
            self._show_home()

        logger.info("Ready.")
        while not self._stop.is_set():
            self._stop.wait(1)

        logger.info("Shutting down; putting display to sleep")
        self._epd.sleep()

    def _handle_stop_signal(self, signum: int, _frame: object) -> None:
        logger.info("Received signal %s, shutting down", signum)
        self._stop.set()

    # --- background loops ----------------------------------------------------
    #
    # Each loop body is wrapped in try/except: an uncaught exception in a
    # daemon thread doesn't crash the app, it just silently kills that one
    # thread forever (Python prints it to stderr and moves on) -- which
    # previously meant a single transient error (e.g. a rare display-write
    # hiccup) could permanently stop the once-a-minute clock tick, idle
    # timeout, or a background refresh, with everything else (buttons, other
    # loops) continuing to work fine. Catching and logging here means a bad
    # iteration is skipped instead of ending the loop.

    def _weather_loop(self) -> None:
        while not self._stop.wait(config.WEATHER_REFRESH_SECONDS):
            try:
                self._weather.refresh()
            except Exception:
                logger.exception("weather_loop iteration failed; will retry next cycle")

    def _readings_loop(self) -> None:
        while not self._stop.wait(config.READINGS_REFRESH_CHECK_SECONDS):
            try:
                self._readings.refresh()
            except Exception:
                logger.exception("readings_loop iteration failed; will retry next cycle")

    def _latin_word_loop(self) -> None:
        while not self._stop.wait(config.LATIN_WORD_REFRESH_CHECK_SECONDS):
            try:
                self._latin_word.refresh()
            except Exception:
                logger.exception("latin_word_loop iteration failed; will retry next cycle")

    def _clock_loop(self) -> None:
        # Waits until the next real minute boundary each iteration (rather
        # than a fixed 60s from whenever this thread happened to start), so
        # the displayed time can't sit stale for up to 59 seconds depending
        # on an arbitrary boot-time phase offset.
        while True:
            now = datetime.datetime.now()
            seconds_until_next_minute = 60 - now.second - now.microsecond / 1_000_000
            if self._stop.wait(seconds_until_next_minute):
                return
            try:
                with self._lock:
                    if self._screen == "home":
                        self._show_home()
            except Exception:
                logger.exception("clock_loop iteration failed; will retry next minute")

    def _idle_timeout_loop(self) -> None:
        while not self._stop.wait(config.IDLE_TIMEOUT_CHECK_SECONDS):
            try:
                with self._lock:
                    idle_for = time.monotonic() - self._last_activity
                    if self._screen != "home" and idle_for >= config.IDLE_TIMEOUT_SECONDS:
                        logger.info("No activity for %.0fs (screen=%s) -> home", idle_for, self._screen)
                        self._show_home()
            except Exception:
                logger.exception("idle_timeout_loop iteration failed; will retry next check")

    # --- buttons ---------------------------------------------------------------

    def _setup_buttons(self) -> None:
        handlers = {
            "button1": self.on_button1,
            "button2": self.on_button2,
            "button3": self.on_button3,
            "button4": self.on_button4,
        }
        for name, pin in config.BUTTON_PINS.items():
            button = Button(pin, bounce_time=0.05)
            button.when_pressed = handlers[name]
            self._buttons.append(button)
            logger.info("Button %s -> GPIO%d", name, pin)

    def on_button1(self) -> None:
        with self._lock:
            self._last_activity = time.monotonic()
            if self._screen == "home":
                logger.info("button1 pressed (home) -> forecast")
                self._show_forecast()
            else:
                logger.info("button1 pressed (%s) -> home", self._screen)
                self._show_home()

    def on_button2(self) -> None:
        with self._lock:
            self._last_activity = time.monotonic()
            if self._screen == "home":
                logger.info("button2 pressed (home) -> hourly_forecast")
                self._show_hourly_forecast()
            elif self._screen == "hourly_forecast":
                logger.info("button2 pressed (hourly_forecast) -> scroll up")
                self._show_hourly_forecast(page=self._page - 1)
            elif self._screen == "readings_menu":
                logger.info("button2 pressed (readings_menu) -> %s", config.READING_KEYS[0])
                self._show_reading(config.READING_KEYS[0], page=0)
            elif self._screen in config.READING_KEYS:
                logger.info("button2 pressed (%s) -> scroll up", self._screen)
                self._show_reading(self._screen, page=self._page - 1)
            elif self._screen == "latin_word":
                logger.info("button2 pressed (latin_word) -> scroll up")
                self._show_latin_word(page=self._page - 1)
            else:
                logger.info("button2 pressed (%s) -> no-op", self._screen)

    def on_button3(self) -> None:
        with self._lock:
            self._last_activity = time.monotonic()
            if self._screen == "home":
                logger.info("button3 pressed (home) -> readings_menu")
                self._show_readings_menu()
            elif self._screen == "hourly_forecast":
                logger.info("button3 pressed (hourly_forecast) -> scroll down")
                self._show_hourly_forecast(page=self._page + 1)
            elif self._screen == "readings_menu":
                logger.info("button3 pressed (readings_menu) -> %s", config.READING_KEYS[1])
                self._show_reading(config.READING_KEYS[1], page=0)
            elif self._screen in config.READING_KEYS:
                logger.info("button3 pressed (%s) -> scroll down", self._screen)
                self._show_reading(self._screen, page=self._page + 1)
            elif self._screen == "latin_word":
                logger.info("button3 pressed (latin_word) -> scroll down")
                self._show_latin_word(page=self._page + 1)
            else:
                logger.info("button3 pressed (%s) -> no-op", self._screen)

    def on_button4(self) -> None:
        with self._lock:
            self._last_activity = time.monotonic()
            if self._screen == "home":
                logger.info("button4 pressed (home) -> latin_word")
                self._show_latin_word()
            elif self._screen == "readings_menu":
                logger.info("button4 pressed (readings_menu) -> %s", config.READING_KEYS[2])
                self._show_reading(config.READING_KEYS[2], page=0)
            elif self._screen in config.READING_KEYS:
                idx = config.READING_KEYS.index(self._screen)
                next_key = config.READING_KEYS[(idx + 1) % len(config.READING_KEYS)]
                logger.info("button4 pressed (%s) -> next reading: %s", self._screen, next_key)
                self._show_reading(next_key, page=0)
            else:
                logger.info("button4 pressed (%s) -> no-op", self._screen)

    # --- screens (caller must hold self._lock) ----------------------------------

    def _show_home(self) -> None:
        self._screen = "home"
        self._page = 0
        image = home.render(self._weather.get_cached())
        self._push(image)

    def _show_forecast(self) -> None:
        self._screen = "forecast"
        self._page = 0
        image = forecast.render(self._weather.get_cached_forecast())
        self._push(image)

    def _show_hourly_forecast(self, page: int = 0) -> None:
        hourly = self._weather.get_cached_hourly()
        image, effective_page, _total_pages = hourly_forecast.render(hourly, page)
        self._screen = "hourly_forecast"
        self._page = effective_page
        self._push(image)

    def _show_readings_menu(self) -> None:
        self._screen = "readings_menu"
        self._page = 0
        image = readings_menu.render()
        self._push(image)

    def _show_latin_word(self, page: int = 0) -> None:
        latin_word = self._latin_word.get_cached()
        image, effective_page, _total_pages = latin_word_screen.render(latin_word, page)
        self._screen = "latin_word"
        self._page = effective_page
        self._push(image)

    def _show_reading(self, key: str, page: int) -> None:
        reading_obj = self._readings.get_cached(key)
        image, effective_page, _total_pages = reading.render(reading_obj, key, page)
        self._screen = key
        self._page = effective_page
        self._push(image)

    def _push(self, image) -> None:
        # This panel is physically mounted buttons-on-the-right, which is
        # upside down relative to the silkscreen's intended (buttons-on-the-
        # left) orientation -- so both the display and the button order (see
        # config.BUTTON_PINS) are flipped 180 degrees from the vendored
        # driver's/third-party writeup's assumptions. Rotate the image here
        # (not in renderer.py/screens/*.py, which stay hardware-orientation-
        # agnostic) rather than hand-editing the vendored driver.
        rotated = image.transpose(Image.Transpose.ROTATE_180)
        self._epd.display(self._epd.getbuffer(rotated))


def main() -> None:
    App().start()


if __name__ == "__main__":
    main()
