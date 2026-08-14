"""Mass Readings submenu, reached from the Home screen's button 2. Purely a
navigation waypoint -- picking a reading is what the sidebar icons are for,
so there's no content here beyond the title."""

from __future__ import annotations

from PIL import Image, ImageDraw

from display import icons, renderer

# Reading-menu button mapping, top to bottom: 1=Home 2=First Reading 3=Psalm 4=Gospel
_SIDEBAR_ICONS = ["home", "book", "note", "cross"]


def render() -> Image.Image:
    image = renderer.new_canvas()
    draw = ImageDraw.Draw(image)
    canvas_width, canvas_height = renderer.CANVAS_SIZE

    content_right = icons.draw_sidebar(image, _SIDEBAR_ICONS, renderer.CANVAS_SIZE, renderer.SIDEBAR_WIDTH)
    content_width = content_right

    title_font = renderer.load_font(22, bold=True)
    subtitle_font = renderer.load_font(14)

    _draw_centered(draw, "Mass Readings", title_font, content_width, y=64)
    _draw_centered(draw, "Choose a reading ->", subtitle_font, content_width, y=100)

    return image


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, font, content_width: int, y: int) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(((content_width - text_width) // 2, y), text, font=font, fill=renderer.BLACK)


if __name__ == "__main__":
    # Quick manual preview: `python -m screens.readings_menu`
    render().save("preview_readings_menu.png")
