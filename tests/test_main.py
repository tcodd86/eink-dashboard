"""Tests for main.py: the button state machine, background loops, startup, and
what gets sent to the display. Runs against the stand-in display driver and
gpiozero from conftest.py, with fake data sources (no network)."""

from __future__ import annotations

import datetime
import threading
import time
import types

import pytest
from PIL import Image

import config
import main
from sources.latin_word import LatinWord
from sources.mass_readings import Reading
from sources.weather import DayForecast, HourForecast, Weather

from tests.helpers import has_ink

FakeButton = main.Button  # the stand-in class from conftest.py that main.py actually imported
_START = datetime.datetime(2026, 10, 11, 14)


class FakeWeather:
    def __init__(self):
        self.refreshes = 0

    def refresh(self):
        self.refreshes += 1

    def get_cached(self):
        return Weather(70.0, "Clear sky", "sun")

    def get_cached_forecast(self):
        return [DayForecast(_START.date() + datetime.timedelta(days=d), 80.0, 60.0, "", "sun") for d in range(7)]

    def get_cached_hourly(self):
        return [HourForecast(_START + datetime.timedelta(hours=h), 60.0, "", "sun", 10) for h in range(24)]  # 4 pages


class FakeReadings:
    def __init__(self):
        self.refreshes = 0

    def refresh(self):
        self.refreshes += 1

    def get_cached(self, key):
        return Reading(key, f"{key} 1:1", " ".join(f"word{i}" for i in range(150)))  # several pages


class FakeLatinWord:
    def __init__(self):
        self.refreshes = 0

    def refresh(self):
        self.refreshes += 1

    def get_cached(self):
        return LatinWord("saeculum", "age", "noun", "Verbum " * 40, "Word " * 40)  # several pages


@pytest.fixture
def app():
    FakeButton.instances.clear()
    app = main.App()
    app._weather = FakeWeather()
    app._readings = FakeReadings()
    app._latin_word = FakeLatinWord()
    yield app
    app._stop.set()


def press(app, button):
    getattr(app, f"on_button{button}")()


def go_to(app, *buttons):
    """Starts from Home and presses `buttons` in order."""
    app._show_home()
    for b in buttons:
        press(app, b)


def frames(app):
    return len(app._epd.displayed)


# --- Home screen buttons --------------------------------------------------------------


@pytest.mark.parametrize(
    ("button", "screen"),
    [(1, "forecast"), (2, "hourly_forecast"), (3, "readings_menu"), (4, "latin_word")],
)
def test_home_buttons_open_each_screen(app, button, screen):
    go_to(app)
    press(app, button)
    assert app._screen == screen
    assert app._page == 0


@pytest.mark.parametrize(
    "path",
    [(1,), (2,), (3,), (4,), (3, 2), (3, 3), (3, 4), (2, 3, 3), (3, 2, 3, 3)],
    ids=["forecast", "hourly", "menu", "latin", "first", "psalm", "gospel", "hourly-p3", "reading-p3"],
)
def test_button1_returns_home_from_every_screen(app, path):
    go_to(app, *path)
    assert app._screen != "home"
    press(app, 1)
    assert (app._screen, app._page) == ("home", 0)


# --- Mass Readings menu and reading screens ---------------------------------------------


@pytest.mark.parametrize(("button", "key"), [(2, "first_reading"), (3, "psalm"), (4, "gospel")])
def test_readings_menu_opens_each_reading_at_page_one(app, button, key):
    go_to(app, 3)
    press(app, button)
    assert (app._screen, app._page) == (key, 0)


def test_reading_scrolls_down_and_up(app):
    go_to(app, 3, 4)  # Gospel
    press(app, 3)
    press(app, 3)
    assert app._page == 2
    press(app, 2)
    assert app._page == 1


def test_reading_scroll_stops_at_first_and_last_page(app):
    go_to(app, 3, 4)
    press(app, 2)
    assert app._page == 0
    previous = -1
    while app._page != previous:  # scroll down until the page stops advancing
        previous = app._page
        press(app, 3)
    assert app._page == previous > 0
    press(app, 3)
    assert app._page == previous


def test_reading_button4_cycles_readings_and_resets_page(app):
    go_to(app, 3, 2)  # First Reading
    press(app, 3)  # scroll to page 2
    seen = []
    for _ in range(4):
        press(app, 4)
        seen.append((app._screen, app._page))
    assert seen == [("psalm", 0), ("gospel", 0), ("first_reading", 0), ("psalm", 0)]


# --- Hourly Forecast and Latin Word scrolling ---------------------------------------------


