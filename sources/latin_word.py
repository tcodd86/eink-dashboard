"""Fetches and caches Transparent Language's Latin Word of the Day RSS feed
(https://feeds.feedblitz.com/latin-word-of-the-day). Free, no API key, one
dated item per day.
"""

from __future__ import annotations

import dataclasses
import datetime
import html
import logging
import re
import threading
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)

_FEED_URL = "https://feeds.feedblitz.com/latin-word-of-the-day"


@dataclasses.dataclass(frozen=True)
class LatinWord:
    word: str
    short_definition: str
    part_of_speech: str
    example_latin: str
    example_english: str


def _extract_field(table_html: str, label: str) -> str:
    """Pulls a value out of the feed's embedded `<th>label</th><td>value</td>`
    HTML table (inside the RSS item's CDATA description)."""
    match = re.search(rf"<th[^>]*>{re.escape(label)}</th>\s*<td[^>]*>(.*?)</td>", table_html, re.DOTALL)
    return html.unescape(match.group(1)).strip() if match else ""


def _parse_feed(xml_text: str) -> LatinWord | None:
    root = ET.fromstring(xml_text)
    item = root.find("./channel/item")
    if item is None:
        return None

    title = (item.findtext("title") or "").strip()
    word, _, short_definition = title.partition(": ")
    if not word:
        return None

    description = item.findtext("description") or ""
    return LatinWord(
        word=word.strip(),
        short_definition=short_definition.strip(),
        part_of_speech=_extract_field(description, "Part of speech:"),
        example_latin=_extract_field(description, "Example sentence:"),
        example_english=_extract_field(description, "Sentence meaning:"),
    )


class LatinWordSource:
    """Fetches the Latin word of the day once per day and caches it in memory.

    `refresh()` does the network fetch and should be called from a background
    thread on a timer. `get_cached()` is instant and safe to call from a
    button-press handler or the render loop.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cached_date: datetime.date | None = None
        self._cached: LatinWord | None = None

    def refresh(self) -> None:
        """Fetches today's word if we don't already have it cached for today."""
        today = datetime.date.today()
        with self._lock:
            if self._cached_date == today and self._cached is not None:
                return

        try:
            response = requests.get(_FEED_URL, timeout=10)
            response.raise_for_status()
            word = _parse_feed(response.text)
        except Exception:
            logger.exception("Failed to fetch Latin word of the day; keeping last cached value")
            return

        if word is None:
            logger.warning("Latin word of the day feed had no usable item")
            return

        with self._lock:
            self._cached_date = today
            self._cached = word

    def get_cached(self) -> LatinWord | None:
        """Returns the cached word, or None if a fetch hasn't succeeded yet."""
        with self._lock:
            return self._cached
