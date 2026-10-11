"""Helpers shared by test modules (kept out of conftest.py so tests can import
them without re-executing conftest's module stubs)."""

from __future__ import annotations


def has_ink(image, box=None) -> bool:
    """True if any pixel in `box` (left, top, right, bottom; exclusive right/bottom) is black."""
    region = image.crop(box) if box else image
    return region.convert("L").getextrema()[0] == 0
