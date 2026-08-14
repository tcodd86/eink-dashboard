"""Latin Word of the Day screen, reached from the Home screen's button 3.

The word/part-of-speech/definition only appear on page 1 (like the
citation on a reading screen); the Latin example sentence + English
translation are paginated across as many pages as they need. Scroll
arrows (buttons 2/3) only appear in the sidebar when there's more than one
page -- button 4 is left unused here regardless (no "next" concept, unlike
the reading screens' cycle-to-next-reading).
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from display import icons, renderer
from sources.latin_word import LatinWord

_HEADER_BOTTOM = 24
_WORD_TOP = 28
_DEF_TOP = 58
_DIVIDER_Y = 96
_BODY_TOP_FIRST_PAGE = 102


def render(latin_word: LatinWord | None, page: int = 0) -> tuple[Image.Image, int, int]:
    """Returns (image, effective_page, total_pages). `effective_page` is `page`
    clamped to [0, total_pages - 1]."""
    image = renderer.new_canvas()
    draw = ImageDraw.Draw(image)
    canvas_width, canvas_height = renderer.CANVAS_SIZE
    # Fixed regardless of which icons end up in the sidebar (that only
    # affects what's drawn *inside* it, not its width) -- computed directly
    # so we don't need the sidebar drawn yet to lay out the content, since
    # which icons to show depends on the page count we compute below.
    content_right = canvas_width - renderer.SIDEBAR_WIDTH
    bottom = canvas_height - 6

    header_font = renderer.load_font(15, bold=True)
    body_font = renderer.load_font(12)

    draw.text((8, 4), "Latin Word of the Day", font=header_font, fill=renderer.BLACK)
    draw.line((8, _HEADER_BOTTOM, content_right - 8, _HEADER_BOTTOM), fill=renderer.BLACK, width=1)

    if latin_word is None:
        renderer.draw_wrapped_text(
            draw,
            "Word of the day unavailable. Check network connection -- will retry automatically.",
            body_font,
            box=(8, _WORD_TOP, content_right - 8, bottom),
        )
        icons.draw_sidebar(image, ["home", None, None, None], renderer.CANVAS_SIZE, renderer.SIDEBAR_WIDTH)
        return image, 0, 1

    parts = [p for p in (latin_word.example_latin, f"— {latin_word.example_english}" if latin_word.example_english else "") if p]
    body_text = "\n\n".join(parts)

    body_box = (8, _HEADER_BOTTOM + 6, content_right - 8, bottom)
    pages = renderer.paginate_with_shorter_first_page(draw, body_text, body_font, body_box, first_page_top=_BODY_TOP_FIRST_PAGE)
    total_pages = len(pages)
    effective_page = max(0, min(page, total_pages - 1))

    if effective_page == 0:
        # Auto-fit rather than a fixed size: word length varies day to day,
        # and a fixed size risks the same off-screen overflow the Home
        # screen's clock once had on DejaVu Sans (see screens/home.py).
        word_font = renderer.fit_font_to_width(
            draw, latin_word.word, max_width=content_right - 16, max_size=22, bold=True, min_size=14
        )
        draw.text((8, _WORD_TOP), latin_word.word, font=word_font, fill=renderer.BLACK)

        pos_and_def = f"({latin_word.part_of_speech}) {latin_word.short_definition}".strip()
        renderer.draw_wrapped_text(draw, pos_and_def, body_font, box=(8, _DEF_TOP, content_right - 8, _DIVIDER_Y - 4))

        draw.line((8, _DIVIDER_Y, content_right - 8, _DIVIDER_Y), fill=renderer.BLACK, width=1)
        page_body_box = (8, _BODY_TOP_FIRST_PAGE, content_right - 8, bottom)
    else:
        page_body_box = body_box

    renderer.draw_lines(draw, pages[effective_page], body_font, page_body_box)

    sidebar_icons = ["home", "up", "down", None] if total_pages > 1 else ["home", None, None, None]
    icons.draw_sidebar(image, sidebar_icons, renderer.CANVAS_SIZE, renderer.SIDEBAR_WIDTH)

    return image, effective_page, total_pages


if __name__ == "__main__":
    # Quick manual preview: `python -m screens.latin_word`
    sample = LatinWord(
        word="excusare",
        short_definition="to excuse, to make an excuse for",
        part_of_speech="verb",
        example_latin="Ignorantia iuris neminem excusat.",
        example_english="Ignorance of the law excuses no one.",
    )
    img, page, total = render(sample, page=0)
    print(f"page {page + 1}/{total}")
    img.save("preview_latin_word.png")
