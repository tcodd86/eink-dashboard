"""Entry point. Wires the 4 HAT buttons and background refresh timers to the
screen state machine, and pushes rendered screens to the e-Paper display.

Button behavior is context-dependent:
  On the Home screen:     1=7-Day Forecast 2=First Reading 3=Psalm 4=Gospel
  On the Forecast screen: 1=Back to Home   2/3/4=unused
  On a reading screen:    1=Back to Home   2=Scroll up 3=Scroll down 4=Next reading
"""

from __future__ import annotations

import logging
import signal
import threading

from gpiozero import Button

import config
from display.epd_driver import epd2in7
from screens import forecast, home, reading
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
        self._buttons: list[Button] = []

        self._screen = "home"  # "home", "forecast", or one of config.READING_KEYS
        self._page = 0

    def start(self) -> None:
        signal.signal(signal.SIGTERM, self._handle_stop_signal)
        signal.signal(signal.SIGINT, self._handle_stop_signal)

        logger.info("Initializing e-Paper display")
        if self._epd.init() != 0:
            raise RuntimeError("e-Paper init failed")
        self._epd.Clear()

        logger.info("Fetching initial weather and readings")
        self._weather.refresh()
        self._readings.refresh()

        self._setup_buttons()

        threading.Thread(target=self._weather_loop, daemon=True).start()
        threading.Thread(target=self._readings_loop, daemon=True).start()
        threading.Thread(target=self._clock_loop, daemon=True).start()

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

    def _weather_loop(self) -> None:
        while not self._stop.wait(config.WEATHER_REFRESH_SECONDS):
            self._weather.refresh()

    def _readings_loop(self) -> None:
        while not self._stop.wait(config.READINGS_REFRESH_CHECK_SECONDS):
            self._readings.refresh()

    def _clock_loop(self) -> None:
        while not self._stop.wait(config.CLOCK_REFRESH_SECONDS):
            with self._lock:
                if self._screen == "home":
                    self._show_home()

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
            if self._screen == "home":
                logger.info("button1 pressed (home) -> forecast")
                self._show_forecast()
            else:
                logger.info("button1 pressed (%s) -> home", self._screen)
                self._show_home()

    def on_button2(self) -> None:
        with self._lock:
            if self._screen == "home":
                logger.info("button2 pressed (home) -> %s", config.READING_KEYS[0])
                self._show_reading(config.READING_KEYS[0], page=0)
            elif self._screen in config.READING_KEYS:
                logger.info("button2 pressed (%s) -> scroll up", self._screen)
                self._show_reading(self._screen, page=self._page - 1)
            else:
                logger.info("button2 pressed (%s) -> no-op", self._screen)

    def on_button3(self) -> None:
        with self._lock:
            if self._screen == "home":
                logger.info("button3 pressed (home) -> %s", config.READING_KEYS[1])
                self._show_reading(config.READING_KEYS[1], page=0)
            elif self._screen in config.READING_KEYS:
                logger.info("button3 pressed (%s) -> scroll down", self._screen)
                self._show_reading(self._screen, page=self._page + 1)
            else:
                logger.info("button3 pressed (%s) -> no-op", self._screen)

    def on_button4(self) -> None:
        with self._lock:
            if self._screen == "home":
                logger.info("button4 pressed (home) -> %s", config.READING_KEYS[2])
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

    def _show_reading(self, key: str, page: int) -> None:
        reading_obj = self._readings.get_cached(key)
        image, effective_page, _total_pages = reading.render(reading_obj, key, page)
        self._screen = key
        self._page = effective_page
        self._push(image)

    def _push(self, image) -> None:
        self._epd.display(self._epd.getbuffer(image))


def main() -> None:
    App().start()


if __name__ == "__main__":
    main()
