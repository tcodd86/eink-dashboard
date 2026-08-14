"""Fetches and caches current weather from Open-Meteo (no API key required)."""

from __future__ import annotations

import dataclasses
import datetime
import logging
import threading

import requests

logger = logging.getLogger(__name__)

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# https://open-meteo.com/en/docs -> WMO Weather interpretation codes.
# `icon` is one of the keys handled by display/icons.py:draw_weather_icon.
_WEATHER_CODES = {
    0: ("Clear sky", "sun"),
    1: ("Mostly clear", "sun"),
    2: ("Partly cloudy", "partly_cloudy"),
    3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"),
    48: ("Freezing fog", "fog"),
    51: ("Light drizzle", "rain"),
    53: ("Drizzle", "rain"),
    55: ("Heavy drizzle", "rain"),
    56: ("Light freezing drizzle", "rain"),
    57: ("Freezing drizzle", "rain"),
    61: ("Light rain", "rain"),
    63: ("Rain", "rain"),
    65: ("Heavy rain", "rain"),
    66: ("Light freezing rain", "rain"),
    67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"),
    73: ("Snow", "snow"),
    75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"),
    80: ("Light rain showers", "rain"),
    81: ("Rain showers", "rain"),
    82: ("Violent rain showers", "rain"),
    85: ("Light snow showers", "snow"),
    86: ("Heavy snow showers", "snow"),
    95: ("Thunderstorm", "thunderstorm"),
    96: ("Thunderstorm w/ hail", "thunderstorm"),
    99: ("Thunderstorm w/ heavy hail", "thunderstorm"),
}
_DEFAULT_ICON = "cloudy"


@dataclasses.dataclass(frozen=True)
class Weather:
    temperature: float
    description: str
    icon: str


@dataclasses.dataclass(frozen=True)
class DayForecast:
    date: datetime.date
    high: float
    low: float
    description: str
    icon: str


@dataclasses.dataclass(frozen=True)
class HourForecast:
    time: datetime.datetime
    temperature: float
    description: str
    icon: str
    precipitation_probability: int  # percent, 0-100


# How many hours of hourly forecast to keep, starting from the current hour.
_HOURLY_WINDOW = 24
# Fetched from the API: must cover >= _HOURLY_WINDOW hours past the *start of
# today* (not "now"), since Open-Meteo's hourly response always starts at
# local midnight -- 48h guarantees a full 24h window regardless of what hour
# it currently is.
_HOURLY_FETCH_HOURS = 48


class WeatherSource:
    """Polls Open-Meteo for current weather, a 7-day forecast, and a 24-hour
    forecast, and caches the last good reading of each.

    `refresh()` does the network call and should be called from a background
    thread on a timer. `get_cached()` / `get_cached_forecast()` /
    `get_cached_hourly()` are instant and safe to call from a button-press
    handler or the render loop.
    """

    def __init__(self, latitude: float, longitude: float, temp_unit: str = "fahrenheit") -> None:
        self._latitude = latitude
        self._longitude = longitude
        self._temp_unit = temp_unit
        self._lock = threading.Lock()
        self._cached: Weather | None = None
        self._cached_forecast: list[DayForecast] = []
        self._cached_hourly: list[HourForecast] = []

    def refresh(self) -> None:
        """Fetches fresh weather + forecasts. On failure, logs and keeps the last cached values."""
        try:
            weather, forecast, hourly = self._fetch()
        except Exception:
            logger.exception("Failed to fetch weather; keeping last cached value")
            return
        with self._lock:
            self._cached = weather
            self._cached_forecast = forecast
            self._cached_hourly = hourly

    def get_cached(self) -> Weather | None:
        """Returns the last successfully fetched current weather, or None if a fetch hasn't succeeded yet."""
        with self._lock:
            return self._cached

    def get_cached_forecast(self) -> list[DayForecast]:
        """Returns the last successfully fetched 7-day forecast (today first), or [] if none yet."""
        with self._lock:
            return self._cached_forecast

    def get_cached_hourly(self) -> list[HourForecast]:
        """Returns the last successfully fetched hourly forecast (current hour first), or [] if none yet."""
        with self._lock:
            return self._cached_hourly

    def _fetch(self) -> tuple[Weather, list[DayForecast], list[HourForecast]]:
        response = requests.get(
            _FORECAST_URL,
            params={
                "latitude": self._latitude,
                "longitude": self._longitude,
                "current": "temperature_2m,weather_code",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "hourly": "temperature_2m,weather_code,precipitation_probability",
                "temperature_unit": self._temp_unit,
                "timezone": "auto",
                "forecast_days": 7,
                "forecast_hours": _HOURLY_FETCH_HOURS,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        current = data["current"]
        code = current["weather_code"]
        description, icon = _WEATHER_CODES.get(code, (f"Weather code {code}", _DEFAULT_ICON))
        weather = Weather(temperature=current["temperature_2m"], description=description, icon=icon)

        daily = data["daily"]
        forecast = []
        for i, date_str in enumerate(daily["time"]):
            day_code = daily["weather_code"][i]
            day_description, day_icon = _WEATHER_CODES.get(day_code, (f"Weather code {day_code}", _DEFAULT_ICON))
            forecast.append(
                DayForecast(
                    date=datetime.date.fromisoformat(date_str),
                    high=daily["temperature_2m_max"][i],
                    low=daily["temperature_2m_min"][i],
                    description=day_description,
                    icon=day_icon,
                )
            )

        hourly_data = data["hourly"]
        current_hour = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
        hourly = []
        for i, time_str in enumerate(hourly_data["time"]):
            hour_time = datetime.datetime.fromisoformat(time_str)
            if hour_time < current_hour:
                continue
            hour_code = hourly_data["weather_code"][i]
            hour_description, hour_icon = _WEATHER_CODES.get(hour_code, (f"Weather code {hour_code}", _DEFAULT_ICON))
            hourly.append(
                HourForecast(
                    time=hour_time,
                    temperature=hourly_data["temperature_2m"][i],
                    description=hour_description,
                    icon=hour_icon,
                    precipitation_probability=hourly_data["precipitation_probability"][i],
                )
            )
            if len(hourly) >= _HOURLY_WINDOW:
                break

        return weather, forecast, hourly
