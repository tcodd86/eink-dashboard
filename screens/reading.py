"""A generic, paginated screen for one of today's Mass readings.

Long readings don't fit on a 264x176 screen at a legible font size, so the
body text is split into pages; `render()` takes a requested page index and
returns the image plus the *effective* (clamped) page and total page count,
which the caller (main.py) should store back as the current page so repeated
scroll-up/scroll-down presses stay in bounds.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from display import icons, renderer
from sources.mass_readings import Reading

TITLES = {
    "first_reading": "Reading(s)",
    "psalm": "Responsorial Psalm",
    "gospel": "Gospel",
}

# Reading-screen button mapping, top to bottom: 1=Home 2=Scroll up 3=Scroll down 4=Next reading
_SIDEBAR_ICONS = ["home", "up", "down", "right"]

_BODY_TOP = 76


def render(reading: Reading | None, key: str, page: int = 0) -> tuple[Image.Image, int, int]:
    """Returns (image, effective_page, total_pages). `effective_page` is `page`
    clamped to [0, total_pages - 1]."""
    image = renderer.new_canvas()
    draw = ImageDraw.Draw(image)
    canvas_height = renderer.CANVAS_SIZE[1]

    content_right = icons.draw_sidebar(image, _SIDEBAR_ICONS, renderer.CANVAS_SIZE, renderer.SIDEBAR_WIDTH)

    header_font = renderer.load_font(16, bold=True)
    citation_font = renderer.load_font(13)
    body_font = renderer.load_font(12)
    indicator_font = renderer.load_font(11)

    title = TITLES.get(key, key)
    draw.text((8, 4), title, font=header_font, fill=renderer.BLACK)
    draw.line((8, 24, content_right - 8, 24), fill=renderer.BLACK, width=1)

    if reading is None:
        renderer.draw_wrapped_text(
            draw,
            "Readings unavailable. Check network connection -- will retry automatically.",
            body_font,
            box=(8, 32, content_right - 8, canvas_height - 6),
        )
        return image, 0, 1

    # 2 lines' worth of height: combined Sunday citations (e.g. "First Reading +
    # Second Reading") routinely wrap to 2 lines and shouldn't get clipped.
    renderer.draw_wrapped_text(draw, reading.citation, citation_font, box=(8, 28, content_right - 8, 72))

    body_box = (8, _BODY_TOP, content_right - 8, canvas_height - 6)
    pages = renderer.paginate_text(draw, reading.body, body_font, body_box)
    total_pages = len(pages)
    effective_page = max(0, min(page, total_pages - 1))
    renderer.draw_lines(draw, pages[effective_page], body_font, body_box)

    if total_pages > 1:
        indicator = f"{effective_page + 1}/{total_pages}"
        indicator_width = draw.textlength(indicator, font=indicator_font)
        draw.text((content_right - 8 - indicator_width, 6), indicator, font=indicator_font, fill=renderer.BLACK)

    return image, effective_page, total_pages


if __name__ == "__main__":
    # Quick manual preview: `python -m screens.reading`
    sample = Reading(
        heading="First Reading",
        citation="1 Kings 19:9a, 11-13a",
        body="At the mountain of God, Horeb, Elijah came to a cave where he took shelter. ",
    )
    img, page, total = render(sample, "first_reading", page=0)
    print(f"page {page + 1}/{total}")
    img.save("preview_reading.png")
