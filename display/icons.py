"""Hand-drawn vector icons (no image assets or icon fonts), so they stay crisp
on the 1-bit e-Paper display at small sizes. Every draw_* function renders
into the given (left, top, right, bottom) box.
"""

from __future__ import annotations

import math
from typing import Callable

from PIL import Image, ImageDraw

from display import renderer

Box = tuple[float, float, float, float]
DrawFn = Callable[[ImageDraw.ImageDraw, Box, int], None]

BLACK = 0
WHITE = 255

# Pillow's ImageDraw has no anti-aliasing, so thin diagonal/curved strokes
# (arrows, the "next" loop, sun rays) rasterize slightly lopsided at these
# icon sizes. Rendering each icon at a higher resolution and downsampling
# with Image.LANCZOS smooths and symmetrizes edges before they hit the
# 1-bit canvas.
_SUPERSAMPLE = 4


def _square(box: Box) -> Box:
    left, top, right, bottom = box
    size = min(right - left, bottom - top)
    cx, cy = (left + right) / 2, (top + bottom) / 2
    return (cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2)


def _render_supersampled(draw_fn: DrawFn, box: Box, width: int) -> tuple[Image.Image, int, int]:
    """Renders `draw_fn` into a box-sized bitmap via a supersampled buffer.
    Returns (bitmap, x, y) ready to `Image.paste()` onto the target canvas."""
    left, top, right, bottom = box
    w, h = max(1, round(right - left)), max(1, round(bottom - top))
    big = Image.new("L", (w * _SUPERSAMPLE, h * _SUPERSAMPLE), WHITE)
    big_draw = ImageDraw.Draw(big)
    draw_fn(big_draw, (0, 0, w * _SUPERSAMPLE, h * _SUPERSAMPLE), width * _SUPERSAMPLE)
    small = big.resize((w, h), Image.LANCZOS)
    bitmap = small.point(lambda p: 0 if p < 128 else 255).convert("1", dither=Image.NONE)
    return bitmap, round(left), round(top)


# --- Weather icons -----------------------------------------------------------


def _sun_rays(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, size: float, width: int) -> None:
    inner = r + size * 0.09
    outer = inner + size * 0.15
    for deg in range(0, 360, 45):
        a = math.radians(deg)
        draw.line(
            (cx + inner * math.cos(a), cy + inner * math.sin(a), cx + outer * math.cos(a), cy + outer * math.sin(a)),
            fill=BLACK,
            width=width,
        )


def _cloud_outline(draw: ImageDraw.ImageDraw, box: Box, width: int) -> Box:
    """Draws a cloud (rounded body + 3 bumps) filling `box`. Returns the cloud's bbox."""
    left, top, right, bottom = box
    w, h = right - left, bottom - top
    body_top = top + h * 0.46
    radius = (bottom - body_top) / 2
    draw.rounded_rectangle(
        (left + w * 0.02, body_top, right - w * 0.02, bottom), radius=radius, outline=BLACK, width=width, fill=WHITE
    )
    for bx_frac, by_frac, br_frac in ((0.28, 0.46, 0.26), (0.52, 0.28, 0.32), (0.76, 0.46, 0.24)):
        bx, by, br = left + w * bx_frac, top + h * by_frac, h * br_frac
        draw.ellipse((bx - br, by - br, bx + br, by + br), outline=BLACK, width=width, fill=WHITE)
    return (left, top, right, bottom)


def draw_sun(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    left, top, right, bottom = _square(box)
    size = right - left
    cx, cy = (left + right) / 2, (top + bottom) / 2
    r = size * 0.24
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=BLACK, width=width, fill=WHITE)
    _sun_rays(draw, cx, cy, r, size, width)


