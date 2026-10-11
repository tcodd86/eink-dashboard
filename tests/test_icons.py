"""Tests for display/icons.py (vector icons and the button sidebar)."""

from __future__ import annotations

import itertools

import pytest
from PIL import Image

from display import icons, renderer
from tests.helpers import has_ink

BOX = (20, 20, 50, 50)  # a 30px icon slot, about the size of a sidebar quadrant's
CANVAS = (70, 70)


def _render_nav(name, box=BOX):
    image = Image.new("1", CANVAS, renderer.WHITE)
    icons.draw_nav_icon(image, name, box)
    return image


def _render_weather(name, box=BOX):
    image = Image.new("1", CANVAS, renderer.WHITE)
    icons.draw_weather_icon(image, name, box)
    return image


def _outside_box_has_ink(image, box):
    left, top, right, bottom = box
    w, h = image.size
    return any(
        has_ink(image, region)
        for region in ((0, 0, w, top), (0, bottom, w, h), (0, top, left, bottom), (right, top, w, bottom))
    )


# --- every icon draws, stays in its box, and is distinguishable -------------------


@pytest.mark.parametrize("name", sorted(icons._NAV_ICONS))
def test_nav_icon_draws_inside_its_box(name):
    image = _render_nav(name)
    assert has_ink(image, BOX), f"{name} drew nothing"
    assert not _outside_box_has_ink(image, BOX), f"{name} drew outside its box"


@pytest.mark.parametrize("name", sorted(icons._WEATHER_ICONS))
def test_weather_icon_draws_inside_its_box(name):
    image = _render_weather(name)
    assert has_ink(image, BOX), f"{name} drew nothing"
    assert not _outside_box_has_ink(image, BOX), f"{name} drew outside its box"


@pytest.mark.parametrize("name", sorted(icons._NAV_ICONS))
def test_nav_icon_scales_to_a_small_slot(name):
    """Hourly-forecast rows and the Home weather row use icons at ~16px."""
    box = (5, 5, 21, 21)
    image = _render_nav(name, box)
    assert has_ink(image, box)
    assert not _outside_box_has_ink(image, box)


def test_every_nav_icon_is_visually_distinct():
    rendered = {name: _render_nav(name).tobytes() for name in icons._NAV_ICONS}
    for a, b in itertools.combinations(rendered, 2):
        assert rendered[a] != rendered[b], f"{a} and {b} render identically"


def test_every_weather_icon_is_visually_distinct():
    rendered = {name: _render_weather(name).tobytes() for name in icons._WEATHER_ICONS}
    for a, b in itertools.combinations(rendered, 2):
        assert rendered[a] != rendered[b], f"{a} and {b} render identically"


def _black_pixels(image):
    return {xy for xy in itertools.product(range(image.width), range(image.height)) if image.getpixel(xy) == 0}


def test_up_and_down_arrows_are_mirror_images():
    """Not pixel-exact: anti-aliasing rounds the two ends of the 1-bit stroke
    slightly differently. But a flipped up-arrow should overlap a down-arrow
    almost entirely, and barely overlap an unflipped one."""
    up = _render_nav("up").crop(BOX)
    down = _black_pixels(_render_nav("down").crop(BOX))
    flipped_up = _black_pixels(up.transpose(Image.Transpose.FLIP_TOP_BOTTOM))
    assert len(flipped_up ^ down) <= 0.2 * len(down)
    assert len(_black_pixels(up) & down) < 0.7 * len(down)


# --- fallbacks ---------------------------------------------------------------------


@pytest.mark.parametrize("name", [None, "no-such-icon"])
def test_unknown_or_missing_nav_icon_draws_nothing(name):
    assert not has_ink(_render_nav(name))


def test_unknown_weather_icon_falls_back_to_cloudy():
    assert _render_weather("no-such-icon").tobytes() == _render_weather("cloudy").tobytes()


# --- sidebar ----------------------------------------------------------------------


def _sidebar(icon_names):
    image = renderer.new_canvas()
    content_right = icons.draw_sidebar(image, icon_names, renderer.CANVAS_SIZE, renderer.SIDEBAR_WIDTH)
    return image, content_right


def test_sidebar_returns_left_edge_of_sidebar():
    _image, content_right = _sidebar(["home", None, None, None])
    assert content_right == renderer.CANVAS_SIZE[0] - renderer.SIDEBAR_WIDTH


def test_sidebar_draws_nothing_in_content_area():
    image, content_right = _sidebar(["calendar", "clock", "bible", "ae"])
    assert not has_ink(image, (0, 0, content_right, image.height))


def _quadrant_interior(index):
    width, height = renderer.CANVAS_SIZE
    left = width - renderer.SIDEBAR_WIDTH
    quadrant_h = height // 4
    top = index * quadrant_h
    return (left + 3, top + 3, width - 3, top + quadrant_h - 3)  # inset past divider lines


def test_sidebar_draws_each_icon_in_its_own_quadrant():
    image, _ = _sidebar(["calendar", None, "bible", None])
    assert has_ink(image, _quadrant_interior(0))
    assert not has_ink(image, _quadrant_interior(1))
    assert has_ink(image, _quadrant_interior(2))
    assert not has_ink(image, _quadrant_interior(3))


def test_sidebar_quadrant_order_matches_button_order():
    """icons[0] must land in the top quadrant (button 1), icons[3] in the bottom (button 4)."""
    top_only, _ = _sidebar(["home", None, None, None])
    bottom_only, _ = _sidebar([None, None, None, "home"])
    assert has_ink(top_only, _quadrant_interior(0)) and not has_ink(top_only, _quadrant_interior(3))
    assert has_ink(bottom_only, _quadrant_interior(3)) and not has_ink(bottom_only, _quadrant_interior(0))


def test_sidebar_draws_divider_even_when_all_slots_empty():
    image, content_right = _sidebar([None, None, None, None])
    assert has_ink(image, (content_right, 0, content_right + 1, image.height))
