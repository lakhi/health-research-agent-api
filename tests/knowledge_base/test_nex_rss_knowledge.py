"""Unit and integration tests for knowledge_base.nex_rss_knowledge."""

import pytest

from knowledge_base.nex_rss_knowledge import (
    _compute_content_hash,
    _strip_html,
    fetch_rss_feed,
    get_rss_news_data,
    parse_rss_feed,
)


# ---------------------------------------------------------------------------
# Fixture XML — modelled on the verified live feed (19 items analysed)
# ---------------------------------------------------------------------------

FIXTURE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"
                   xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>

    <!-- Item A: empty content:encoded CDATA → use description -->
    <item>
      <guid isPermaLink="false">news-1789</guid>
      <pubDate>Wed, 18 Mar 2026 18:00:00 +0100</pubDate>
      <title>Live stream with Helena Hansen</title>
      <link>https://gig.univie.ac.at/en/study#c9773</link>
      <description>The event at VHS Urania is fully booked. You can still join via live stream.</description>
      <content:encoded><![CDATA[]]></content:encoded>
      <enclosure url="https://gig.univie.ac.at/fileadmin/img.png" length="0" type="image/png"/>
    </item>

    <!-- Item B: non-empty content:encoded CDATA → use content:encoded (HTML stripped) -->
    <item>
      <guid isPermaLink="false">news-1753</guid>
      <pubDate>Tue, 03 Mar 2026 09:11:11 +0100</pubDate>
      <title>How do music lessons affect the brain?</title>
      <link>https://gig.univie.ac.at/en/about-us/news/news-details/music-lessons</link>
      <description>A summary without full detail.</description>
      <content:encoded><![CDATA[<p>A <strong>familiar melody</strong> and <em>memories</em>.</p>]]></content:encoded>
      <enclosure url="https://gig.univie.ac.at/fileadmin/logo.png" length="0" type="image/png"/>
    </item>

    <!-- Item C: external link, empty content:encoded → use description -->
    <item>
      <guid isPermaLink="false">news-1749</guid>
      <pubDate>Mon, 02 Mar 2026 10:00:00 +0100</pubDate>
      <title>GiG members in the new edition of Rudolphina</title>
      <link>https://rudolphina.univie.ac.at/en/article/some-article</link>
      <description>Interviews with GiG members for the focus topic of stress in the science magazine.</description>
      <content:encoded><![CDATA[]]></content:encoded>
      <enclosure url="https://gig.univie.ac.at/fileadmin/user_upload/gig/News/2026_02_Rudolphina.png" length="0" type="image/png"/>
    </item>

    <!-- Item D: missing guid → should be skipped -->
    <item>
      <title>No GUID Article</title>
      <link>https://gig.univie.ac.at/en/no-guid</link>
      <description>This item has no guid.</description>
      <content:encoded><![CDATA[]]></content:encoded>
    </item>

    <!-- Item E: missing title → should be skipped -->
    <item>
      <guid isPermaLink="false">news-0001</guid>
      <link>https://gig.univie.ac.at/en/no-title</link>
      <description>This item has no title.</description>
      <content:encoded><![CDATA[]]></content:encoded>
    </item>

  </channel>
