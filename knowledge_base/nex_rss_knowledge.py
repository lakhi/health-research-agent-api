import hashlib
import logging
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.request import urlopen

logger = logging.getLogger(__name__)

RSS_FEED_URL = "https://gig.univie.ac.at/en/about-us/news/feed.xml"
RSS_LANGUAGE = "en"
RSS_SOURCE_TYPE = "news_article"
RSS_NAMESPACES = {"content": "http://purl.org/rss/1.0/modules/content/"}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


class _HTMLStripper(HTMLParser):
    """Minimal HTMLParser subclass that strips tags and collects text data."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts).split()  # type: ignore[return-value]


def _strip_html(html: str) -> str:
    """Strip HTML tags, decode entities, and collapse whitespace."""
    stripper = _HTMLStripper()
    stripper.feed(html)
    words: list[str] = stripper._parts
    # Re-join all collected text parts, then split on any whitespace to collapse
    joined = " ".join(words)
    return " ".join(joined.split())


def _compute_content_hash(text: str) -> str:
    """Return SHA-256 hex digest of the stripped text for audit/change detection."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _parse_rss_item(item: ET.Element) -> dict | None:  # type: ignore[type-arg]
    """Extract fields from a single RSS <item> element.

    Returns None (and logs a warning) if guid or title is missing.
    """
    guid_el = item.find("guid")
    title_el = item.find("title")

    if guid_el is None or not (guid_el.text or "").strip():
        logger.warning("RSS item missing <guid> — skipping")
        return None

    if title_el is None or not (title_el.text or "").strip():
        logger.warning("RSS item missing <title> — skipping")
        return None

    guid = (guid_el.text or "").strip()
    title = (title_el.text or "").strip()

    link_el = item.find("link")
    link = (link_el.text or "").strip() if link_el is not None else ""

    pub_date_el = item.find("pubDate")
    pub_date = (pub_date_el.text or "").strip() if pub_date_el is not None else ""

    # Prefer content:encoded when non-empty after stripping; fall back to description
    content_encoded_el = item.find("content:encoded", RSS_NAMESPACES)
    raw_content = (content_encoded_el.text or "").strip() if content_encoded_el is not None else ""
    plain_content = _strip_html(raw_content) if raw_content else ""

    if not plain_content:
        description_el = item.find("description")
        description = (description_el.text or "").strip() if description_el is not None else ""
        plain_content = _strip_html(description)

    enclosure_el = item.find("enclosure")
    image_url = ""
    if enclosure_el is not None:
        image_url = enclosure_el.get("url", "")

    return {
        "name": f"NEX News - {title}",
        "text_content": plain_content,
        "metadata": {
            "guid": guid,
            "title": title,
            "link": link,
            "pub_date": pub_date,
            "language": RSS_LANGUAGE,
            "source_type": RSS_SOURCE_TYPE,
            "image_url": image_url,
            "content_hash": _compute_content_hash(plain_content),
        },
    }


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def fetch_rss_feed(url: str = RSS_FEED_URL) -> str:
    """Fetch the RSS feed at *url* and return the raw XML string."""
    with urlopen(url, timeout=15) as response:  # noqa: S310  (url is a known constant)
        return response.read().decode("utf-8")


def parse_rss_feed(xml_str: str) -> list[dict]:  # type: ignore[type-arg]
    """Parse *xml_str* as RSS 2.0 and return one dict per valid <item>."""
    root = ET.fromstring(xml_str)
    channel = root.find("channel")
    items_el = channel.findall("item") if channel is not None else root.findall(".//item")

    results: list[dict] = []  # type: ignore[type-arg]
    for item_el in items_el:
        parsed = _parse_rss_item(item_el)
        if parsed is not None:
            results.append(parsed)

    return results


def get_rss_news_data() -> list[dict]:  # type: ignore[type-arg]
    """Fetch and parse the NEX RSS news feed.

    Returns a list of dicts with keys: ``name``, ``text_content``, ``metadata``.
    """
    xml_str = fetch_rss_feed()
    return parse_rss_feed(xml_str)
