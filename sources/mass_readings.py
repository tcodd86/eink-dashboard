"""Fetches and caches today's Catholic Mass readings via the `catholic_mass_readings` package.

That package scrapes https://bible.usccb.org/bible/readings/ and returns full reading
text (not just citations). A weekday Mass has 3 readings (First Reading, Responsorial
Psalm, Gospel); Sundays/solemnities add an extra "Second Reading" between the Psalm and
Gospel. Since we only have 3 content buttons, that extra reading is appended onto the
"first_reading" bucket below the First Reading rather than dropped.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import logging
import threading

from catholic_mass_readings import USCCB, models

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class Reading:
    heading: str
    citation: str
    body: str


def _combine_reading_sections(sections: list[models.Section]) -> Reading:
    """Combines one or more same-kind sections (e.g. First + Second Reading) into one Reading."""
    heading = " & ".join(s.display_header for s in sections)
    citation = " | ".join("; ".join(r.header for r in s.readings) for s in sections)

    if len(sections) == 1:
        body = "\n\n".join(r.text for r in sections[0].readings)
    else:
        parts = []
        for s in sections:
            s_citation = "; ".join(r.header for r in s.readings)
            s_text = "\n\n".join(r.text for r in s.readings)
            parts.append(f"{s.display_header} ({s_citation})\n\n{s_text}")
        body = "\n\n---\n\n".join(parts)

    return Reading(heading=heading, citation=citation, body=body)


def _extract_readings(mass: models.Mass) -> dict[str, Reading]:
    reading_sections = [s for s in mass.sections if s.type_ == models.SectionType.READING]
    psalm_section = next((s for s in mass.sections if s.type_ == models.SectionType.PSALM), None)
    gospel_section = next((s for s in mass.sections if s.type_.is_gospel), None)

    result: dict[str, Reading] = {}
    if reading_sections:
        result["first_reading"] = _combine_reading_sections(reading_sections)
    if psalm_section:
        result["psalm"] = _combine_reading_sections([psalm_section])
    if gospel_section:
        result["gospel"] = _combine_reading_sections([gospel_section])
    return result


async def _fetch_today_mass() -> models.Mass | None:
    async with USCCB() as usccb:
        return await usccb.get_today_mass()


class MassReadingsSource:
    """Fetches today's readings once per day and caches them in memory.

    `refresh()` does the (slow, network) scrape and should be called from a
    background thread on a timer. `get_cached()` is instant and safe to call
    from a button-press handler or the render loop.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cached_date: datetime.date | None = None
        self._readings: dict[str, Reading] = {}

    def refresh(self) -> None:
        """Fetches today's readings if we don't already have them cached for today."""
        today = datetime.date.today()
        with self._lock:
            if self._cached_date == today and self._readings:
                return

        try:
            mass = asyncio.run(_fetch_today_mass())
        except Exception:
            logger.exception("Failed to fetch mass readings; keeping last cached value")
            return

        if mass is None:
            logger.warning("No mass found for today's date")
            return

        readings = _extract_readings(mass)
        with self._lock:
            self._cached_date = today
            self._readings = readings

    def get_cached(self, key: str) -> Reading | None:
        """Returns the cached Reading for `key` ("first_reading", "psalm", or "gospel")."""
        with self._lock:
            return self._readings.get(key)
