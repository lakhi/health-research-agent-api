import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.request import urlopen

from agno.knowledge import Knowledge

logger = logging.getLogger(__name__)

RSS_FEED_URL = "https://gig.univie.ac.at/en/about-us/news/feed.xml"
RSS_LANGUAGE = "en"
RSS_SOURCE_TYPE = "news_article"
RSS_NAMESPACES = {"content": "http://purl.org/rss/1.0/modules/content/"}

# The CMS emits an empty rich-text field as "<>" inside content:encoded, which survives HTML
# stripping as the literal two-character string "<>". That is truthy, so it used to suppress the
# <description> fallback and two articles were embedded with "<>" as their entire body. Require at
# least one alphanumeric character before treating stripped text as real content.
_HAS_WORD_CHAR_RE = re.compile(r"\w")


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


def _is_meaningful(text: str) -> bool:
    """True when *text* contains at least one word character (letter/digit/underscore)."""
    return bool(_HAS_WORD_CHAR_RE.search(text))


def _compute_content_hash(text: str) -> str:
    """Return SHA-256 hex digest of the stripped text for audit/change detection."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _to_iso_date(pub_date: str) -> str:
    """Convert an RFC-2822 pubDate to a sortable YYYY-MM-DD string; "" if unparseable."""
    if not pub_date:
        return ""
    try:
        return parsedate_to_datetime(pub_date).date().isoformat()
    except (TypeError, ValueError):
        logger.warning("Unparseable pubDate, storing empty pub_date_iso: %r", pub_date)
        return ""


def _build_document_text(title: str, iso_date: str, body: str) -> str:
    """Assemble the text that actually gets embedded.

    The headline is the most topic-dense field an article has and the date is what "latest"
    questions are really about, yet both used to live only in metadata — the embedding was built
    from the body alone. Putting them in the embedded text is what lets a query like
    "news about heat in August" match on more than a paragraph of prose.
    """
    header = f"GiG network news: {title}"
    if iso_date:
        header = f"{header}\nPublished: {iso_date}"
    return f"{header}\n\n{body}" if body else header


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

    # Prefer content:encoded when it carries real text; fall back to description otherwise
    content_encoded_el = item.find("content:encoded", RSS_NAMESPACES)
    raw_content = (content_encoded_el.text or "").strip() if content_encoded_el is not None else ""
    plain_content = _strip_html(raw_content) if raw_content else ""

    if not _is_meaningful(plain_content):
        description_el = item.find("description")
        description = (description_el.text or "").strip() if description_el is not None else ""
        plain_content = _strip_html(description)

    if not _is_meaningful(plain_content):
        plain_content = ""

    enclosure_el = item.find("enclosure")
    image_url = ""
    if enclosure_el is not None:
        image_url = enclosure_el.get("url", "")

    iso_date = _to_iso_date(pub_date)
    document_text = _build_document_text(title, iso_date, plain_content)

    return {
        "name": f"HeX News - {title}",
        "text_content": document_text,
        "metadata": {
            "guid": guid,
            "title": title,
            "link": link,
            "pub_date": pub_date,
            # Sortable form of pub_date. The RFC-2822 original ("Thu, 11 Jun 2026 09:18:00 +0200")
            # is not something a model can order reliably by eye.
            "pub_date_iso": iso_date,
            "language": RSS_LANGUAGE,
            "source_type": RSS_SOURCE_TYPE,
            "image_url": image_url,
            # Fingerprint of the text we actually embed, so a changed article is detectable.
            "content_hash": _compute_content_hash(document_text),
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
    """Fetch and parse the HeX RSS news feed.

    Returns a list of dicts with keys: ``name``, ``text_content``, ``metadata``.
    """
    xml_str = fetch_rss_feed()
    return parse_rss_feed(xml_str)


async def _astored_news_fingerprints(knowledge: Knowledge) -> dict[str, tuple[str | None, str | None]]:
    """Map ``name`` → ``(content_id, content_hash)`` for news articles already in *knowledge*.

    Failure is deliberately non-fatal: an empty map means "treat every article as new", which
    costs a re-embed of the whole feed but can never leave the knowledge base short of an article.
    """
    try:
        contents, _ = await knowledge.aget_content()
    except Exception:
        logger.warning("Could not read stored knowledge contents — re-inserting every article", exc_info=True)
        return {}

    fingerprints: dict[str, tuple[str | None, str | None]] = {}
    for content in contents:
        metadata = content.metadata or {}
        if metadata.get("source_type") != RSS_SOURCE_TYPE or not content.name:
            continue
        fingerprints[content.name] = (content.id, metadata.get("content_hash"))
    return fingerprints


async def aload_rss_into_knowledge(knowledge: Knowledge) -> tuple[int, int]:
    """Fetch the RSS feed and bring *knowledge* in line with it.

    An article is (re)inserted only when its ``content_hash`` differs from what is stored, so a
    steady-state run does no embedding work at all.

    This deliberately does not use ``skip_if_exists=True``. Agno derives its own dedupe key from
    the content *name* and type (``Knowledge._build_content_hash``), never the body — so under
    ``skip_if_exists`` an article was keyed by its title alone and could never be updated once
    stored. A feed that later filled in an empty article, fixed a typo, or expanded a stub was
    invisible to us forever; two articles sat in the knowledge base with "<>" as their whole body
    while the feed served a perfectly good description. Comparing hashes ourselves and replacing
    the content on a mismatch makes the pipeline self-healing.

    Returns ``(items_seen, items_written)`` for logging.
    """
    items = get_rss_news_data()
    stored = await _astored_news_fingerprints(knowledge)

    written = 0
    for item in items:
        name = item["name"]
        content_id, stored_hash = stored.get(name, (None, None))

        if stored_hash == item["metadata"]["content_hash"]:
            continue

        if content_id is not None:
            logger.info("RSS article changed — replacing: %s", name)
            await knowledge.aremove_content_by_id(content_id)
        # Also clear vectors orphaned by an earlier run that left no contents-db row behind.
        knowledge.remove_vectors_by_name(name)

        await knowledge.ainsert(
            name=name,
            text_content=item["text_content"],
            metadata=item["metadata"],
            skip_if_exists=False,
        )
        written += 1

    logger.info("RSS feed: %d items, %d written, %d unchanged", len(items), written, len(items) - written)
    return len(items), written
