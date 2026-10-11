"""Tests for sources/latin_word.py (Transparent Language RSS feed parsing and caching)."""

from __future__ import annotations

import datetime
import types
from unittest.mock import MagicMock

import pytest
import requests

from sources import latin_word as latin_mod
from sources.latin_word import LatinWord, LatinWordSource, _parse_feed

_TH = '<th scope="row" style="color:#484868;font-family:Arial;font-size:large;text-align:left;vertical-align:top">'
_TD = '<td style="color:#484868;font-family:Arial;font-size:large;padding-bottom:3em">'


def _feed(title="excusare: to excuse, to make an excuse for", pos="verb",
          latin="Ignorantia iuris neminem excusat.", english="Ignorance of the law excuses no one.",
          include_item=True):
    """An RSS document in the same shape as the real feed (styled table inside CDATA)."""
    rows = []
    for label, value in (("Part of speech:", pos), ("Example sentence:", latin), ("Sentence meaning:", english)):
        if value is not None:
            rows.append(f"<tr>\n{_TH}{label}</th>\n{_TD}{value}</td>\n</tr>")
    item = f"""
<item>
<description><![CDATA[
<table>
{chr(10).join(rows)}
</table>
]]>
</description>
<pubDate>Thu, 13 Aug 2026 00:00:00 GMT</pubDate>
<title><![CDATA[{title}]]></title>
<wotd:transliteratedWord></wotd:transliteratedWord>
</item>"""
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<?xml-stylesheet type="text/xsl" href="https://feeds.feedblitz.com/feedblitz_rss.xslt"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0" xmlns:wotd="http://www.transparent.com/word-of-the-day/">
<channel>
<title>Latin Word of the Day</title>
<meta xmlns="http://www.w3.org/1999/xhtml" name="robots" content="noindex" />
{item if include_item else ""}
</channel>
</rss>"""


# --- parsing ----------------------------------------------------------------------


def test_parses_all_fields():
    assert _parse_feed(_feed()) == LatinWord(
        word="excusare",
        short_definition="to excuse, to make an excuse for",
        part_of_speech="verb",
        example_latin="Ignorantia iuris neminem excusat.",
        example_english="Ignorance of the law excuses no one.",
    )


def test_definition_containing_a_colon_splits_only_on_the_first():
    word = _parse_feed(_feed(title="saeculum: age: century"))
    assert (word.word, word.short_definition) == ("saeculum", "age: century")


def test_title_without_definition():
    word = _parse_feed(_feed(title="saeculum"))
    assert (word.word, word.short_definition) == ("saeculum", "")


def test_html_entities_are_unescaped():
    word = _parse_feed(_feed(english="Bread &amp; wine &quot;quoted&quot; &#8212; dash"))
    assert word.example_english == 'Bread & wine "quoted" — dash'


def test_surrounding_whitespace_is_stripped():
    word = _parse_feed(_feed(title="  aqua :  water  ", latin="  Aqua vitae.  "))
    assert word.example_latin == "Aqua vitae."
    assert word.short_definition == "water"


def test_missing_table_row_becomes_empty_string():
    word = _parse_feed(_feed(english=None))
    assert word.example_english == ""
    assert word.example_latin == "Ignorantia iuris neminem excusat."


def test_feed_with_no_item_returns_none():
    assert _parse_feed(_feed(include_item=False)) is None


def test_empty_title_returns_none():
    assert _parse_feed(_feed(title="")) is None


# --- LatinWordSource caching ------------------------------------------------------


@pytest.fixture
def today(monkeypatch):
    """Controls latin_word.py's notion of today's date."""
    current = {"date": datetime.date(2026, 8, 13)}

    class FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return current["date"]

    monkeypatch.setattr(latin_mod, "datetime", types.SimpleNamespace(date=FakeDate))
    return current


@pytest.fixture
def feed_server(monkeypatch):
    """Serves queued RSS strings (or raises queued exceptions); counts requests."""
    server = types.SimpleNamespace(queue=[], requests=0)

    def fake_get(url, timeout=None):
        server.requests += 1
        item = server.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        response = MagicMock()
        response.text = item
        return response

    monkeypatch.setattr(latin_mod.requests, "get", fake_get)
    return server


def test_nothing_cached_before_first_fetch():
    assert LatinWordSource().get_cached() is None


def test_refresh_caches_the_word(today, feed_server):
    feed_server.queue.append(_feed())
    src = LatinWordSource()
    src.refresh()
    assert src.get_cached().word == "excusare"


def test_fetches_only_once_per_day(today, feed_server):
    feed_server.queue.append(_feed())
    src = LatinWordSource()
    src.refresh()
    src.refresh()
    src.refresh()
    assert feed_server.requests == 1


def test_refetches_after_date_rolls_over(today, feed_server):
    feed_server.queue += [_feed(title="excusare: to excuse"), _feed(title="saeculum: age, century")]
    src = LatinWordSource()
    src.refresh()
    today["date"] += datetime.timedelta(days=1)
    src.refresh()
    assert feed_server.requests == 2
    assert src.get_cached().word == "saeculum"


@pytest.mark.parametrize(
    "error",
    [requests.ConnectionError("down"), requests.Timeout("slow"), requests.HTTPError("503")],
)
def test_network_failure_keeps_last_word(today, feed_server, error):
    feed_server.queue += [_feed(), error]
    src = LatinWordSource()
    src.refresh()
    today["date"] += datetime.timedelta(days=1)
    src.refresh()  # must not raise
    assert src.get_cached().word == "excusare"


def test_malformed_xml_keeps_last_word(today, feed_server):
    feed_server.queue += [_feed(), "<rss><channel><item>not closed"]
    src = LatinWordSource()
    src.refresh()
    today["date"] += datetime.timedelta(days=1)
    src.refresh()
    assert src.get_cached().word == "excusare"


def test_empty_feed_does_not_replace_word_and_retries_later(today, feed_server):
    feed_server.queue += [_feed(), _feed(include_item=False), _feed(title="saeculum: age")]
    src = LatinWordSource()
    src.refresh()
    today["date"] += datetime.timedelta(days=1)
    src.refresh()  # empty feed: keep yesterday's word...
    assert src.get_cached().word == "excusare"
    src.refresh()  # ...and try again rather than treating today as done
    assert src.get_cached().word == "saeculum"


def test_failure_before_any_success_leaves_cache_empty(today, feed_server):
    feed_server.queue.append(requests.ConnectionError("down"))
    src = LatinWordSource()
    src.refresh()
    assert src.get_cached() is None
