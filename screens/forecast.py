"""7-day forecast screen, reached from the Home screen's button 1 (pressing
"Home" while already on Home was a wasted button, so it opens this instead)."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from display import icons, renderer
from sources.weather import DayForecast

# Only button 1 (back to Home) does anything on this screen -- everything
# fits on one screen, no scrolling needed -- so the other 3 quadrants show no icon.
_SIDEBAR_ICONS = ["home", None, None, None]

_TOP = 24
_ICON_SIZE = 18


def render(forecast: list[DayForecast]) -> Image.Image:
    image = renderer.new_canvas()
    draw = ImageDraw.Draw(image)
    canvas_height = renderer.CANVAS_SIZE[1]

    content_right = icons.draw_sidebar(image, _SIDEBAR_ICONS, renderer.CANVAS_SIZE, renderer.SIDEBAR_WIDTH)

    header_font = renderer.load_font(15, bold=True)
    day_font = renderer.load_font(12, bold=True)
    temp_font = renderer.load_font(12)

    draw.text((8, 4), "7-Day Forecast", font=header_font, fill=renderer.BLACK)
    draw.line((8, _TOP - 2, content_right - 8, _TOP - 2), fill=renderer.BLACK, width=1)

    if not forecast:
        renderer.draw_wrapped_text(
            draw,
            "Forecast unavailable. Check network connection -- will retry automatically.",
            temp_font,
            box=(8, _TOP + 6, content_right - 8, canvas_height - 6),
        )
        return image

    row_height = (canvas_height - _TOP - 4) / len(forecast)
    for i, day in enumerate(forecast):
        row_top = _TOP + i * row_height
        row_bottom = row_top + row_height
        if i > 0:
            draw.line((8, row_top, content_right - 8, row_top), fill=renderer.BLACK, width=1)
        _draw_row(draw, image, day, i, row_top, row_bottom, content_right, day_font, temp_font)

    return image


def _draw_row(
    draw: ImageDraw.ImageDraw,
    image: Image.Image,
    day: DayForecast,
    index: int,
    row_top: float,
    row_bottom: float,
    content_right: int,
    day_font: ImageFont.FreeTypeFont,
    temp_font: ImageFont.FreeTypeFont,
) -> None:
    label = "Today" if index == 0 else day.date.strftime("%a")
    label_y = row_top + (row_bottom - row_top - _text_height(day_font)) / 2
    draw.text((8, label_y), label, font=day_font, fill=renderer.BLACK)

    icon_y = row_top + (row_bottom - row_top - _ICON_SIZE) / 2
    icon_x = 58
    icons.draw_weather_icon(image, day.icon, (icon_x, icon_y, icon_x + _ICON_SIZE, icon_y + _ICON_SIZE))

    temp_str = f"{round(day.high)}° / {round(day.low)}°"
    temp_width = draw.textlength(temp_str, font=temp_font)
    temp_y = row_top + (row_bottom - row_top - _text_height(temp_font)) / 2
    draw.text((content_right - 8 - temp_width, temp_y), temp_str, font=temp_font, fill=renderer.BLACK)


def _text_height(font: ImageFont.FreeTypeFont) -> int:
    return font.getbbox("Ag")[3]


if __name__ == "__main__":
    # Quick manual preview: `python -m screens.forecast`
    import datetime

    sample = [
        DayForecast(datetime.date.today() + datetime.timedelta(days=i), 90 - i, 70 - i, "Sunny", icon)
        for i, icon in enumerate(["sun", "partly_cloudy", "cloudy", "rain", "thunderstorm", "snow", "fog"])
    ]
    render(sample).save("preview_forecast.png")
