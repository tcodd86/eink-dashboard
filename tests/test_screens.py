"""Tests for screens/*.py: what each screen draws, its sidebar buttons, its
pagination, and that nothing spills off-screen or into the button sidebar."""

from __future__ import annotations

import datetime
import re

import pytest
from PIL import ImageDraw

from display import renderer
from screens import forecast, home, hourly_forecast, latin_word, reading, readings_menu
from sources.latin_word import LatinWord
from sources.mass_readings import Reading
from sources.weather import DayForecast, HourForecast, Weather
from tests.helpers import has_ink

CONTENT_RIGHT = renderer.CANVAS_SIZE[0] - renderer.SIDEBAR_WIDTH
HOME_ICONS = ["calendar", "clock", "bible", "ae"]
HOME_ONLY = ["home", None, None, None]
SCROLLING = ["home", "up", "down", None]


def _tokens(n, start=0):
    """Numbered words, so tests can check every word of long text is shown exactly once, in order."""
    return " ".join(f"w{i}" for i in range(start, start + n))


def _found_tokens(strings):
    return re.findall(r"\bw\d+\b", " ".join(strings))


@pytest.fixture
def text_positions(monkeypatch):
    """Records (x, text, width) for every string drawn, to check horizontal bounds."""
    recorded = []
    original = ImageDraw.ImageDraw.text

    def recording_text(self, xy, text, *args, font=None, **kwargs):
        recorded.append((xy[0], text, self.textlength(text, font=font)))
        return original(self, xy, text, *args, font=font, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", recording_text)
    return recorded


def _assert_stays_in_content_area(image, positions):
    """Nothing drawn left of the screen, past the sidebar edge, or inside the sidebar.
    (Pass the image from a render done with the `sidebar_icons` fixture active, so
    the sidebar itself isn't drawn and any ink there must be spilled content.)"""
    for x, text, width in positions:
        assert x >= 0, f"{text!r} starts off the left edge (x={x})"
        assert x + width <= CONTENT_RIGHT, f"{text!r} runs into the sidebar ({x + width:.0f} > {CONTENT_RIGHT})"
    assert not has_ink(image, (CONTENT_RIGHT, 0, image.width, image.height)), "content drew into the sidebar"


# --- Home ---------------------------------------------------------------------------

WEATHER = Weather(temperature=76.3, description="Clear sky", icon="sun")


def test_home_renders_full_size_1bit_canvas():
    image = home.render(WEATHER, now=datetime.datetime(2026, 1, 1, 9, 5))
    assert image.mode == "1" and image.size == renderer.CANVAS_SIZE


def test_home_sidebar_buttons(sidebar_icons):
    home.render(WEATHER)
    assert sidebar_icons == [HOME_ICONS]


@pytest.mark.parametrize(
    ("now", "time_text"),
    [
        (datetime.datetime(2026, 1, 1, 9, 5), "9:05 AM"),  # leading zero stripped
        (datetime.datetime(2026, 1, 1, 0, 30), "12:30 AM"),  # midnight hour
        (datetime.datetime(2026, 1, 1, 12, 0), "12:00 PM"),  # noon
        (datetime.datetime(2026, 1, 1, 23, 59), "11:59 PM"),
    ],
)
def test_home_shows_12_hour_time(drawn_text, now, time_text):
    home.render(WEATHER, now=now)
    assert time_text in drawn_text


def test_home_shows_date_and_rounded_temperature(drawn_text):
    home.render(WEATHER, now=datetime.datetime(2026, 1, 1, 9, 5))
    assert "Thu, Jan 1" in drawn_text
    assert "76°F" in drawn_text


def test_home_without_weather_says_unavailable(drawn_text):
    home.render(None, now=datetime.datetime(2026, 1, 1, 9, 5))
    assert "Weather unavailable" in drawn_text
    assert "9:05 AM" in drawn_text  # clock still works


@pytest.mark.parametrize("hour", [0, 10, 11, 12, 22, 23])
@pytest.mark.parametrize("temperature", [-40.4, 5.0, 109.6])
def test_home_never_overflows(sidebar_icons, text_positions, hour, temperature):
    """Regression: the clock once ran off the left edge and into the sidebar on the
    Pi, whose font renders wider than the dev machine's."""
    now = datetime.datetime(2026, 9, 30, hour, 58)  # "Wed, Sep 30": a wide date
    image = home.render(Weather(temperature=temperature, description="", icon="thunderstorm"), now=now)
    _assert_stays_in_content_area(image, text_positions)


# --- 7-Day Forecast -----------------------------------------------------------------

WEEK = [
    DayForecast(datetime.date(2026, 10, 11) + datetime.timedelta(days=d), 81.4 + d, 61.6 + d, "", icon)
    for d, icon in enumerate(["sun", "partly_cloudy", "cloudy", "fog", "rain", "snow", "thunderstorm"])
]


def test_forecast_labels_and_temperatures(drawn_text):
    forecast.render(WEEK)
    assert drawn_text[0] == "7-Day Forecast"
    assert ["Today", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] == [t for t in drawn_text if t in
                                                                   ("Today", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")]
    assert "81° / 62°" in drawn_text  # rounded


def test_forecast_sidebar_only_has_home(sidebar_icons):
    forecast.render(WEEK)
    assert sidebar_icons == [HOME_ONLY]


def test_forecast_empty_says_unavailable(drawn_text):
    forecast.render([])
    assert "unavailable" in " ".join(drawn_text)


def test_forecast_never_overflows(sidebar_icons, text_positions):
    extreme = [DayForecast(d.date, 112.0, -21.0, "", d.icon) for d in WEEK]
    image = forecast.render(extreme)
    _assert_stays_in_content_area(image, text_positions)


# --- Hourly Forecast ----------------------------------------------------------------

START = datetime.datetime(2026, 10, 11, 14)  # 2 PM


def _hours(n, precip=20):
    return [HourForecast(START + datetime.timedelta(hours=h), 60.4 + h, "", "rain", precip) for h in range(n)]


def test_hourly_first_row_is_now_then_clock_hours(drawn_text):
    hourly_forecast.render(_hours(24))
    assert "Now" in drawn_text
    assert "3 PM" in drawn_text
    assert "2 PM" not in drawn_text  # the current hour shows as "Now"


def test_hourly_shows_temperature_and_rain_chance(drawn_text):
    hourly_forecast.render(_hours(24))
    assert "60°" in drawn_text
    assert "20%" in drawn_text


def test_hourly_missing_rain_chance_shows_dashes(drawn_text):
    hourly_forecast.render(_hours(6, precip=None))
    assert "--" in drawn_text
    assert not any(t.endswith("%") for t in drawn_text)


@pytest.mark.parametrize(("hours", "pages"), [(24, 4), (25, 5), (6, 1), (1, 1)])
def test_hourly_page_count(hours, pages):
    _image, _page, total = hourly_forecast.render(_hours(hours))
    assert total == pages


def test_hourly_second_page_continues_where_first_ended(drawn_text):
    hourly_forecast.render(_hours(24), page=1)
    assert "8 PM" in drawn_text  # row 7 overall (2 PM + 6h)
    assert "Now" not in drawn_text


def test_hourly_midnight_and_noon_labels(drawn_text):
    hourly_forecast.render(_hours(24), page=2)  # 2 AM -- 7 AM
    hourly_forecast.render(_hours(24), page=3)  # 8 AM -- 1 PM
    assert "12 PM" in drawn_text
    hourly_forecast.render(_hours(24), page=1)  # 8 PM -- 1 AM
    assert "12 AM" in drawn_text


@pytest.mark.parametrize(("requested", "effective"), [(-1, 0), (0, 0), (3, 3), (4, 3), (99, 3)])
def test_hourly_page_is_clamped(requested, effective):
    _image, page, _total = hourly_forecast.render(_hours(24), page=requested)
    assert page == effective


def test_hourly_scroll_arrows_only_when_multiple_pages(sidebar_icons):
    hourly_forecast.render(_hours(24))
    hourly_forecast.render(_hours(6))
    assert sidebar_icons == [SCROLLING, HOME_ONLY]


def test_hourly_empty_says_unavailable(drawn_text, sidebar_icons):
    _image, page, total = hourly_forecast.render([])
    assert (page, total) == (0, 1)
    assert "unavailable" in " ".join(drawn_text)
    assert sidebar_icons == [HOME_ONLY]


def test_hourly_never_overflows(sidebar_icons, text_positions):
    hours = [HourForecast(START + datetime.timedelta(hours=h), -100.0, "", "snow", 100) for h in range(24)]
    for page in range(4):
        text_positions.clear()
        image, *_ = hourly_forecast.render(hours, page=page)
        _assert_stays_in_content_area(image, text_positions)


# --- Mass Readings menu ---------------------------------------------------------------


def test_readings_menu(drawn_text, sidebar_icons):
    readings_menu.render()
    assert "Mass Readings" in drawn_text
    assert sidebar_icons == [["home", "book", "note", "cross"]]


# --- Reading screens ----------------------------------------------------------------

LONG_READING = Reading(heading="Gospel", citation="Matthew 14:22-33", body=_tokens(400))


@pytest.mark.parametrize(
    ("key", "title"), [("first_reading", "Reading(s)"), ("psalm", "Responsorial Psalm"), ("gospel", "Gospel")]
)
def test_reading_titles(drawn_text, key, title):
    reading.render(LONG_READING, key)
    assert drawn_text[0] == title


def test_reading_sidebar(sidebar_icons):
    reading.render(LONG_READING, "gospel")
    assert sidebar_icons == [["home", "up", "down", "right"]]


def test_reading_citation_only_on_first_page(drawn_text):
    reading.render(LONG_READING, "gospel", page=0)
    assert "Matthew 14:22-33" in drawn_text
    drawn_text.clear()
    reading.render(LONG_READING, "gospel", page=1)
    assert "Matthew 14:22-33" not in drawn_text


def test_reading_page_indicator(drawn_text):
    _image, _page, total = reading.render(LONG_READING, "gospel", page=1)
    assert total > 2
    assert f"2/{total}" in drawn_text


def test_short_reading_is_one_page_without_indicator(drawn_text):
    _image, _page, total = reading.render(Reading("Psalm", "Ps 23", "The Lord is my shepherd."), "psalm")
    assert total == 1
    assert not any(re.fullmatch(r"\d+/\d+", t) for t in drawn_text)


def test_every_word_of_a_long_reading_appears_once_in_order(drawn_text):
    _image, _page, total = reading.render(LONG_READING, "gospel")
    drawn_text.clear()
    for page in range(total):
        reading.render(LONG_READING, "gospel", page=page)
    assert _found_tokens(drawn_text) == LONG_READING.body.split()


@pytest.mark.parametrize("requested", [-5, 999])
def test_reading_page_is_clamped(requested):
    _image, page, total = reading.render(LONG_READING, "gospel", page=requested)
    assert page == (0 if requested < 0 else total - 1)


def test_unavailable_reading(drawn_text):
    _image, page, total = reading.render(None, "gospel")
    assert (page, total) == (0, 1)
    assert "unavailable" in " ".join(drawn_text)


def test_reading_never_overflows(sidebar_icons, text_positions):
    long_citation = "1 Kings 19:9a, 11-13a, 15-16, 19-21 | Romans 9:1-5, 8:35, 37-39 | Isaiah 55:1-3"
    long_word = "Constantinopolitanensibus " * 30
    long = Reading("First Reading", long_citation, long_word + _tokens(300))
    _image, _page, total = reading.render(long, "first_reading")
    for page in range(total):
        text_positions.clear()
        image, *_ = reading.render(long, "first_reading", page=page)
        _assert_stays_in_content_area(image, text_positions)


# --- Latin Word -------------------------------------------------------------------------

SHORT_WORD = LatinWord("excusare", "to excuse", "verb", "Ignorantia iuris neminem excusat.",
                       "Ignorance of the law excuses no one.")
LONG_WORD = LatinWord("saeculum", "age, century", "noun", _tokens(60), _tokens(60, start=60))


def test_latin_word_shows_all_fields(drawn_text):
    latin_word.render(SHORT_WORD)
    joined = " ".join(drawn_text)
    assert "excusare" in drawn_text
    assert "(verb) to excuse" in joined
    assert "Ignorantia iuris neminem excusat." in joined
    assert "— Ignorance of the law" in joined  # translation marked with a dash


def test_short_latin_word_is_one_page_without_scroll_arrows(sidebar_icons):
    _image, _page, total = latin_word.render(SHORT_WORD)
    assert total == 1
    assert sidebar_icons == [HOME_ONLY]


def test_long_latin_word_paginates_with_scroll_arrows(sidebar_icons):
    _image, _page, total = latin_word.render(LONG_WORD)
    assert total > 1
    assert sidebar_icons == [SCROLLING]


def test_latin_word_header_only_on_first_page(drawn_text):
    latin_word.render(LONG_WORD, page=1)
    assert "saeculum" not in drawn_text
    assert not any("(noun)" in t for t in drawn_text)


def test_latin_example_and_translation_fully_shown_in_order(drawn_text):
    """Regression: a long English translation used to be silently cut off."""
    _image, _page, total = latin_word.render(LONG_WORD)
    drawn_text.clear()
    for page in range(total):
        latin_word.render(LONG_WORD, page=page)
    assert _found_tokens(drawn_text) == [f"w{i}" for i in range(120)]


@pytest.mark.parametrize("requested", [-1, 999])
def test_latin_word_page_is_clamped(requested):
    _image, page, total = latin_word.render(LONG_WORD, page=requested)
    assert page == (0 if requested < 0 else total - 1)


def test_latin_word_unavailable(drawn_text, sidebar_icons):
    _image, page, total = latin_word.render(None)
    assert (page, total) == (0, 1)
    assert "unavailable" in " ".join(drawn_text)
    assert sidebar_icons == [HOME_ONLY]


def test_latin_word_without_examples_is_one_page():
    _image, _page, total = latin_word.render(LatinWord("aqua", "water", "noun", "", ""))
    assert total == 1


def test_latin_word_never_overflows(sidebar_icons, text_positions):
    # The word auto-shrinks to fit; "honorificabilitudinitatibus" (27 letters) is about
    # the longest real Latin-form word, so anything up to it must fit the title line.
    extreme = LatinWord("honorificabilitudinitatibus", "a very long definition " * 6, "adjective",
                        "Verbum " * 50, "Word " * 50)
    _image, _page, total = latin_word.render(extreme)
    for page in range(total):
        text_positions.clear()
        image, *_ = latin_word.render(extreme, page=page)
        _assert_stays_in_content_area(image, text_positions)