def draw_partly_cloudy(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    left, top, right, bottom = _square(box)
    size = right - left
    # Small sun peeking from the upper-left, cloud covering the lower-right 70%.
    sun_cx, sun_cy = left + size * 0.32, top + size * 0.30
    sun_r = size * 0.16
    draw.ellipse((sun_cx - sun_r, sun_cy - sun_r, sun_cx + sun_r, sun_cy + sun_r), outline=BLACK, width=width, fill=WHITE)
    _sun_rays(draw, sun_cx, sun_cy, sun_r, size * 0.7, width)
    cloud_box = (left + size * 0.18, top + size * 0.34, right, bottom)
    _cloud_outline(draw, cloud_box, width)


def draw_cloudy(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    _cloud_outline(draw, _square(box), width)


def draw_fog(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    left, top, right, bottom = _square(box)
    h = bottom - top
    for i, frac in enumerate((0.30, 0.50, 0.70)):
        y = top + h * frac
        inset = (right - left) * (0.12 if i != 1 else 0.0)
        draw.line((left + inset, y, right - inset, y), fill=BLACK, width=width)


def draw_rain(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    left, top, right, bottom = _square(box)
    w, h = right - left, bottom - top
    cloud_box = (left, top, right, top + h * 0.68)
    _, _, _, cloud_bottom = _cloud_outline(draw, cloud_box, width)
    for x_frac in (0.32, 0.52, 0.72):
        x = left + w * x_frac
        y0 = cloud_bottom - h * 0.04
        y1 = min(bottom, y0 + h * 0.28)
        draw.line((x, y0, x - w * 0.06, y1), fill=BLACK, width=width)


def draw_snow(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    left, top, right, bottom = _square(box)
    w, h = right - left, bottom - top
    cloud_box = (left, top, right, top + h * 0.68)
    _, _, _, cloud_bottom = _cloud_outline(draw, cloud_box, width)
    for x_frac in (0.32, 0.52, 0.72):
        cx = left + w * x_frac
        cy = min(bottom - h * 0.08, cloud_bottom + h * 0.14)
        r = h * 0.07
        for deg in (0, 60, 120):
            a = math.radians(deg)
            draw.line((cx - r * math.cos(a), cy - r * math.sin(a), cx + r * math.cos(a), cy + r * math.sin(a)), fill=BLACK, width=width)


def draw_thunderstorm(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    left, top, right, bottom = _square(box)
    w, h = right - left, bottom - top
    cloud_box = (left, top, right, top + h * 0.62)
    _cloud_outline(draw, cloud_box, width)
    cx = left + w * 0.52
    bolt = [
        (cx + w * 0.06, top + h * 0.56),
        (cx - w * 0.10, top + h * 0.78),
        (cx + w * 0.02, top + h * 0.78),
        (cx - w * 0.06, bottom),
        (cx + w * 0.16, top + h * 0.72),
        (cx + w * 0.04, top + h * 0.72),
    ]
    draw.polygon(bolt, fill=BLACK)


_WEATHER_ICONS = {
    "sun": draw_sun,
    "partly_cloudy": draw_partly_cloudy,
    "cloudy": draw_cloudy,
    "fog": draw_fog,
    "rain": draw_rain,
    "snow": draw_snow,
    "thunderstorm": draw_thunderstorm,
}


def draw_weather_icon(image: Image.Image, icon: str, box: Box, width: int = 2) -> None:
    handler = _WEATHER_ICONS.get(icon) or draw_cloudy
    bitmap, x, y = _render_supersampled(handler, box, width)
    image.paste(bitmap, (x, y))


# --- Navigation / button-function icons ---------------------------------------


def draw_home(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    left, top, right, bottom = _square(box)
    w, h = right - left, bottom - top
    roof_tip = (left + w * 0.5, top + h * 0.05)
    roof_left = (left + w * 0.08, top + h * 0.48)
    roof_right = (left + w * 0.92, top + h * 0.48)
    draw.line((roof_tip, roof_left), fill=BLACK, width=width)
    draw.line((roof_tip, roof_right), fill=BLACK, width=width)
    body = (left + w * 0.20, top + h * 0.46, right - w * 0.20, bottom - h * 0.05)
    draw.rectangle(body, outline=BLACK, width=width)
    door = (left + w * 0.42, top + h * 0.68, left + w * 0.58, bottom - h * 0.05)
    draw.rectangle(door, outline=BLACK, width=width)


def draw_up_arrow(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    _draw_chevron(draw, box, direction="up", width=width)


def draw_down_arrow(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    _draw_chevron(draw, box, direction="down", width=width)


def draw_right_arrow(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    """A plain right-pointing arrow, for 'go to the next reading'. Deliberately
    reuses the same stem+chevron-head language as the up/down scroll arrows
    rather than a looping/refresh-style icon, which read as 'reload' instead
    of 'advance' at this size."""
    _draw_chevron(draw, box, direction="right", width=width)


def _draw_chevron(draw: ImageDraw.ImageDraw, box: Box, direction: str, width: int) -> None:
    left, top, right, bottom = _square(box)
    w, h = right - left, bottom - top
    cx, cy = (left + right) / 2, (top + bottom) / 2

    if direction in ("up", "down"):
        tip = (cx, top + h * 0.05) if direction == "up" else (cx, bottom - h * 0.05)
        stem_end = (cx, bottom - h * 0.05) if direction == "up" else (cx, top + h * 0.05)
        head_offset = h * 0.35
        head_y = tip[1] + head_offset if direction == "up" else tip[1] - head_offset
        wing1, wing2 = (left + w * 0.20, head_y), (right - w * 0.20, head_y)
    else:
        tip = (right - w * 0.05, cy) if direction == "right" else (left + w * 0.05, cy)
        stem_end = (left + w * 0.05, cy) if direction == "right" else (right - w * 0.05, cy)
        head_offset = w * 0.35
        head_x = tip[0] - head_offset if direction == "right" else tip[0] + head_offset
        wing1, wing2 = (head_x, top + h * 0.20), (head_x, bottom - h * 0.20)

    draw.line((stem_end, tip), fill=BLACK, width=width)
    draw.line((tip, wing1), fill=BLACK, width=width)
    draw.line((tip, wing2), fill=BLACK, width=width)


def draw_calendar(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    left, top, right, bottom = _square(box)
    w, h = right - left, bottom - top
    body = (left + w * 0.08, top + h * 0.20, right - w * 0.08, bottom - h * 0.06)
    draw.rectangle(body, outline=BLACK, width=width)
    draw.line((left + w * 0.08, top + h * 0.38, right - w * 0.08, top + h * 0.38), fill=BLACK, width=width)
    draw.line((left + w * 0.30, top + h * 0.06, left + w * 0.30, top + h * 0.24), fill=BLACK, width=width)
    draw.line((right - w * 0.30, top + h * 0.06, right - w * 0.30, top + h * 0.24), fill=BLACK, width=width)


def draw_book(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    left, top, right, bottom = _square(box)
    w, h = right - left, bottom - top
    draw.rectangle((left + w * 0.10, top + h * 0.15, right - w * 0.10, bottom - h * 0.15), outline=BLACK, width=width)
    for frac in (0.35, 0.55, 0.75):
        y = top + h * frac
        draw.line((left + w * 0.22, y, right - w * 0.22, y), fill=BLACK, width=width)


def draw_note(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    left, top, right, bottom = _square(box)
    w, h = right - left, bottom - top
    head_cx, head_cy = left + w * 0.32, bottom - h * 0.22
    head_r = h * 0.16
    draw.ellipse((head_cx - head_r, head_cy - head_r, head_cx + head_r, head_cy + head_r), outline=BLACK, width=width, fill=BLACK)
    stem_x = head_cx + head_r * 0.95
    draw.line((stem_x, head_cy, stem_x, top + h * 0.12), fill=BLACK, width=width)
    draw.line((stem_x, top + h * 0.12, stem_x + w * 0.28, top + h * 0.26), fill=BLACK, width=width)


def draw_cross(draw: ImageDraw.ImageDraw, box: Box, width: int = 3) -> None:
    left, top, right, bottom = _square(box)
    w, h = right - left, bottom - top
    cx = (left + right) / 2
    draw.line((cx, top + h * 0.08, cx, bottom - h * 0.08), fill=BLACK, width=width)
    draw.line((left + w * 0.20, top + h * 0.36, right - w * 0.20, top + h * 0.36), fill=BLACK, width=width)


def draw_bible(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    """A closed book with a cross on the cover -- the top-level "Mass Readings"
    menu icon. Distinct from draw_book's open book (used one level down, for
    First Reading specifically) so the two don't read as the same thing."""
    left, top, right, bottom = _square(box)
    w, h = right - left, bottom - top
    cover = (left + w * 0.12, top + h * 0.10, right - w * 0.12, bottom - h * 0.10)
    draw.rectangle(cover, outline=BLACK, width=width)
    spine_x = cover[0] + (cover[2] - cover[0]) * 0.16
    draw.line((spine_x, cover[1], spine_x, cover[3]), fill=BLACK, width=width)
    cover_w, cover_h = cover[2] - spine_x, cover[3] - cover[1]
    cross_box = (spine_x + cover_w * 0.15, cover[1] + cover_h * 0.12, cover[2] - cover_w * 0.15, cover[3] - cover_h * 0.12)
    draw_cross(draw, cross_box, width=max(1, width - 1))


def draw_ae_ligature(draw: ImageDraw.ImageDraw, box: Box, width: int = 2) -> None:
    """AE, the Latin digraph (as in Caesar, praesidium) -- the Latin Word of
    the Day icon. Rendered as actual text (DejaVu Sans includes AE) rather
    than hand-drawn vector lines, since letterforms don't read cleanly as
    tiny hand-drawn shapes the way geometric icons do."""
    left, top, right, bottom = box
    h = bottom - top
    font = renderer.load_font(int(h * 0.85), bold=True)
    text = "Æ"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cx, cy = (left + right) / 2, (top + bottom) / 2
    draw.text((cx - text_w / 2 - bbox[0], cy - text_h / 2 - bbox[1]), text, font=font, fill=BLACK)


_NAV_ICONS = {
    "home": draw_home,
    "up": draw_up_arrow,
    "down": draw_down_arrow,
    "right": draw_right_arrow,
    "book": draw_book,
    "note": draw_note,
    "cross": draw_cross,
    "calendar": draw_calendar,
    "bible": draw_bible,
    "ae": draw_ae_ligature,
}


def draw_nav_icon(image: Image.Image, icon: str, box: Box, width: int = 2) -> None:
    handler = _NAV_ICONS.get(icon)
    if handler is None:
        return
    bitmap, x, y = _render_supersampled(handler, box, width)
    image.paste(bitmap, (x, y))


def draw_sidebar(
    image: Image.Image,
    icons: list[str],
    canvas_size: tuple[int, int],
    sidebar_width: int,
) -> int:
    """Draws a right-hand sidebar split into `len(icons)` equal-height quadrants
    (icons[0] = button1/top, ...), one nav icon centered in each. Returns the
    x-coordinate where the sidebar begins, i.e. the right edge of the content area.
    """
    draw = ImageDraw.Draw(image)
    width, height = canvas_size
    sidebar_left = width - sidebar_width
    draw.line((sidebar_left, 0, sidebar_left, height), fill=BLACK, width=1)

    quadrant_h = height / len(icons)
    padding = sidebar_width * 0.16
    for i, icon in enumerate(icons):
        qtop, qbottom = i * quadrant_h, (i + 1) * quadrant_h
        if i > 0:
            draw.line((sidebar_left, qtop, width, qtop), fill=BLACK, width=1)
        icon_box = (sidebar_left + padding, qtop + padding, width - padding, qbottom - padding)
        draw_nav_icon(image, icon, icon_box)

    return sidebar_left
