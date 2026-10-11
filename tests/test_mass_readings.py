"""Tests for sources/mass_readings.py (grouping USCCB sections into 3 screens, and caching)."""

from __future__ import annotations

import datetime
import types

import pytest
from catholic_mass_readings import models

from sources import mass_readings as mr
from sources.mass_readings import MassReadingsSource, Reading, _combine_reading_sections, _extract_readings

T = models.SectionType


def _section(type_, header, *readings):
    """Stand-in for models.Section exposing only what our code reads.
    `readings` are (citation, text) pairs."""
    return types.SimpleNamespace(
        type_=type_,
        display_header=header,
        readings=[types.SimpleNamespace(header=citation, text=text) for citation, text in readings],
    )


def _mass(*sections):
    return types.SimpleNamespace(sections=list(sections))


WEEKDAY = _mass(
    _section(T.READING, "Reading 1", ("1 Kings 19:9a, 11-13a", "At the mountain of God...")),
    _section(T.PSALM, "Responsorial Psalm", ("Psalms 85:9, 10", "R. Lord, let us see your kindness.")),
    _section(T.ALLELUIA, "Alleluia", ("Psalms 130:5", "I trust in the Lord.")),
    _section(T.GOSPEL, "Gospel", ("Matthew 14:22-33", "After he had fed the people...")),
)

SUNDAY = _mass(
    _section(T.READING, "Reading 1", ("Isaiah 55:1-3", "All you who are thirsty...")),
    _section(T.PSALM, "Responsorial Psalm", ("Psalms 145:8-9", "The hand of the Lord feeds us.")),
    _section(T.READING, "Reading 2", ("Romans 8:35, 37-39", "Brothers and sisters...")),
    _section(T.ALLELUIA, "Alleluia", ("Matthew 4:4b", "One does not live on bread alone.")),
    _section(T.GOSPEL, "Gospel", ("Matthew 14:13-21", "When Jesus heard of the death of John...")),
)


# --- grouping ---------------------------------------------------------------------


def test_single_section_combines_into_one_reading():
    reading = _combine_reading_sections([_section(T.GOSPEL, "Gospel", ("Matthew 14:22-33", "Body text."))])
    assert reading == Reading(heading="Gospel", citation="Matthew 14:22-33", body="Body text.")


def test_section_with_multiple_readings_joins_citations_and_bodies():
    reading = _combine_reading_sections(
        [_section(T.READING, "Reading 1", ("Gen 1:1", "In the beginning."), ("Gen 1:2", "The earth was formless."))]
    )
    assert reading.citation == "Gen 1:1; Gen 1:2"
    assert reading.body == "In the beginning.\n\nThe earth was formless."


def test_multiple_sections_are_labeled_and_separated():
    reading = _combine_reading_sections(
        [
            _section(T.READING, "Reading 1", ("Isaiah 55:1-3", "First text.")),
            _section(T.READING, "Reading 2", ("Romans 8:35", "Second text.")),
        ]
    )
    assert reading.heading == "Reading 1 & Reading 2"
    assert reading.citation == "Isaiah 55:1-3 | Romans 8:35"
    first, second = reading.body.split("\n\n---\n\n")
    assert first == "Reading 1 (Isaiah 55:1-3)\n\nFirst text."
    assert second == "Reading 2 (Romans 8:35)\n\nSecond text."


def test_weekday_mass_maps_to_three_screens():
    readings = _extract_readings(WEEKDAY)
    assert set(readings) == {"first_reading", "psalm", "gospel"}
    assert readings["first_reading"].citation == "1 Kings 19:9a, 11-13a"
    assert readings["psalm"].citation == "Psalms 85:9, 10"
    assert readings["gospel"].citation == "Matthew 14:22-33"


def test_sunday_second_reading_is_appended_to_first_reading():
    readings = _extract_readings(SUNDAY)
    assert set(readings) == {"first_reading", "psalm", "gospel"}
    first = readings["first_reading"]
    assert first.citation == "Isaiah 55:1-3 | Romans 8:35, 37-39"
    assert "All you who are thirsty" in first.body
    assert "Brothers and sisters" in first.body
    assert first.body.index("All you who are thirsty") < first.body.index("Brothers and sisters")


def test_alleluia_is_not_shown_on_any_screen():
    readings = _extract_readings(SUNDAY)
    assert all("bread alone" not in r.body for r in readings.values())


def test_missing_sections_are_omitted_rather_than_invented():
    readings = _extract_readings(_mass(_section(T.GOSPEL, "Gospel", ("John 1:1", "In the beginning was the Word."))))
    assert set(readings) == {"gospel"}


def test_reading_keys_match_config():
    import config

    assert set(_extract_readings(WEEKDAY)) == set(config.READING_KEYS)


# --- MassReadingsSource caching ---------------------------------------------------


@pytest.fixture
def today(monkeypatch):
    current = {"date": datetime.date(2026, 8, 9)}

    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return current["date"]

    monkeypatch.setattr(mr, "datetime", types.SimpleNamespace(date=FakeDate))
    return current


@pytest.fixture
def usccb(monkeypatch):
    """Replaces the USCCB scrape with queued Mass objects (or exceptions)."""
    server = types.SimpleNamespace(queue=[], fetches=0)

    async def fake_fetch():
        server.fetches += 1
        item = server.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(mr, "_fetch_today_mass", fake_fetch)
    return server


def test_nothing_cached_before_first_fetch():
    assert MassReadingsSource().get_cached("gospel") is None


def test_refresh_caches_all_readings(today, usccb):
    usccb.queue.append(WEEKDAY)
    src = MassReadingsSource()
    src.refresh()
    assert src.get_cached("gospel").citation == "Matthew 14:22-33"
    assert src.get_cached("psalm") is not None
    assert src.get_cached("first_reading") is not None


def test_unknown_key_returns_none(today, usccb):
    usccb.queue.append(WEEKDAY)
    src = MassReadingsSource()
    src.refresh()
    assert src.get_cached("homily") is None


def test_scrapes_only_once_per_day(today, usccb):
    usccb.queue.append(WEEKDAY)
    src = MassReadingsSource()
    src.refresh()
    src.refresh()
    assert usccb.fetches == 1


def test_rescrapes_after_date_rolls_over(today, usccb):
    usccb.queue += [WEEKDAY, SUNDAY]
    src = MassReadingsSource()
    src.refresh()
    today["date"] += datetime.timedelta(days=1)
    src.refresh()
    assert usccb.fetches == 2
    assert src.get_cached("gospel").citation == "Matthew 14:13-21"


def test_scrape_failure_keeps_previous_readings(today, usccb):
    usccb.queue += [WEEKDAY, RuntimeError("403 Forbidden")]
    src = MassReadingsSource()
    src.refresh()
    today["date"] += datetime.timedelta(days=1)
    src.refresh()  # must not raise
    assert src.get_cached("gospel").citation == "Matthew 14:22-33"


def test_no_mass_found_keeps_previous_readings_and_retries(today, usccb):
    usccb.queue += [WEEKDAY, None, SUNDAY]
    src = MassReadingsSource()
    src.refresh()
    today["date"] += datetime.timedelta(days=1)
    src.refresh()  # no Mass found: keep yesterday's...
    assert src.get_cached("gospel").citation == "Matthew 14:22-33"
    src.refresh()  # ...and retry rather than treating today as done
    assert src.get_cached("gospel").citation == "Matthew 14:13-21"


def test_failure_before_any_success_leaves_cache_empty(today, usccb):
    usccb.queue.append(RuntimeError("403 Forbidden"))
    src = MassReadingsSource()
    src.refresh()
    assert src.get_cached("gospel") is None
