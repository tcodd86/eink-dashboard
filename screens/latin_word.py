"""Latin Word of the Day screen, reached from the Home screen's button 3."""

from __future__ import annotations

from PIL import Image, ImageDraw

from display import icons, renderer
from sources.latin_word import LatinWord

# Latin-word-screen button mapping: only button 1 (back to Home) does
# anything -- everything is meant to fit on one screen, no scrolling needed.
_SIDEBAR_ICONS = ["home", None, None, None]

_HEADER_BOTTOM = 24
_TOP = 28


def render(latin_word: LatinWord | None) -> Image.Image:
    image = renderer.new_canvas()
    draw = ImageDraw.Draw(image)
    canvas_height = renderer.CANVAS_SIZE[1]
    bottom = canvas_height - 6

    content_right = icons.draw_sidebar(image, _SIDEBAR_ICONS, renderer.CANVAS_SIZE, renderer.SIDEBAR_WIDTH)

    header_font = renderer.load_font(15, bold=True)
    body_font = renderer.load_font(12)

    draw.text((8, 4), "Latin Word of the Day", font=header_font, fill=renderer.BLACK)
    draw.line((8, _HEADER_BOTTOM, content_right - 8, _HEADER_BOTTOM), fill=renderer.BLACK, width=1)

    if latin_word is None:
        renderer.draw_wrapped_text(
            draw,
            "Word of the day unavailable. Check network connection -- will retry automatically.",
            body_font,
            box=(8, _TOP, content_right - 8, bottom),
        )
        return image

    # Auto-fit rather than a fixed size: word length varies day to day, and a
    # fixed size risks the same off-screen overflow the Home screen's clock
    # once had on DejaVu Sans (see screens/home.py).
    word_font = renderer.fit_font_to_width(
        draw, latin_word.word, max_width=content_right - 16, max_size=22, bold=True, min_size=14
    )

    pos_and_def = f"({latin_word.part_of_speech}) {latin_word.short_definition}".strip()
    translation = f"— {latin_word.example_english}" if latin_word.example_english else ""

    # Each block is measured against the space actually left, so nothing gets
    # cut off mid-word or drawn past the bottom edge the way a fixed set of
    # guessed pixel offsets once did here.
    y = _TOP
    y = _draw_block(draw, latin_word.word, word_font, 8, content_right - 8, y, bottom, max_lines=1)
    y += 4
    y = _draw_block(draw, pos_and_def, body_font, 8, content_right - 8, y, bottom, max_lines=2)

    if y < bottom - 8:
        y += 4
        draw.line((8, y, content_right - 8, y), fill=renderer.BLACK, width=1)
        y += 8

    y = _draw_block(draw, latin_word.example_latin, body_font, 8, content_right - 8, y, bottom, max_lines=2)
    y += 4
    _draw_block(draw, translation, body_font, 8, content_right - 8, y, bottom, max_lines=2)

    return image


def _draw_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    left: int,
    right: int,
    top: int,
    bottom: int,
    max_lines: int,
) -> int:
    """Draws up to `max_lines` wrapped lines of `text` starting at `top`,
    never past `bottom`. Returns the y position just below what was drawn."""
    if not text or top >= bottom:
        return top

    line_height = renderer.line_height_for(font)
    lines = renderer.wrap_text(draw, text, font, right - left)[:max_lines]
    lines_that_fit = max(0, min(len(lines), (bottom - top) // line_height))

    y = top
    for line in lines[:lines_that_fit]:
        draw.text((left, y), line, font=font, fill=renderer.BLACK)
        y += line_height
    return y


if __name__ == "__main__":
    # Quick manual preview: `python -m screens.latin_word`
    sample = LatinWord(
        word="excusare",
        short_definition="to excuse, to make an excuse for",
        part_of_speech="verb",
        example_latin="Ignorantia iuris neminem excusat.",
        example_english="Ignorance of the law excuses no one.",
    )
    render(sample).save("preview_latin_word.png")