</rss>
"""


# ---------------------------------------------------------------------------
# _strip_html unit tests
# ---------------------------------------------------------------------------


def test_strip_html_removes_tags():
    assert _strip_html("<p>A <b>bold</b></p>") == "A bold"


def test_strip_html_decodes_entities():
    result = _strip_html("it&#039;s &amp; that")
    assert "'" in result
    assert "&" in result


def test_strip_html_collapses_whitespace():
    assert _strip_html("  hello   \n  world  ") == "hello world"


# ---------------------------------------------------------------------------
# _compute_content_hash unit tests
# ---------------------------------------------------------------------------


def test_compute_content_hash_is_deterministic():
    assert _compute_content_hash("hello") == _compute_content_hash("hello")


def test_compute_content_hash_differs_on_change():
    assert _compute_content_hash("hello") != _compute_content_hash("world")


# ---------------------------------------------------------------------------
# parse_rss_feed unit tests
# ---------------------------------------------------------------------------


def test_parse_rss_feed_happy_path():
    """5 items in fixture XML → 3 valid dicts (D and E skipped)."""
    results = parse_rss_feed(FIXTURE_XML)
    assert len(results) == 3


def test_parse_rss_feed_empty_cdata_uses_description():
    """Item A: empty CDATA → description text used as text_content."""
    results = parse_rss_feed(FIXTURE_XML)
    item_a = next(r for r in results if r["metadata"]["guid"] == "news-1789")
    assert "VHS Urania" in item_a["text_content"]
    assert "live stream" in item_a["text_content"]


def test_parse_rss_feed_nonempty_content_encoded_used():
    """Item B: non-empty CDATA → stripped HTML of content:encoded used."""
    results = parse_rss_feed(FIXTURE_XML)
    item_b = next(r for r in results if r["metadata"]["guid"] == "news-1753")
    assert "familiar melody" in item_b["text_content"]
    assert "memories" in item_b["text_content"]
    # HTML tags must be stripped
    assert "<p>" not in item_b["text_content"]
    assert "<strong>" not in item_b["text_content"]


def test_parse_rss_feed_external_link_uses_description():
    """Item C: external domain link, empty CDATA → description used; external link preserved."""
    results = parse_rss_feed(FIXTURE_XML)
    item_c = next(r for r in results if r["metadata"]["guid"] == "news-1749")
    assert "stress" in item_c["text_content"]
    assert item_c["metadata"]["link"] == "https://rudolphina.univie.ac.at/en/article/some-article"


def test_parse_rss_feed_skips_item_missing_guid():
    results = parse_rss_feed(FIXTURE_XML)
    guids = [r["metadata"]["guid"] for r in results]
    # Item D has no guid — "No GUID Article" should not appear
    titles = [r["metadata"]["title"] for r in results]
    assert "No GUID Article" not in titles
    assert len(guids) == 3


def test_parse_rss_feed_skips_item_missing_title():
    results = parse_rss_feed(FIXTURE_XML)
    guids = [r["metadata"]["guid"] for r in results]
    # Item E has guid news-0001 but no title — must be skipped
    assert "news-0001" not in guids


def test_parse_rss_feed_guid_is_short_id():
    """guid value is a short string like 'news-1789', not a full URL."""
    results = parse_rss_feed(FIXTURE_XML)
    item_a = next(r for r in results if r["metadata"]["guid"] == "news-1789")
    guid = item_a["metadata"]["guid"]
    assert guid == "news-1789"
    assert not guid.startswith("http")


def test_parse_rss_feed_enclosure_maps_to_image_url():
    results = parse_rss_feed(FIXTURE_XML)
    item_a = next(r for r in results if r["metadata"]["guid"] == "news-1789")
    assert item_a["metadata"]["image_url"] == "https://gig.univie.ac.at/fileadmin/img.png"


def test_parse_rss_feed_empty_feed():
    empty_xml = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    assert parse_rss_feed(empty_xml) == []


# ---------------------------------------------------------------------------
# get_rss_news_data structure tests (monkeypatched — no network)
# ---------------------------------------------------------------------------


def test_get_rss_news_data_structure(monkeypatch):
    """Returned dicts have required top-level keys."""
    import knowledge_base.nex_rss_knowledge as rss_mod

    monkeypatch.setattr(rss_mod, "fetch_rss_feed", lambda url=rss_mod.RSS_FEED_URL: FIXTURE_XML)
    results = get_rss_news_data()
    assert len(results) == 3
    for item in results:
        assert "name" in item
        assert "text_content" in item
        assert "metadata" in item


def test_metadata_required_fields(monkeypatch):
    """Each metadata dict contains all required fields."""
    import knowledge_base.nex_rss_knowledge as rss_mod

    monkeypatch.setattr(rss_mod, "fetch_rss_feed", lambda url=rss_mod.RSS_FEED_URL: FIXTURE_XML)
    results = get_rss_news_data()
    required = {"guid", "title", "link", "pub_date", "language", "source_type", "content_hash"}
    for item in results:
        assert required.issubset(item["metadata"].keys()), f"Missing fields in {item['metadata']}"


# ---------------------------------------------------------------------------
# Integration test — real HTTP GET
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_fetch_rss_feed_live():
    """Live network: fetch the real feed, validate structure."""
    xml_str = fetch_rss_feed()
    assert xml_str.strip().startswith("<?xml") or "<rss" in xml_str

    items = parse_rss_feed(xml_str)
    assert len(items) >= 1

    first = items[0]
    assert "name" in first
    assert "text_content" in first
    assert "guid" in first["metadata"]
