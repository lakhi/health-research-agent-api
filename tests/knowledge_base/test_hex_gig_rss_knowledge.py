"""Unit and integration tests for knowledge_base.hex_gig_rss_knowledge."""

import pytest

from knowledge_base.hex_gig_rss_knowledge import (
    _build_document_text,
    _compute_content_hash,
    _is_meaningful,
    _strip_html,
    _to_iso_date,
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

    <!-- Item F: content:encoded is the CMS's empty-field artifact "<>" → must fall back
         to description rather than embedding "<>" as the whole article -->
    <item>
      <guid isPermaLink="false">news-2159</guid>
      <pubDate>Thu, 11 Jun 2026 09:18:00 +0200</pubDate>
      <title>Launch of the first comprehensive Health Survey</title>
      <link>https://gig.univie.ac.at/en/health-survey</link>
      <description>For the first time, the network is surveying all staff about their health at work.</description>
      <content:encoded><![CDATA[<>]]></content:encoded>
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
    """6 items in fixture XML → 4 valid dicts (D and E skipped)."""
    results = parse_rss_feed(FIXTURE_XML)
    assert len(results) == 4


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
    assert len(guids) == 4


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
    import knowledge_base.hex_gig_rss_knowledge as rss_mod

    monkeypatch.setattr(rss_mod, "fetch_rss_feed", lambda url=rss_mod.RSS_FEED_URL: FIXTURE_XML)
    results = get_rss_news_data()
    assert len(results) == 4
    for item in results:
        assert "name" in item
        assert "text_content" in item
        assert "metadata" in item


def test_metadata_required_fields(monkeypatch):
    """Each metadata dict contains all required fields."""
    import knowledge_base.hex_gig_rss_knowledge as rss_mod

    monkeypatch.setattr(rss_mod, "fetch_rss_feed", lambda url=rss_mod.RSS_FEED_URL: FIXTURE_XML)
    results = get_rss_news_data()
    required = {
        "guid",
        "title",
        "link",
        "pub_date",
        "pub_date_iso",
        "language",
        "source_type",
        "content_hash",
    }
    for item in results:
        assert required.issubset(item["metadata"].keys()), f"Missing fields in {item['metadata']}"


# ---------------------------------------------------------------------------
# _is_meaningful / _to_iso_date / _build_document_text unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("empty", ["", "   ", "<>", "<> <>", "\n\t"])
def test_is_meaningful_rejects_contentless_text(empty):
    """The CMS's "<>" artifact must not count as article content."""
    assert not _is_meaningful(empty)


@pytest.mark.parametrize("real", ["A", "health survey", "2026", "Böhm"])
def test_is_meaningful_accepts_real_text(real):
    assert _is_meaningful(real)


def test_to_iso_date_converts_rfc2822():
    assert _to_iso_date("Thu, 11 Jun 2026 09:18:00 +0200") == "2026-06-11"


@pytest.mark.parametrize("bad", ["", "not a date", "31 Feb 2026"])
def test_to_iso_date_returns_empty_on_unparseable(bad):
    assert _to_iso_date(bad) == ""


def test_build_document_text_leads_with_title_and_date():
    text = _build_document_text("Heat and health", "2026-08-05", "Julia Reiter on the effects of heat.")
    assert text.startswith("GiG network news: Heat and health")
    assert "Published: 2026-08-05" in text
    assert text.endswith("Julia Reiter on the effects of heat.")


def test_build_document_text_survives_missing_body_and_date():
    """A body-less article still embeds something searchable rather than an empty string."""
    text = _build_document_text("Heat and health", "", "")
    assert text == "GiG network news: Heat and health"


# ---------------------------------------------------------------------------
# Regression tests for the "<>" ingestion bug
# ---------------------------------------------------------------------------


def test_parse_rss_feed_empty_field_artifact_falls_back_to_description():
    """Item F: content:encoded of "<>" must not suppress the description fallback.

    Two live articles were embedded with "<>" as their entire body because "<>" is truthy.
    """
    results = parse_rss_feed(FIXTURE_XML)
    item_f = next(r for r in results if r["metadata"]["guid"] == "news-2159")
    assert "surveying all staff" in item_f["text_content"]
    assert "<>" not in item_f["text_content"]
    assert len(item_f["text_content"]) > 50


def test_parse_rss_feed_embeds_title_and_iso_date():
    """Title and date belong in the embedded text, not only in metadata."""
    results = parse_rss_feed(FIXTURE_XML)
    item_a = next(r for r in results if r["metadata"]["guid"] == "news-1789")
    assert "Live stream with Helena Hansen" in item_a["text_content"]
    assert "Published: 2026-03-18" in item_a["text_content"]
    assert item_a["metadata"]["pub_date_iso"] == "2026-03-18"


def test_content_hash_fingerprints_the_embedded_text():
    """The hash must cover what is embedded, or a changed article looks unchanged."""
    results = parse_rss_feed(FIXTURE_XML)
    for item in results:
        assert item["metadata"]["content_hash"] == _compute_content_hash(item["text_content"])


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