@pytest.mark.parametrize("path", [(2,), (4,)], ids=["hourly", "latin"])
def test_paginated_screens_scroll_with_buttons_2_and_3(app, path):
    go_to(app, *path)
    screen = app._screen
    press(app, 3)
    assert (app._screen, app._page) == (screen, 1)
    press(app, 2)
    assert (app._screen, app._page) == (screen, 0)
    press(app, 2)
    assert app._page == 0  # can't scroll above the first page


def test_hourly_scroll_stops_at_last_page(app):
    go_to(app, 2)
    for _ in range(10):
        press(app, 3)
    assert app._page == 3  # 24 hours / 6 rows per page


# --- no-op buttons ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "button"),
    [((1,), 2), ((1,), 3), ((1,), 4), ((2,), 4), ((4,), 4)],
    ids=["forecast-b2", "forecast-b3", "forecast-b4", "hourly-b4", "latin-b4"],
)
def test_unused_buttons_do_nothing(app, path, button):
    go_to(app, *path)
    before = (app._screen, app._page, frames(app))
    press(app, button)
    assert (app._screen, app._page, frames(app)) == before  # no state change, no redraw


# --- every press is activity, every navigation is one redraw ------------------------------


@pytest.mark.parametrize("button", [1, 2, 3, 4])
def test_every_press_resets_the_idle_timer_even_if_it_does_nothing(app, button):
    go_to(app, 1)  # Forecast: buttons 2-4 do nothing here
    app._last_activity = 0.0
    press(app, button)
    assert app._last_activity > 0.0


def test_each_navigation_redraws_exactly_once(app):
    go_to(app)
    start = frames(app)
    for button in (3, 4, 1):  # menu -> Gospel -> Home
        press(app, button)
    assert frames(app) == start + 3


# --- what reaches the display ---------------------------------------------------------------


def test_frames_are_rotated_180_degrees_for_the_upside_down_mount(app, monkeypatch):
    marker = Image.new("1", (264, 176), 255)
    marker.putpixel((0, 0), 0)  # top-left of the composed screen...
    app._push(marker)
    shown = app._epd.displayed[-1]
    assert shown.getpixel((263, 175)) == 0  # ...ends up bottom-right on the panel
    assert shown.getpixel((0, 0)) == 255


def test_home_frame_is_a_real_rendered_screen(app):
    app._show_home()
    shown = app._epd.displayed[-1]
    assert shown.size == (264, 176)
    assert has_ink(shown)


# --- background loops -------------------------------------------------------------------


def _run_until(app, target, condition, timeout=3.0):
    """Runs a loop method in a thread until `condition()` holds, then stops it and
    checks it shut down cleanly."""
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.005)
    met = condition()
    app._stop.set()
    thread.join(timeout=2)
    assert not thread.is_alive(), "loop didn't exit after stop was requested"
    return met


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime.datetime(2026, 1, 1, 12, 5, 0), 60.0),
        (datetime.datetime(2026, 1, 1, 12, 5, 1), 59.0),
        (datetime.datetime(2026, 1, 1, 12, 5, 30, 500_000), 29.5),
        (datetime.datetime(2026, 1, 1, 12, 5, 59, 999_000), 0.001),
    ],
)
def test_seconds_until_next_minute(now, expected):
    assert main.seconds_until_next_minute(now) == pytest.approx(expected)


@pytest.fixture
def fast_clock(monkeypatch):
    monkeypatch.setattr(main, "seconds_until_next_minute", lambda now: 0.005)


def test_clock_loop_redraws_home(app, fast_clock):
    app._show_home()
    start = frames(app)
    assert _run_until(app, app._clock_loop, lambda: frames(app) >= start + 3)


def test_clock_loop_does_not_redraw_other_screens(app, fast_clock):
    go_to(app, 1)
    start = frames(app)
    _run_until(app, app._clock_loop, lambda: False, timeout=0.2)
    assert frames(app) == start
    assert app._screen == "forecast"


def test_clock_loop_survives_a_failed_redraw(app, fast_clock, monkeypatch):
    """Regression: one exception (a null temperature crashing round()) used to kill the
    clock thread for good, freezing the Home screen while buttons kept working."""
    calls = []

    def flaky_show_home():
        calls.append(1)
        if len(calls) == 1:
            raise TypeError("type NoneType doesn't define __round__ method")

    monkeypatch.setattr(app, "_show_home", flaky_show_home)
    assert _run_until(app, app._clock_loop, lambda: len(calls) >= 3)


