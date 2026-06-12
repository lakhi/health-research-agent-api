"""
Build the inline-excerpt `citations` payload for SSC-Psych responses.

Operates on Agno's `RunOutput.references` (list of MessageReferences), each of
which carries a list of retrieved-chunk dicts produced by Document.to_dict()
(`name`, `meta_data`, `content`). Agno's Document.to_dict() does not surface
the retrieval/reranking score, so dedup falls back to first-seen per URL —
which is equivalent because Agno returns chunks ordered by relevance.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Optional

# Minimal bilingual stopword union — kept inline to avoid a new dependency.
_STOPWORDS: frozenset[str] = frozenset(
    {
        # German
        "der",
        "die",
        "das",
        "den",
        "dem",
        "des",
        "ein",
        "eine",
        "einen",
        "einem",
        "einer",
        "und",
        "oder",
        "aber",
        "wenn",
        "weil",
        "dass",
        "ich",
        "ist",
        "sind",
        "war",
        "hat",
        "habe",
        "haben",
        "wie",
        "was",
        "wer",
        "wo",
        "wann",
        "warum",
        "mit",
        "auf",
        "für",
        "von",
        "zu",
        "bei",
        "aus",
        "nach",
        "über",
        "unter",
        "nicht",
        "auch",
        "nur",
        "schon",
        # English
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "if",
        "because",
        "that",
        "is",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "how",
        "what",
        "who",
        "where",
        "when",
        "why",
        "with",
        "on",
        "for",
        "of",
        "to",
        "in",
        "at",
        "from",
        "by",
        "not",
        "also",
        "only",
        "i",
        "you",
        "we",
        "they",
        "he",
        "she",
        "it",
    }
)


_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


def _query_keywords(query: str) -> list[str]:
    """Lowercase, deduped, stopword-stripped tokens of length >= 3."""
    seen: set[str] = set()
    out: list[str] = []
    for tok in _TOKEN_RE.findall(query.lower()):
        if len(tok) < 3 or tok in _STOPWORDS or tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def _snap_to_whitespace(text: str, start: int, end: int) -> tuple[int, int]:
    """Expand/contract [start, end) outward to nearest whitespace boundaries."""
    n = len(text)
    s = max(0, start)
    e = min(n, end)
    while s > 0 and not text[s - 1].isspace():
        s -= 1
    while e < n and not text[e].isspace():
        e += 1
    return s, e


def extract_excerpt(chunk_content: str, query: str, max_chars: int = 200) -> str:
    """Verbatim window from chunk_content centered on the earliest query-term match.

    Falls back to the leading max_chars when no query terms match. Internal
    whitespace is collapsed; ellipses are added only at truncation boundaries.
    """
    if not chunk_content:
        return ""

    content = chunk_content.strip()
    if len(content) <= max_chars:
        return _WHITESPACE_RE.sub(" ", content).strip()

    keywords = _query_keywords(query)
    lowered = content.lower()

    match_pos: Optional[int] = None
    for kw in keywords:
        pos = lowered.find(kw)
        if pos != -1 and (match_pos is None or pos < match_pos):
            match_pos = pos

    if match_pos is None:
        window = content[:max_chars]
        return _WHITESPACE_RE.sub(" ", window).strip() + "…"

    half = max_chars // 2
    raw_start = match_pos - half
    raw_end = raw_start + max_chars
    start, end = _snap_to_whitespace(content, raw_start, raw_end)

    excerpt = content[start:end]
    excerpt = _WHITESPACE_RE.sub(" ", excerpt).strip()

    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(content) else ""
    return f"{prefix}{excerpt}{suffix}"


def _chunk_meta(chunk: Any) -> tuple[Optional[str], dict, str]:
    """Extract (name, meta_data, content) from a chunk dict-or-string."""
    if isinstance(chunk, dict):
        return chunk.get("name"), chunk.get("meta_data") or {}, chunk.get("content") or ""
    if isinstance(chunk, str):
        return None, {}, chunk
    return None, {}, str(chunk)


def _iter_chunks(references: Any) -> Iterable[Any]:
    """Yield each retrieved-chunk entry from `RunOutput.references`.

    `references` is `List[MessageReferences]`; each carries its own
    `references: List[Dict | str]` of chunks. Tolerates None / mixed shapes.
    """
    if not references:
        return
    for msg_refs in references:
        inner = getattr(msg_refs, "references", None)
        if inner is None and isinstance(msg_refs, dict):
            inner = msg_refs.get("references")
        if not inner:
            continue
        for chunk in inner:
            yield chunk


def build_citations(
    references: Any,
    query: str,
    max_excerpt_chars: int = 200,
) -> list[dict]:
    """Flatten Agno references into a deduplicated citation list.

    - Skips chunks whose `meta_data` lacks `source_url` (so VAX / HeX-GiG
      chunks silently produce no citations).
    - Dedup key: `source_url`. First-seen wins, because Agno returns chunks
      in relevance order.
    - `score` is derived from rank (top = 1.0) since Document.to_dict() does
      not expose the retrieval score.
    """
    seen: set[str] = set()
    ordered: list[dict] = []

    for chunk in _iter_chunks(references):
        name, meta, content = _chunk_meta(chunk)
        source_url = meta.get("source_url")
        if not source_url or source_url in seen:
            continue
        seen.add(source_url)

        title = meta.get("page_title") or meta.get("document_title") or name or source_url
        source_type = meta.get("source_type") or "web_page"
        language = meta.get("language") or "de"
        excerpt = extract_excerpt(content, query, max_chars=max_excerpt_chars)

        ordered.append(
            {
                "source_url": source_url,
                "title": title,
                "source_type": source_type,
                "language": language,
                "excerpt": excerpt,
            }
        )

    total = len(ordered)
    if total == 0:
        return []
    for rank, citation in enumerate(ordered):
        citation["score"] = round(1.0 - (rank / total), 4)
    return ordered


def format_citations_sse(citations: list[dict]) -> str:
    """Render the terminal Citations SSE frame for the streaming response.

    The agent-ui stream parser (useAIResponseStream.parseBuffer) does not parse
    SSE framing — it extracts bare JSON objects from the byte stream and routes
    on the `event` key *inside* the JSON, mirroring how Agno embeds the event
    name in every frame's payload. The `event: Citations` header line alone is
    discarded by that parser, so the payload must carry the key too.
    """
    payload = json.dumps({"event": "Citations", "citations": citations})
    return f"event: Citations\ndata: {payload}\n\n"
