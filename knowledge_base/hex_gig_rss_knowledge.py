import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.request import urlopen

from agno.knowledge import Knowledge

logger = logging.getLogger(__name__)

# The site publishes every article in both languages, under the same <guid> in each feed, so the
# two feeds are merged into one bilingual document per article (see build_news_items). Ingesting
# only the English feed left German users with no German content at all — not even the network's
# German name, "Forschungsverbund Gesundheit in Gesellschaft", which GiG abbreviates.
RSS_FEED_URL = "https://gig.univie.ac.at/en/about-us/news/feed.xml"
RSS_FEED_URL_DE = "https://gig.univie.ac.at/news-events/news/feed.xml"
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


# Per-language section headings for the embedded text. The German heading carries the network's
# German name so a German query about the network lands on German wording, not a translation.
_SECTION_LABELS = {
    "en": ("GiG network news", "Published"),
    "de": ("Neuigkeiten aus dem Forschungsverbund Gesundheit in Gesellschaft", "Veröffentlicht"),
}


def _build_document_text(title: str, iso_date: str, body: str, language: str = "en") -> str:
    """Assemble one language's section of the text that actually gets embedded.

    The headline is the most topic-dense field an article has and the date is what "latest"
    questions are really about, yet both used to live only in metadata — the embedding was built
    from the body alone. Putting them in the embedded text is what lets a query like
    "news about heat in August" match on more than a paragraph of prose.
    """
    heading, published = _SECTION_LABELS[language]
    header = f"{heading}: {title}"
    if iso_date:
        header = f"{header}\n{published}: {iso_date}"
    return f"{header}\n\n{body}" if body else header


def _parse_rss_item(item: ET.Element) -> dict[str, str] | None:
    """Extract the article fields from a single RSS <item> element.

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

    return {
        "guid": guid,
        "title": title,
        "link": link,
        "pub_date": pub_date,
        "body": plain_content,
        "image_url": image_url,
    }


def _build_news_item(en: dict[str, str] | None, de: dict[str, str] | None) -> dict[str, Any]:
    """Build one knowledge item from an article's English and/or German version.

    English is the primary language: it supplies ``title``, ``link``, the date and the item
    ``name``. Keeping the name English is what lets items stored before the German feed was added
    be recognised by name and replaced in place (their content_hash changes) instead of being
    left behind as duplicates. ``title_de``/``link_de`` are set whenever a German version exists.

    There is deliberately no ``language`` key: a merged item is both languages, and agno
    advertises every metadata key to the model as a filter — a ``language`` filter would drop
    every research paper and member profile, which carry no such key.
    """
    primary = en or de
    if primary is None:
        raise ValueError("A news item needs at least one language version")

    pub_date = primary["pub_date"] or (de["pub_date"] if de else "")
    # Sortable form of pub_date. The RFC-2822 original ("Thu, 11 Jun 2026 09:18:00 +0200")
    # is not something a model can order reliably by eye.
    iso_date = _to_iso_date(pub_date)

    sections = []
    if en is not None:
        sections.append(_build_document_text(en["title"], iso_date, en["body"], "en"))
    if de is not None:
        sections.append(_build_document_text(de["title"], iso_date, de["body"], "de"))
    document_text = "\n\n".join(sections)

    metadata = {
        "guid": primary["guid"],
        "title": primary["title"],
        "link": primary["link"],
        "pub_date": pub_date,
        "pub_date_iso": iso_date,
        "source_type": RSS_SOURCE_TYPE,
        "image_url": primary["image_url"] or (de["image_url"] if de else ""),
        # Fingerprint of the text we actually embed, so a changed article is detectable.
        "content_hash": _compute_content_hash(document_text),
    }
    if de is not None:
        metadata["title_de"] = de["title"]
        metadata["link_de"] = de["link"]

    return {
        "name": f"HeX News - {primary['title']}",
        "text_content": document_text,
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def fetch_rss_feed(url: str = RSS_FEED_URL) -> str:
    """Fetch the RSS feed at *url* and return the raw XML string."""
    with urlopen(url, timeout=15) as response:  # noqa: S310  (url is a known constant)
        return response.read().decode("utf-8")


def parse_rss_feed(xml_str: str) -> list[dict[str, str]]:
    """Parse *xml_str* as RSS 2.0 and return the article fields of each valid <item>."""
    root = ET.fromstring(xml_str)
    channel = root.find("channel")
    items_el = channel.findall("item") if channel is not None else root.findall(".//item")

    results: list[dict[str, str]] = []
    for item_el in items_el:
        parsed = _parse_rss_item(item_el)
        if parsed is not None:
            results.append(parsed)

    return results


def build_news_items(articles_en: list[dict[str, str]], articles_de: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Merge the English and German feeds into one bilingual knowledge item per article.

    Articles are paired by <guid>, which the site keeps identical across the two feeds. One
    document per article rather than one per language: two translations of one article would
    otherwise take two of the reranked slots in every search, and get_latest_hex_news — which
    groups rows by guid — would splice both bodies together under whichever title it read first.
    An article present in only one feed is still stored, in that language alone.
    """
    de_by_guid = {article["guid"]: article for article in articles_de}
    en_guids = {article["guid"] for article in articles_en}

    items = [_build_news_item(en, de_by_guid.get(en["guid"])) for en in articles_en]
    items.extend(_build_news_item(None, de) for de in articles_de if de["guid"] not in en_guids)
    return items


def get_rss_news_data() -> list[dict[str, Any]]:
    """Fetch both HeX RSS news feeds and merge them into bilingual items.

    Returns a list of dicts with keys: ``name``, ``text_content``, ``metadata``.

    Either feed failing raises rather than storing English-only items: that would change every
    article's content_hash, re-embedding the whole feed now and again once the German feed is back.
    """
    articles_en = parse_rss_feed(fetch_rss_feed(RSS_FEED_URL))
    articles_de = parse_rss_feed(fetch_rss_feed(RSS_FEED_URL_DE))
    return build_news_items(articles_en, articles_de)


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
    """Fetch both RSS feeds and bring *knowledge* in line with them.

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
