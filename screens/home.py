"""The default screen: current time (to the minute), weather icon + temperature,
and the right-hand button-function sidebar."""

from __future__ import annotations

import datetime

from PIL import Image, ImageDraw

import config
from display import icons, renderer
from sources.weather import Weather

# Home-screen button mapping, top to bottom: 1=7-Day Forecast 2=Mass Readings menu
# 3=Latin Word of the Day 4=unused
_SIDEBAR_ICONS = ["calendar", "bible", "ae", None]


def render(weather: Weather | None, now: datetime.datetime | None = None) -> Image.Image:
    now = now or datetime.datetime.now()
    image = renderer.new_canvas()
    draw = ImageDraw.Draw(image)
    canvas_width, _canvas_height = renderer.CANVAS_SIZE

    content_right = icons.draw_sidebar(image, _SIDEBAR_ICONS, renderer.CANVAS_SIZE, renderer.SIDEBAR_WIDTH)
    content_width = content_right

    time_str = now.strftime(config.TIME_FORMAT).lstrip("0")
    date_str = f"{now.strftime(config.DATE_FORMAT)} {now.day}"

    # Auto-fit rather than a fixed size: DejaVu Sans (the Pi's actual runtime
    # font) renders noticeably wider than Arial (the Windows dev-preview
    # fallback) at the same point size, so a size that fits in preview can
    # overflow off-screen on real hardware.
    time_font = renderer.fit_font_to_width(draw, time_str, max_width=content_width - 16, max_size=52, bold=True, min_size=28)
    date_font = renderer.load_font(17)
    weather_font = renderer.load_font(22, bold=True)

    _draw_centered(draw, time_str, time_font, content_width, y=26)
    _draw_centered(draw, date_str, date_font, content_width, y=100)
    _draw_weather_row(image, draw, weather, weather_font, content_width, y=124, icon_size=32)

    return image


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, font, content_width: int, y: int) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(((content_width - text_width) // 2, y), text, font=font, fill=renderer.BLACK)


def _draw_weather_row(
    image: Image.Image, draw: ImageDraw.ImageDraw, weather: Weather | None, font, content_width: int, y: int, icon_size: int
) -> None:
    if weather is None:
        _draw_centered(draw, "Weather unavailable", font, content_width, y)
        return

    temp_str = f"{round(weather.temperature)}°F"
    gap = 8
    text_width = draw.textlength(temp_str, font=font)
    group_width = icon_size + gap + text_width
    start_x = (content_width - group_width) // 2

    icon_box = (start_x, y, start_x + icon_size, y + icon_size)
    icons.draw_weather_icon(image, weather.icon, icon_box)

    text_bbox = draw.textbbox((0, 0), temp_str, font=font)
    text_height = text_bbox[3] - text_bbox[1]
    text_y = y + (icon_size - text_height) // 2 - text_bbox[1]
    draw.text((start_x + icon_size + gap, text_y), temp_str, font=font, fill=renderer.BLACK)


if __name__ == "__main__":
    # Quick manual preview: `python -m screens.home`
    render(Weather(temperature=76.3, description="Clear sky", icon="sun")).save("preview_home.png")
