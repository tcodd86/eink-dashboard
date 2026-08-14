"""Dev-only helper for previewing screen layouts without Pi hardware.

Renders each screen to a 3x-upscaled PNG using live weather data and
whatever Mass readings are available (falls back to a fixed sample if
USCCB is unreachable/blocking). Not used by the deployed app on the Pi --
just a design-iteration tool.

Usage: .devvenv/Scripts/python.exe preview_screens.py
"""

from __future__ import annotations

from PIL import Image

from screens import forecast, home, hourly_forecast, reading, readings_menu
from screens import latin_word as latin_word_screen
from sources.latin_word import LatinWordSource
from sources.mass_readings import MassReadingsSource, Reading
from sources.weather import WeatherSource

import config

SCALE = 3

_FALLBACK_READINGS = {
    "first_reading": Reading(
        heading="First Reading",
        citation="1 Kings 19:9a, 11-13a",
        body=(
            "At the mountain of God, Horeb, Elijah came to a cave where he took "
            "shelter. Then the LORD said to him, “Go outside and stand on the "
            "mountain before the LORD; the LORD will be passing by.” A strong and "
            "heavy wind was rending the mountains and crushing rocks before the "
            "LORD— but the LORD was not in the wind. After the wind there was an "
            "earthquake— but the LORD was not in the earthquake."
        ),
    ),
    "psalm": Reading(
        heading="Responsorial Psalm",
        citation="Psalms 85:9, 10, 11-12, 13-14",
        body=(
            "R. Lord, let us see your kindness, and grant us your salvation. "
            "I will hear what God proclaims; the LORD—for he proclaims peace."
        ),
    ),
    "gospel": Reading(
        heading="Gospel",
        citation="Matthew 14:22-33",
        body=(
            "After he had fed the people, Jesus made the disciples get into a boat "
            "and precede him to the other side, while he dismissed the crowds. "
            "After doing so, he went up on the mountain by himself to pray."
        ),
    ),
}


def save_preview(img: Image.Image, path: str) -> None:
    img.convert("L").resize((img.width * SCALE, img.height * SCALE), Image.NEAREST).save(path)


def main() -> None:
    ws = WeatherSource(config.LATITUDE, config.LONGITUDE, config.TEMP_UNIT)
    ws.refresh()
    weather = ws.get_cached()
    print("weather:", weather)

    mrs = MassReadingsSource()
    mrs.refresh()

    save_preview(home.render(weather), "preview_home.png")
    save_preview(forecast.render(ws.get_cached_forecast()), "preview_forecast.png")
    save_preview(readings_menu.render(), "preview_readings_menu.png")

    hourly_img, hourly_page, hourly_total = hourly_forecast.render(ws.get_cached_hourly())
    print(f"hourly forecast page {hourly_page + 1}/{hourly_total}")
    save_preview(hourly_img, "preview_hourly_forecast.png")

    lws = LatinWordSource()
    lws.refresh()
    latin_word = lws.get_cached()
    print("latin word:", latin_word)
    lw_img, lw_page, lw_total = latin_word_screen.render(latin_word)
    print(f"latin word page {lw_page + 1}/{lw_total}")
    save_preview(lw_img, "preview_latin_word.png")

    for key in config.READING_KEYS:
        live = mrs.get_cached(key)
        used = live if live is not None else _FALLBACK_READINGS[key]
        source = "live" if live is not None else "fallback (USCCB unreachable)"
        print(f"{key}: using {source} data")
        img, page, total = reading.render(used, key, page=0)
        save_preview(img, f"preview_{key}.png")

    save_preview(reading.render(None, "gospel")[0], "preview_reading_unavailable.png")
    print("done")


if __name__ == "__main__":
    main()
