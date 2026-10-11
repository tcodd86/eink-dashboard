"""Tests for sources/weather.py (Open-Meteo fetch, parsing, and caching)."""

from __future__ import annotations

import datetime
import types
from unittest.mock import MagicMock

import pytest
import requests

from sources import weather as weather_mod
from sources.weather import WeatherSource

_TODAY = datetime.date(2026, 10, 11)


def _payload(
    *,
    current_temp=70.0,
    current_code=0,
    daily_highs=None,
    daily_lows=None,
    daily_codes=None,
    hourly_temps=None,
    hourly_codes=None,
    hourly_precip=None,
):
    """A response shaped like Open-Meteo's: 7 daily entries, and 48 hourly
    entries starting at local midnight today (as the real API returns)."""
    midnight = datetime.datetime.combine(_TODAY, datetime.time())
    return {
        "current": {"temperature_2m": current_temp, "weather_code": current_code},
        "daily": {
            "time": [(_TODAY + datetime.timedelta(days=d)).isoformat() for d in range(7)],
            "weather_code": daily_codes or [0] * 7,
            "temperature_2m_max": daily_highs or [80.0 + d for d in range(7)],
            "temperature_2m_min": daily_lows or [60.0 + d for d in range(7)],
        },
        "hourly": {
            "time": [(midnight + datetime.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(48)],
            "weather_code": hourly_codes or [0] * 48,
            "temperature_2m": hourly_temps or [50.0 + h for h in range(48)],
            "precipitation_probability": hourly_precip or [h % 100 for h in range(48)],
        },
    }


@pytest.fixture
def freeze_now(monkeypatch):
    """Freezes weather.py's notion of "now" (used to start the hourly window)."""

    def freeze(hour, minute=37):
        frozen = datetime.datetime.combine(_TODAY, datetime.time(hour, minute))

        class FrozenDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return frozen

        monkeypatch.setattr(weather_mod, "datetime", types.SimpleNamespace(datetime=FrozenDateTime, date=datetime.date))

    freeze(14)
    return freeze


@pytest.fixture
def api(monkeypatch):
    """Serves queued responses (dicts) or raises queued exceptions from requests.get."""
    queue = []
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append({"url": url, "params": params, "timeout": timeout})
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = MagicMock(return_value=item)
        return response

    monkeypatch.setattr(weather_mod.requests, "get", fake_get)
    api = types.SimpleNamespace(queue=queue, calls=calls)
    return api


@pytest.fixture
def source(freeze_now, api):
    return WeatherSource(40.0, -95.0, "fahrenheit")


# --- parsing ----------------------------------------------------------------------


def test_nothing_cached_before_first_fetch():
    src = WeatherSource(0, 0)
    assert src.get_cached() is None
    assert src.get_cached_forecast() == []
    assert src.get_cached_hourly() == []


def test_parses_current_conditions(source, api):
    api.queue.append(_payload(current_temp=72.4, current_code=3))
    source.refresh()
    current = source.get_cached()
    assert current.temperature == 72.4
    assert current.description == "Overcast"
    assert current.icon == "cloudy"


def test_parses_seven_day_forecast(source, api):
    api.queue.append(_payload())
    source.refresh()
    forecast = source.get_cached_forecast()
    assert len(forecast) == 7
    assert forecast[0].date == _TODAY
    assert forecast[6].date == _TODAY + datetime.timedelta(days=6)
    assert (forecast[2].high, forecast[2].low) == (82.0, 62.0)


def test_hourly_window_starts_at_current_hour_and_spans_24_hours(source, api):
    api.queue.append(_payload())
    source.refresh()
    hourly = source.get_cached_hourly()
    assert len(hourly) == 24
    assert hourly[0].time == datetime.datetime.combine(_TODAY, datetime.time(14))  # frozen at 14:37
    assert hourly[0].temperature == 50.0 + 14
    assert hourly[-1].time == datetime.datetime.combine(_TODAY + datetime.timedelta(days=1), datetime.time(13))


def test_hourly_window_late_in_day_reaches_into_tomorrow(source, api, freeze_now):
    freeze_now(23, 59)
    api.queue.append(_payload())
    source.refresh()
    hourly = source.get_cached_hourly()
    assert len(hourly) == 24
    assert hourly[0].time.hour == 23
    assert hourly[-1].time == datetime.datetime.combine(_TODAY + datetime.timedelta(days=1), datetime.time(22))


def test_hourly_window_right_after_midnight(source, api, freeze_now):
    freeze_now(0, 0)
    api.queue.append(_payload())
    source.refresh()
    assert source.get_cached_hourly()[0].time == datetime.datetime.combine(_TODAY, datetime.time(0))


def test_hourly_includes_rain_chance(source, api):
    api.queue.append(_payload())
    source.refresh()
    assert source.get_cached_hourly()[0].precipitation_probability == 14


@pytest.mark.parametrize(
    ("code", "icon", "description"),
    [
        (0, "sun", "Clear sky"),
        (1, "sun", "Mostly clear"),
        (2, "partly_cloudy", "Partly cloudy"),
        (3, "cloudy", "Overcast"),
        (45, "fog", "Fog"),
        (61, "rain", "Light rain"),
        (73, "snow", "Snow"),
        (95, "thunderstorm", "Thunderstorm"),
    ],
)
def test_weather_codes_map_to_icons(source, api, code, icon, description):
    api.queue.append(_payload(current_code=code))
    source.refresh()
    assert (source.get_cached().icon, source.get_cached().description) == (icon, description)


def test_unknown_weather_code_falls_back_to_cloudy(source, api):
    api.queue.append(_payload(current_code=12345))
    source.refresh()
    assert source.get_cached().icon == "cloudy"
    assert source.get_cached().description == "Weather code 12345"


def test_every_mapped_icon_is_drawable():
    from display import icons

    for _description, icon in weather_mod._WEATHER_CODES.values():
        assert icon in icons._WEATHER_ICONS
    assert weather_mod._DEFAULT_ICON in icons._WEATHER_ICONS


def test_request_parameters(source, api):
    api.queue.append(_payload())
    source.refresh()
    params = api.calls[0]["params"]
    assert (params["latitude"], params["longitude"]) == (40.0, -95.0)
    assert params["temperature_unit"] == "fahrenheit"
    assert params["forecast_days"] == 7
    assert params["forecast_hours"] == 48
    assert "precipitation_probability" in params["hourly"]
    assert api.calls[0]["timeout"] is not None  # a hung request must not block the loop forever


# --- failures keep the last good data ------------------------------------------


@pytest.mark.parametrize(
    "error",
    [requests.ConnectionError("no network"), requests.Timeout("slow"), ValueError("bad json")],
)
def test_request_failure_keeps_last_cached_values(source, api, error):
    api.queue.append(_payload(current_temp=70.0))
    source.refresh()
    before = (source.get_cached(), source.get_cached_forecast(), source.get_cached_hourly())

    api.queue.append(error)
    source.refresh()  # must not raise

    assert (source.get_cached(), source.get_cached_forecast(), source.get_cached_hourly()) == before


def test_http_error_status_keeps_last_cached_values(source, api, monkeypatch):
    api.queue.append(_payload(current_temp=70.0))
    source.refresh()

    bad = MagicMock()
    bad.raise_for_status.side_effect = requests.HTTPError("503")
    monkeypatch.setattr(weather_mod.requests, "get", lambda *a, **k: bad)
    source.refresh()

    assert source.get_cached().temperature == 70.0


def test_failure_before_any_success_leaves_cache_empty(source, api):
    api.queue.append(requests.ConnectionError("no network"))
    source.refresh()
    assert source.get_cached() is None


# --- null fields (Open-Meteo sometimes returns 200 OK with nulls) -----------------


def test_null_current_temperature_keeps_last_current_value(source, api):
    """Regression: a null current temp used to be cached and crash round() on render."""
    api.queue.append(_payload(current_temp=70.0))
    source.refresh()
    api.queue.append(_payload(current_temp=None))
    source.refresh()
    assert source.get_cached().temperature == 70.0


def test_null_current_temperature_before_any_success_caches_nothing(source, api):
    api.queue.append(_payload(current_temp=None))
    source.refresh()
    assert source.get_cached() is None


def test_null_current_temperature_still_updates_forecasts(source, api):
    api.queue.append(_payload(current_temp=70.0))
    source.refresh()
    api.queue.append(_payload(current_temp=None, daily_highs=[99.0] * 7))
    source.refresh()
    assert source.get_cached_forecast()[0].high == 99.0


def test_null_forecast_value_does_not_block_current_temperature(source, api):
    """Regression: a single null anywhere in the forecasts used to discard the whole
    response, freezing the Home screen's temperature."""
    api.queue.append(_payload(current_temp=70.0))
    source.refresh()

    precip = [10] * 48
    precip[40] = None
    highs = [80.0] * 7
    highs[5] = None
    api.queue.append(_payload(current_temp=71.0, hourly_precip=precip, daily_highs=highs))
    source.refresh()

    assert source.get_cached().temperature == 71.0


def test_day_with_null_high_or_low_is_skipped(source, api):
    highs = [80.0] * 7
    highs[2] = None
    lows = [60.0] * 7
    lows[4] = None
    api.queue.append(_payload(daily_highs=highs, daily_lows=lows))
    source.refresh()
    dates = [d.date for d in source.get_cached_forecast()]
    assert len(dates) == 5
    assert _TODAY + datetime.timedelta(days=2) not in dates
    assert _TODAY + datetime.timedelta(days=4) not in dates


def test_hour_with_null_temperature_is_skipped(source, api):
    temps = [50.0] * 48
    temps[15] = None  # 3 PM today, inside the window
    api.queue.append(_payload(hourly_temps=temps))
    source.refresh()
    hours = [h.time.hour for h in source.get_cached_hourly()]
    assert 15 not in hours[:5]
    assert hours[:3] == [14, 16, 17]


def test_null_rain_chance_is_kept_as_none(source, api):
    precip = [10] * 48
    precip[14] = None
    api.queue.append(_payload(hourly_precip=precip))
    source.refresh()
    assert source.get_cached_hourly()[0].precipitation_probability is None


def test_all_null_forecasts_keep_previous_forecasts(source, api):
    api.queue.append(_payload())
    source.refresh()
    previous_daily, previous_hourly = source.get_cached_forecast(), source.get_cached_hourly()

    api.queue.append(_payload(daily_highs=[None] * 7, hourly_temps=[None] * 48))
    source.refresh()

    assert source.get_cached_forecast() == previous_daily
    assert source.get_cached_hourly() == previous_hourly
