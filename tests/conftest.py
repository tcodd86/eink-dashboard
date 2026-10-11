"""Shared test setup.

The real app imports Pi-only modules at import time (gpiozero, and the
vendored Waveshare driver, which opens SPI/GPIO the moment it's imported),
plus the gitignored config_local.py. Stand-ins for all three are installed
into sys.modules here, before any test module imports app code, so the whole
suite runs on any machine with no hardware, no network, and no personal
location file.
"""

from __future__ import annotations

import sys
import types

from PIL import ImageDraw

# --- config_local.py (gitignored; holds the real location) ------------------
_config_local = types.ModuleType("config_local")
_config_local.LATITUDE = 40.0
_config_local.LONGITUDE = -95.0
sys.modules["config_local"] = _config_local


# --- gpiozero ------------------------------------------------------------------
class FakeButton:
    instances: list[FakeButton] = []

    def __init__(self, pin, bounce_time=None):
        self.pin = pin
        self.bounce_time = bounce_time
        self.when_pressed = None
        FakeButton.instances.append(self)


_gpiozero = types.ModuleType("gpiozero")
_gpiozero.Button = FakeButton
sys.modules["gpiozero"] = _gpiozero


# --- Waveshare epd2in7 driver ----------------------------------------------------
class FakeEPD:
    width = 176
    height = 264

    def __init__(self):
        self.displayed = []  # every buffer passed to display(), in order
        self.cleared = 0
        self.slept = False

    def init(self):
        return 0

    def Clear(self):
        self.cleared += 1

    def getbuffer(self, image):
        # The real driver packs bits into a bytearray; returning the image
        # itself lets tests inspect exactly what would have been shown.
        return image.copy()

    def display(self, buffer):
        self.displayed.append(buffer)

    def sleep(self):
        self.slept = True


import display.epd_driver  # noqa: E402  (real, empty package __init__)

_epd2in7 = types.ModuleType("display.epd_driver.epd2in7")
_epd2in7.EPD = FakeEPD
sys.modules["display.epd_driver.epd2in7"] = _epd2in7
display.epd_driver.epd2in7 = _epd2in7


# --- shared helpers ------------------------------------------------------------
import pytest  # noqa: E402


@pytest.fixture
def drawn_text(monkeypatch):
    """Records every string drawn with ImageDraw.text during the test, in order."""
    recorded: list[str] = []
    original = ImageDraw.ImageDraw.text

    def recording_text(self, xy, text, *args, **kwargs):
        recorded.append(text)
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", recording_text)
    return recorded


@pytest.fixture
def sidebar_icons(monkeypatch):
    """Records the icon list each screen asks the sidebar to show, without drawing it
    -- so the sidebar area stays blank, which tests use to detect content bleeding
    into it."""
    from display import icons, renderer

    class SidebarCalls(list):
        content_right = renderer.CANVAS_SIZE[0] - renderer.SIDEBAR_WIDTH

    calls = SidebarCalls()

    def fake_draw_sidebar(image, icon_names, canvas_size, sidebar_width):
        calls.append(list(icon_names))
        return canvas_size[0] - sidebar_width

    monkeypatch.setattr(icons, "draw_sidebar", fake_draw_sidebar)
    return calls
