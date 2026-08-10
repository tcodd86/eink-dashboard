"""Hardware-independent screen composition.

Everything here builds plain PIL `Image` objects and knows nothing about SPI,
GPIO, or the Waveshare driver. That makes it possible to unit-test/preview
screens on any machine (see `screens/*.py`'s `if __name__ == "__main__"`
blocks) and keeps the hardware driver code in `display/epd_driver/` the only
Pi-specific part of the display pipeline.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config

# Landscape canvas: (EPD_HEIGHT, EPD_WIDTH) matches Waveshare's own "Horizontal
# image" convention for this panel (native driver orientation is portrait).
CANVAS_SIZE = (config.EPD_HEIGHT, config.EPD_WIDTH)

WHITE = 255
BLACK = 0

# Right-hand button-function sidebar, split into 4 equal quadrants (one per
# physical button). 44px matches CANVAS_SIZE height (176) / 4 exactly.
SIDEBAR_WIDTH = 44

# DejaVu Sans ships by default on Raspberry Pi OS (`fonts-dejavu-core`).
# The Windows Arial paths are only ever hit during local dev/preview.
_REGULAR_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_BOLD_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

_font_cache: dict[tuple[bool, int], ImageFont.FreeTypeFont] = {}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Loads (and caches) a font at the given point size, falling back through
    known font locations, and finally to PIL's built-in default font."""
    key = (bold, size)
    if key in _font_cache:
        return _font_cache[key]

    candidates = _BOLD_FONT_CANDIDATES if bold else _REGULAR_FONT_CANDIDATES
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None
    for path in candidates:
        if Path(path).exists():
            font = ImageFont.truetype(path, size)
            break

    if font is None:
        font = ImageFont.load_default(size=size)

    _font_cache[key] = font
    return font


def fit_font_to_width(
    draw: ImageDraw.ImageDraw, text: str, max_width: int, max_size: int, bold: bool = False, min_size: int = 10
) -> ImageFont.FreeTypeFont:
    """Returns the largest font (from `max_size` down to `min_size`) at which
    `text` fits within `max_width` px.

    Font metrics vary between the DejaVu Sans used on the Pi and the Arial
    fallback used for local/Windows preview rendering (DejaVu runs wider per
    point size), so a size tuned against one can silently overflow on the
    other. Auto-fitting avoids having to hand-pick a size that "should" fit.
    """
    size = max_size
    while size > min_size:
        font = load_font(size, bold=bold)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 1
    return load_font(min_size, bold=bold)


def new_canvas() -> Image.Image:
    """Returns a blank white landscape canvas sized for this panel."""
    return Image.new("1", CANVAS_SIZE, WHITE)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wraps `text` (may contain existing newlines/paragraphs) to fit `max_width` px."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    box: tuple[int, int, int, int],
    line_spacing: int = 4,
    fill: int = BLACK,
) -> None:
    """Draws word-wrapped text inside `box` (left, top, right, bottom), clipping
    (silently dropping) any lines that don't fit vertically. Intended for short
    fixed content (e.g. a citation) where clipping is acceptable; for long
    content that should be readable in full, use `paginate_text` instead."""
    left, top, right, bottom = box
    max_width = right - left
    line_height = font.getbbox("Ag")[3] + line_spacing

    y = top
    for line in wrap_text(draw, text, font, max_width):
        if y + line_height > bottom:
            break
        draw.text((left, y), line, font=font, fill=fill)
        y += line_height


def line_height_for(font: ImageFont.FreeTypeFont, line_spacing: int = 4) -> int:
    """Pixel height (including inter-line spacing) of one line in `font`."""
    return font.getbbox("Ag")[3] + line_spacing


def paginate_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    box: tuple[int, int, int, int],
    line_spacing: int = 4,
) -> list[list[str]]:
    """Word-wraps `text` to fit `box`'s width, then splits the wrapped lines into
    pages, each holding as many lines as fit in `box`'s height. Always returns
    at least one (possibly empty) page."""
    left, top, right, bottom = box
    max_width = right - left
    line_height = line_height_for(font, line_spacing)
    lines_per_page = max(1, (bottom - top) // line_height)

    lines = wrap_text(draw, text, font, max_width)
    pages = [lines[i : i + lines_per_page] for i in range(0, len(lines), lines_per_page)]
    return pages or [[]]


def draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    box: tuple[int, int, int, int],
    line_spacing: int = 4,
    fill: int = BLACK,
) -> None:
    """Draws pre-wrapped `lines` (e.g. one page from `paginate_text`) starting at the top-left of `box`."""
    left, top, _right, _bottom = box
    line_height = line_height_for(font, line_spacing)
    y = top
    for line in lines:
        draw.text((left, y), line, font=font, fill=fill)
        y += line_height
