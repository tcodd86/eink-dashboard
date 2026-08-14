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

# The citation (book/chapter/verse) is only shown on page 1 -- see
# _paginate_with_shorter_first_page. Later pages reclaim that vertical space
# for body text instead of repeating it.
_CITATION_TOP = 28
_CITATION_BOTTOM = 72
_BODY_TOP_FIRST_PAGE = 76


def _paginate_with_shorter_first_page(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    box: tuple[int, int, int, int],
    first_page_top: int,
    line_spacing: int = 4,
) -> list[list[str]]:
    """Like renderer.paginate_text, but the first page has less vertical room
    (top starts at `first_page_top` instead of `box`'s own top) to make space
    for the citation, since later pages don't repeat it and get the full box."""
    left, top, right, bottom = box
    max_width = right - left
    line_height = renderer.line_height_for(font, line_spacing)
    lines = renderer.wrap_text(draw, text, font, max_width)
    if not lines:
        return [[]]

    first_page_capacity = max(1, (bottom - first_page_top) // line_height)
    rest_capacity = max(1, (bottom - top) // line_height)

    pages = [lines[:first_page_capacity]]
    remaining = lines[first_page_capacity:]
    for i in range(0, len(remaining), rest_capacity):
        pages.append(remaining[i : i + rest_capacity])
    return pages


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

    body_box = (8, _CITATION_TOP, content_right - 8, canvas_height - 6)
    pages = _paginate_with_shorter_first_page(draw, reading.body, body_font, body_box, first_page_top=_BODY_TOP_FIRST_PAGE)
    total_pages = len(pages)
    effective_page = max(0, min(page, total_pages - 1))

    if effective_page == 0:
        # 2 lines' worth of height: combined Sunday citations (e.g. "First
        # Reading + Second Reading") routinely wrap to 2 lines and shouldn't
        # get clipped.
        renderer.draw_wrapped_text(
            draw, reading.citation, citation_font, box=(8, _CITATION_TOP, content_right - 8, _CITATION_BOTTOM)
        )
        page_body_box = (8, _BODY_TOP_FIRST_PAGE, content_right - 8, canvas_height - 6)
    else:
        page_body_box = body_box

    renderer.draw_lines(draw, pages[effective_page], body_font, page_body_box)

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