@pytest.mark.parametrize(
    ("loop", "source", "interval"),
    [
        ("_weather_loop", "_weather", "WEATHER_REFRESH_SECONDS"),
        ("_readings_loop", "_readings", "READINGS_REFRESH_CHECK_SECONDS"),
        ("_latin_word_loop", "_latin_word", "LATIN_WORD_REFRESH_CHECK_SECONDS"),
    ],
)
def test_refresh_loops_keep_running_after_an_exception(app, monkeypatch, loop, source, interval):
    monkeypatch.setattr(config, interval, 0.005)
    attempts = []

    def flaky_refresh():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("boom")

    monkeypatch.setattr(getattr(app, source), "refresh", flaky_refresh)
    assert _run_until(app, getattr(app, loop), lambda: len(attempts) >= 3)


@pytest.fixture
def fast_idle_check(monkeypatch):
    monkeypatch.setattr(config, "IDLE_TIMEOUT_CHECK_SECONDS", 0.005)


def test_idle_timeout_returns_to_home(app, fast_idle_check, monkeypatch):
    monkeypatch.setattr(config, "IDLE_TIMEOUT_SECONDS", 300)
    go_to(app, 3, 4)  # Gospel
    app._last_activity = time.monotonic() - 301
    assert _run_until(app, app._idle_timeout_loop, lambda: app._screen == "home")


def test_idle_timeout_waits_while_there_is_activity(app, fast_idle_check, monkeypatch):
    monkeypatch.setattr(config, "IDLE_TIMEOUT_SECONDS", 300)
    go_to(app, 3, 4)
    app._last_activity = time.monotonic() - 299
    _run_until(app, app._idle_timeout_loop, lambda: False, timeout=0.2)
    assert app._screen == "gospel"


def test_idle_timeout_does_not_redraw_home_repeatedly(app, fast_idle_check, monkeypatch):
    monkeypatch.setattr(config, "IDLE_TIMEOUT_SECONDS", 0)
    app._show_home()
    start = frames(app)
    _run_until(app, app._idle_timeout_loop, lambda: False, timeout=0.2)
    assert frames(app) == start


def test_idle_timeout_survives_a_failed_redraw(app, fast_idle_check, monkeypatch):
    monkeypatch.setattr(config, "IDLE_TIMEOUT_SECONDS", 0)
    go_to(app, 1)
    calls = []

    def flaky_show_home():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("SPI hiccup")
        app._screen = "home"

    monkeypatch.setattr(app, "_show_home", flaky_show_home)
    assert _run_until(app, app._idle_timeout_loop, lambda: app._screen == "home")
    assert len(calls) == 2


# --- startup and shutdown -------------------------------------------------------------


@pytest.fixture
def no_signal_handlers(monkeypatch):
    # start() installs SIGTERM/SIGINT handlers, which Python only allows on the main
    # thread; the test itself doesn't need them.
    monkeypatch.setattr(main.signal, "signal", lambda *args: None)


def test_start_initializes_everything_and_shuts_down_cleanly(app, no_signal_handlers):
    app._stop.set()  # request shutdown immediately, so start() returns
    app.start()

    assert app._epd.cleared == 1
    assert (app._weather.refreshes, app._readings.refreshes, app._latin_word.refreshes) == (1, 1, 1)
    assert app._screen == "home" and frames(app) == 1
    assert app._epd.slept


def test_start_wires_all_four_buttons(app, no_signal_handlers):
    app._stop.set()
    app.start()

    assert sorted(b.pin for b in FakeButton.instances) == sorted(config.BUTTON_PINS.values())
    by_pin = {b.pin: b for b in FakeButton.instances}
    by_pin[config.BUTTON_PINS["button2"]].when_pressed()  # physical button 2 on Home
    assert app._screen == "hourly_forecast"


def test_start_fails_loudly_if_display_init_fails(app, no_signal_handlers, monkeypatch):
    monkeypatch.setattr(app._epd, "init", lambda: -1)
    with pytest.raises(RuntimeError, match="e-Paper init failed"):
        app.start()


def test_stop_signal_requests_shutdown(app):
    app._handle_stop_signal(15, None)
    assert app._stop.is_set()


# --- config sanity ---------------------------------------------------------------------


def test_button_pins_are_four_distinct_gpios():
    assert set(config.BUTTON_PINS) == {"button1", "button2", "button3", "button4"}
    assert len(set(config.BUTTON_PINS.values())) == 4


def test_reading_keys_have_titles():
    from screens import reading

    assert set(config.READING_KEYS) == set(reading.TITLES)


def test_idle_timeout_is_longer_than_its_check_interval():
    assert config.IDLE_TIMEOUT_SECONDS > config.IDLE_TIMEOUT_CHECK_SECONDS > 0
