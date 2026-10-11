"""Tests for display/renderer.py (canvas, fonts, wrapping, pagination, auto-fit).

Assertions are relative to whichever font is actually loaded (DejaVu on the
Pi, Arial on Windows, PIL's default elsewhere) rather than exact pixel
widths, since those differ between machines.
"""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from display import renderer
from tests.helpers import has_ink

LOREM = (
    "At the mountain of God, Horeb, Elijah came to a cave where he took shelter. Then the "
    "LORD said to him, Go outside and stand on the mountain before the LORD; the LORD will "
    "be passing by. A strong and heavy wind was rending the mountains and crushing rocks."
)


@pytest.fixture
def draw():
    return ImageDraw.Draw(Image.new("1", renderer.CANVAS_SIZE, renderer.WHITE))


@pytest.fixture
def font():
    return renderer.load_font(12)


# --- canvas and fonts -------------------------------------------------------------


def test_canvas_is_landscape_1bit_and_blank():
    canvas = renderer.new_canvas()
    assert canvas.mode == "1"
    assert canvas.size == (264, 176) == renderer.CANVAS_SIZE
    assert not has_ink(canvas)


def test_sidebar_splits_evenly_into_four_button_quadrants():
    assert renderer.CANVAS_SIZE[1] % 4 == 0
    assert renderer.SIDEBAR_WIDTH * 4 == renderer.CANVAS_SIZE[1]


def test_fonts_are_cached():
    assert renderer.load_font(15) is renderer.load_font(15)
    assert renderer.load_font(15, bold=True) is renderer.load_font(15, bold=True)
    assert renderer.load_font(15) is not renderer.load_font(15, bold=True)


def test_larger_font_renders_wider(draw):
    assert draw.textlength("Gospel", font=renderer.load_font(24)) > draw.textlength("Gospel", font=renderer.load_font(10))


def test_line_height_includes_spacing(font):
    assert renderer.line_height_for(font, line_spacing=10) == renderer.line_height_for(font, line_spacing=0) + 10
    assert renderer.line_height_for(font, line_spacing=0) > 0


# --- wrapping ---------------------------------------------------------------------


@pytest.mark.parametrize("width", [60, 120, 204])
def test_wrapped_lines_fit_and_preserve_every_word(draw, font, width):
    lines = renderer.wrap_text(draw, LOREM, font, width)
    assert all(draw.textlength(line, font=font) <= width for line in lines)
    assert " ".join(lines).split() == LOREM.split()


def test_narrower_width_produces_more_lines(draw, font):
    assert len(renderer.wrap_text(draw, LOREM, font, 80)) > len(renderer.wrap_text(draw, LOREM, font, 200))


def test_existing_newlines_and_blank_lines_are_preserved(draw, font):
    lines = renderer.wrap_text(draw, "First paragraph.\n\nSecond paragraph.", font, 204)
    assert lines == ["First paragraph.", "", "Second paragraph."]


def test_word_longer_than_width_gets_its_own_line_instead_of_looping(draw, font):
    lines = renderer.wrap_text(draw, "a constantinopolitanensibus b", font, 30)
    assert lines == ["a", "constantinopolitanensibus", "b"]


def test_empty_text_wraps_to_one_empty_line(draw, font):
    assert renderer.wrap_text(draw, "", font, 204) == [""]


# --- pagination -------------------------------------------------------------------


def test_paginate_text_respects_page_capacity_and_keeps_order(draw, font):
    box = (8, 30, 212, 170)
    pages = renderer.paginate_text(draw, LOREM * 3, font, box)
    capacity = (box[3] - box[1]) // renderer.line_height_for(font)
    assert len(pages) > 1
    assert all(len(page) <= capacity for page in pages)
    assert [line for page in pages for line in page] == renderer.wrap_text(draw, LOREM * 3, font, box[2] - box[0])


def test_paginate_text_always_returns_a_page(draw, font):
    assert len(renderer.paginate_text(draw, "", font, (8, 30, 212, 170))) == 1


def test_shorter_first_page_capacities(draw, font):
    box = (8, 30, 212, 170)
    first_page_top = 100
    pages = renderer.paginate_with_shorter_first_page(draw, LOREM * 3, font, box, first_page_top=first_page_top)
    line_height = renderer.line_height_for(font)
    assert len(pages[0]) == (box[3] - first_page_top) // line_height
    assert all(len(page) <= (box[3] - box[1]) // line_height for page in pages[1:])
    assert len(pages[1]) > len(pages[0])  # later pages reclaim the header space
    assert [line for page in pages for line in page] == renderer.wrap_text(draw, LOREM * 3, font, box[2] - box[0])


def test_shorter_first_page_short_text_is_one_page(draw, font):
    assert len(renderer.paginate_with_shorter_first_page(draw, "Short.", font, (8, 30, 212, 170), 100)) == 1


def test_shorter_first_page_always_fits_at_least_one_line(draw, font):
    pages = renderer.paginate_with_shorter_first_page(draw, LOREM, font, (8, 30, 212, 170), first_page_top=169)
    assert len(pages[0]) == 1


# --- auto-fit ---------------------------------------------------------------------


def test_fit_font_keeps_max_size_when_text_already_fits(draw):
    assert renderer.fit_font_to_width(draw, "9:05 AM", max_width=204, max_size=30, bold=True).size == 30


def test_fit_font_shrinks_until_text_fits(draw):
    font = renderer.fit_font_to_width(draw, "12:59 PM", max_width=100, max_size=52, bold=True, min_size=8)
    assert font.size < 52
    assert draw.textlength("12:59 PM", font=font) <= 100
    larger = renderer.load_font(font.size + 1, bold=True)
    assert draw.textlength("12:59 PM", font=larger) > 100  # it's the largest size that fits


def test_fit_font_stops_at_min_size_when_nothing_fits(draw):
    assert renderer.fit_font_to_width(draw, "x" * 200, max_width=20, max_size=40, min_size=14).size == 14


# --- drawing ----------------------------------------------------------------------


def test_draw_wrapped_text_never_draws_below_its_box():
    image = renderer.new_canvas()
    box = (8, 30, 212, 60)  # room for ~1 line
    renderer.draw_wrapped_text(ImageDraw.Draw(image), LOREM, renderer.load_font(12), box)
    assert has_ink(image, box)
    assert not has_ink(image, (0, box[3], image.width, image.height))


def test_draw_lines_draws_one_row_per_line_inside_box(font):
    image = renderer.new_canvas()
    box = (8, 30, 212, 170)
    renderer.draw_lines(ImageDraw.Draw(image), ["first", "second"], font, box)
    line_height = renderer.line_height_for(font)
    assert has_ink(image, (box[0], box[1], box[2], box[1] + line_height))
    assert has_ink(image, (box[0], box[1] + line_height, box[2], box[1] + 2 * line_height))
    assert not has_ink(image, (0, box[1] + 2 * line_height, image.width, image.height))
