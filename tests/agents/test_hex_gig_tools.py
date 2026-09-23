"""Unit tests for agents.hex_gig_tools — the deterministic recency path.

The bug these guard against: asking the agent for the "latest" news returned a
similarity-ranked top-10 in which the newest articles did not appear at all.
"""

from unittest.mock import MagicMock

import pytest

from agents import hex_gig_tools
from agents.hex_gig_tools import MAX_LATEST_NEWS, _sort_date, get_latest_hex_news

# ---------------------------------------------------------------------------
# Fake rows — shaped like ai.hex_gig_embeddings, deliberately out of date order
# ---------------------------------------------------------------------------

ROWS = [
    {
        "guid": "news-1749",
        "title": "On cosmetic procedures",
        "pub_date_iso": "2026-01-22",
        "pub_date": "Thu, 22 Jan 2026 10:00:00 +0100",
        "link": "https://gig.univie.ac.at/en/a",
        "content": "Final presentations of a research seminar.",
        "title_de": None,
        "link_de": None,
    },
    {
        "guid": "news-2200",
        "title": "Personal expectations of ageing",
        "pub_date_iso": "2026-08-18",
        "pub_date": "Tue, 18 Aug 2026 09:00:00 +0200",
        "link": "https://gig.univie.ac.at/en/b",
        "content": "Expectations of one's own ageing are a self-fulfilling prophecy.",
        "title_de": None,
        "link_de": None,
    },
    # No pub_date_iso — an article ingested before that field existed.
    {
        "guid": "news-2100",
        "title": "Julia Reiter on the effects of heat",
        "pub_date_iso": None,
        "pub_date": "Wed, 05 Aug 2026 12:00:00 +0200",
        "link": "https://gig.univie.ac.at/en/c",
        "content": "TV appearance on heat, health and social inequalities.",
        "title_de": None,
        "link_de": None,
    },
    # Second chunk of the same article — must not become a separate entry.
    {
        "guid": "news-2200",
        "title": "Personal expectations of ageing",
        "pub_date_iso": "2026-08-18",
        "pub_date": "Tue, 18 Aug 2026 09:00:00 +0200",
        "link": "https://gig.univie.ac.at/en/b",
        "content": "A study by Christina Ristl.",
        "title_de": None,
        "link_de": None,
    },
]


@pytest.fixture
def fake_engine(monkeypatch):
    """Patch get_engine so the tool reads ROWS instead of PostgreSQL."""

    def _install(rows):
        connection = MagicMock()
        connection.execute.return_value.mappings.return_value.all.return_value = rows
        engine = MagicMock()
        engine.connect.return_value.__enter__.return_value = connection
        monkeypatch.setattr(hex_gig_tools, "get_engine", lambda: engine)
        return engine

    return _install


# ---------------------------------------------------------------------------
# _sort_date
# ---------------------------------------------------------------------------


def test_sort_date_prefers_iso():
    assert _sort_date("2026-08-18", "Thu, 22 Jan 2026 10:00:00 +0100") == "2026-08-18"


def test_sort_date_falls_back_to_rfc2822():
    """Rows written before pub_date_iso existed must still sort correctly."""
    assert _sort_date(None, "Wed, 05 Aug 2026 12:00:00 +0200") == "2026-08-05"


def test_sort_date_empty_when_nothing_parseable():
    assert _sort_date(None, "not a date") == ""
    assert _sort_date(None, None) == ""


# ---------------------------------------------------------------------------
# get_latest_hex_news
# ---------------------------------------------------------------------------


def test_returns_articles_newest_first(fake_engine):
    fake_engine(ROWS)
    result = get_latest_hex_news()
    positions = [
        result.index("Personal expectations of ageing"),
        result.index("Julia Reiter on the effects of heat"),
        result.index("On cosmetic procedures"),
    ]
    assert positions == sorted(positions), "articles must be ordered newest first"


def test_chunks_of_one_article_are_merged(fake_engine):
    """Two chunks sharing a guid are one article, not two."""
    fake_engine(ROWS)
    result = get_latest_hex_news()
    assert result.count("Personal expectations of ageing (published 2026-08-18)") == 1
    assert "self-fulfilling prophecy" in result
    assert "Christina Ristl" in result


def test_limit_is_respected_and_clamped(fake_engine):
    fake_engine(ROWS)
    assert get_latest_hex_news(limit=1).count("published ") == 1
    # Out-of-range values clamp rather than raise or return everything.
    assert get_latest_hex_news(limit=0).count("published ") == 1
    assert get_latest_hex_news(limit=MAX_LATEST_NEWS + 50).count("published ") == 3


def test_publication_date_and_link_are_included(fake_engine):
    """The agent cites date and link from this output, so both must survive."""
    fake_engine(ROWS)
    result = get_latest_hex_news()
    assert "published 2026-08-18" in result
    assert "https://gig.univie.ac.at/en/b" in result


def test_empty_knowledge_base_is_reported_not_faked(fake_engine):
    fake_engine([])
    assert "No news articles" in get_latest_hex_news()


def test_database_error_returns_a_message_rather_than_raising(monkeypatch):
    """A DB blip must not take the whole agent turn down."""

    def boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(hex_gig_tools, "get_engine", boom)
    result = get_latest_hex_news()
    assert "could not be reached" in result


def test_bilingual_article_lists_both_titles_and_links(fake_engine):
    """The agent cites the title and link matching its reply language, so both must be offered."""
    fake_engine(
        [
            {
                "guid": "news-2300",
                "title": "Thinking About Health in a Societal Context",
                "pub_date_iso": "2026-09-16",
                "pub_date": "Wed, 16 Sep 2026 10:00:00 +0200",
                "link": "https://gig.univie.ac.at/en/d",
                "title_de": "Gesundheit gesellschaftlich denken",
                "link_de": "https://gig.univie.ac.at/detailansicht/d",
                "content": "GiG network news: ...\n\nNeuigkeiten aus dem Forschungsverbund ...",
            }
        ]
    )
    result = get_latest_hex_news()
    assert "German title: Gesundheit gesellschaftlich denken" in result
    assert "Link (English): https://gig.univie.ac.at/en/d" in result
    assert "Link (German): https://gig.univie.ac.at/detailansicht/d" in result


def test_english_only_article_keeps_the_single_link_shape(fake_engine):
    fake_engine(ROWS)
    result = get_latest_hex_news()
    assert "Link: https://gig.univie.ac.at/en/b" in result
    assert "German title" not in result
