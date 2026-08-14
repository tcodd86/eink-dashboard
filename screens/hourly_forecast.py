"""Hourly forecast screen, reached from the Home screen's button 2. Shows
the next 24 hours starting with the current hour, one row each: time,
condition icon, temperature, chance of rain. Paginated with scroll arrows
since 24 rows don't fit on one screen.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from display import icons, renderer
from sources.weather import HourForecast

_TOP = 24
_ICON_SIZE = 16
_ROWS_PER_PAGE = 6

_ICON_X = 50
_TEMP_X = 74


def render(hourly: list[HourForecast], page: int = 0) -> tuple[Image.Image, int, int]:
    """Returns (image, effective_page, total_pages). `effective_page` is `page`
    clamped to [0, total_pages - 1]."""
    image = renderer.new_canvas()
    draw = ImageDraw.Draw(image)
    canvas_width, canvas_height = renderer.CANVAS_SIZE
    content_right = canvas_width - renderer.SIDEBAR_WIDTH

    header_font = renderer.load_font(15, bold=True)
    row_font = renderer.load_font(12, bold=True)
    data_font = renderer.load_font(12)

    draw.text((8, 4), "Hourly Forecast", font=header_font, fill=renderer.BLACK)
    draw.line((8, _TOP - 2, content_right - 8, _TOP - 2), fill=renderer.BLACK, width=1)

    if not hourly:
        renderer.draw_wrapped_text(
            draw,
            "Forecast unavailable. Check network connection -- will retry automatically.",
            data_font,
            box=(8, _TOP + 6, content_right - 8, canvas_height - 6),
        )
        icons.draw_sidebar(image, ["home", None, None, None], renderer.CANVAS_SIZE, renderer.SIDEBAR_WIDTH)
        return image, 0, 1

    total_pages = max(1, (len(hourly) + _ROWS_PER_PAGE - 1) // _ROWS_PER_PAGE)
    effective_page = max(0, min(page, total_pages - 1))

    start = effective_page * _ROWS_PER_PAGE
    page_items = hourly[start : start + _ROWS_PER_PAGE]

    row_height = (canvas_height - _TOP - 4) / _ROWS_PER_PAGE
    for i, hour in enumerate(page_items):
        row_top = _TOP + i * row_height
        row_bottom = row_top + row_height
        if i > 0:
            draw.line((8, row_top, content_right - 8, row_top), fill=renderer.BLACK, width=1)
        _draw_row(draw, image, hour, start + i, row_top, row_bottom, content_right, row_font, data_font)

    sidebar_icons = ["home", "up", "down", None] if total_pages > 1 else ["home", None, None, None]
    icons.draw_sidebar(image, sidebar_icons, renderer.CANVAS_SIZE, renderer.SIDEBAR_WIDTH)

    return image, effective_page, total_pages


def _draw_row(
    draw: ImageDraw.ImageDraw,
    image: Image.Image,
    hour: HourForecast,
    index: int,
    row_top: float,
    row_bottom: float,
    content_right: int,
    row_font: ImageFont.FreeTypeFont,
    data_font: ImageFont.FreeTypeFont,
) -> None:
    label = "Now" if index == 0 else hour.time.strftime("%I %p").lstrip("0")
    label_y = row_top + (row_bottom - row_top - _text_height(row_font)) / 2
    draw.text((8, label_y), label, font=row_font, fill=renderer.BLACK)

    icon_y = row_top + (row_bottom - row_top - _ICON_SIZE) / 2
    icons.draw_weather_icon(image, hour.icon, (_ICON_X, icon_y, _ICON_X + _ICON_SIZE, icon_y + _ICON_SIZE))

    temp_str = f"{round(hour.temperature)}°"
    temp_y = row_top + (row_bottom - row_top - _text_height(data_font)) / 2
    draw.text((_TEMP_X, temp_y), temp_str, font=data_font, fill=renderer.BLACK)

    precip_str = f"{hour.precipitation_probability}%"
    precip_width = draw.textlength(precip_str, font=data_font)
    precip_y = row_top + (row_bottom - row_top - _text_height(data_font)) / 2
    draw.text((content_right - 8 - precip_width, precip_y), precip_str, font=data_font, fill=renderer.BLACK)


def _text_height(font: ImageFont.FreeTypeFont) -> int:
    return font.getbbox("Ag")[3]


if __name__ == "__main__":
    # Quick manual preview: `python -m screens.hourly_forecast`
    import datetime

    now = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
    sample = [
        HourForecast(now + datetime.timedelta(hours=i), 90 - i, "Sunny", icon, precip)
        for i, (icon, precip) in enumerate(
            [("sun", 0), ("sun", 5), ("partly_cloudy", 10), ("cloudy", 20), ("rain", 60), ("rain", 80)] * 4
        )
    ]
    img, page, total = render(sample, page=0)
    print(f"page {page + 1}/{total}")
    img.save("preview_hourly_forecast.png")
