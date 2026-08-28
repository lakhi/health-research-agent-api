"""Deterministic (non-semantic) tools for the HeX-GiG agent.

Vector search ranks by topic similarity, which is orthogonal to recency: asking it for "the
latest news" returns the ten articles most *similar to the phrase* "latest news", and the newest
article is rarely among them. Temporal questions need a temporal query, so this module answers
them straight from the news metadata instead.
"""

import logging
from email.utils import parsedate_to_datetime

from sqlalchemy import text

from db.session import get_engine
from knowledge_base.hex_gig_knowledge_base import HEX_GIG_EMBEDDINGS_TABLE, HEX_GIG_VECTOR_SCHEMA

logger = logging.getLogger(__name__)

MAX_LATEST_NEWS = 20

# `meta_data @> ...` is the same containment predicate agno's own filtered search uses, so this
# reads exactly the rows the knowledge base considers news articles.
_LATEST_NEWS_SQL = text(
    f"""
    SELECT meta_data->>'guid'         AS guid,
           meta_data->>'title'        AS title,
           meta_data->>'pub_date_iso' AS pub_date_iso,
           meta_data->>'pub_date'     AS pub_date,
           meta_data->>'link'         AS link,
           content                    AS content
    FROM {HEX_GIG_VECTOR_SCHEMA}.{HEX_GIG_EMBEDDINGS_TABLE}
    WHERE meta_data @> '{{"source_type": "news_article"}}'::jsonb
    """
)


def _sort_date(pub_date_iso: str | None, pub_date: str | None) -> str:
    """Return a sortable YYYY-MM-DD date, parsing the RFC-2822 pubDate as a fallback.

    Articles ingested before pub_date_iso existed have no ISO field, so the fallback keeps
    ordering correct across the transition rather than dumping them all at the bottom.
    """
    if pub_date_iso:
        return pub_date_iso
    if pub_date:
        try:
            return parsedate_to_datetime(pub_date).date().isoformat()
        except (TypeError, ValueError):
            logger.warning("Unparseable pub_date on a news row: %r", pub_date)
    return ""


def get_latest_hex_news(limit: int = 8) -> str:
    """Return the most recently published GiG network news articles, newest first.

    Use this for any question about the latest, most recent, newest, current or upcoming news,
    events, or network activities, and whenever the user asks what happened in a given month or
    year. It orders by publication date, which searching the knowledge base cannot do.

    Args:
        limit: How many articles to return, from 1 to 20. Defaults to 8.

    Returns:
        The articles as readable text, each with its title, publication date and link.
    """
    limit = max(1, min(int(limit), MAX_LATEST_NEWS))

    try:
        with get_engine().connect() as connection:
            rows = connection.execute(_LATEST_NEWS_SQL).mappings().all()
    except Exception:
        logger.exception("Could not read the latest GiG news")
        return "The news archive could not be reached just now. Please try again in a moment."

    # One article can span several chunks; collapse them back into a single entry per guid.
    articles: dict[str, dict[str, str]] = {}
    for row in rows:
        guid = row["guid"] or row["title"] or ""
        article = articles.setdefault(
            guid,
            {
                "title": row["title"] or "Untitled",
                "date": _sort_date(row["pub_date_iso"], row["pub_date"]),
                "link": row["link"] or "",
                "body": "",
            },
        )
        chunk = (row["content"] or "").strip()
        if chunk:
            article["body"] = f"{article['body']}\n{chunk}".strip()

    newest = sorted(articles.values(), key=lambda a: a["date"], reverse=True)[:limit]
    if not newest:
        return "No news articles are currently stored in the knowledge base."

    blocks = []
    for article in newest:
        header = f"{article['title']} (published {article['date'] or 'date unknown'})"
        if article["link"]:
            header = f"{header}\nLink: {article['link']}"
        blocks.append(f"{header}\n{article['body']}".strip())

    return f"The {len(newest)} most recent GiG news articles, newest first:\n\n" + "\n\n---\n\n".join(blocks)
