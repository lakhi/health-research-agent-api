"""
Build the inline-excerpt `citations` payload for SSC-Psych responses.

Operates on Agno's `RunOutput.references` (list of MessageReferences), each of
which carries a list of retrieved-chunk dicts produced by Document.to_dict()
(`name`, `meta_data`, `content`). Agno's Document.to_dict() does not surface
the retrieval/reranking score, so dedup falls back to first-seen per URL —
which is equivalent because Agno returns chunks ordered by relevance.

Excerpts are claim-anchored: keywords from the answer sentence that cites the
source (weight 2) plus the user query (weight 1) compete for the densest
window in the chunk, and the citation's own title words are barred from
anchoring (titles repeat in header/nav boilerplate — the exact text a chip
should not quote).
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
        "mich",
        "dich",
        "sich",
        "uns",
        "euch",
        "ihr",
        "ihre",
        "ihren",
        "ihrem",
        "ihrer",
        "ihres",
        "sie",
        "wir",
        "mir",
        "dir",
        "ihm",
        "ihn",
        "ihnen",
        "mein",
        "meine",
        "man",
        "sein",
        "seine",
        "dies",
        "diese",
        "diesen",
        "dieser",
        "dieses",
        "kann",
        "muss",
        "soll",
        "wird",
        "werden",
        "wurde",
        "können",
        "müssen",
        "sollen",
        "möchte",
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
        "my",
        "your",
        "our",
        "their",
        "them",
        "this",
        "these",
        "those",
        "there",
        "will",
        "would",
        "can",
        "could",
        "should",
        "shall",
        "must",
        "may",
        "might",
        "does",
        "did",
        "been",
        "being",
        "about",
    }
)


_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
_URL_RE = re.compile(r"https?://\S+")


def _claim_text_for_url(answer_text: Optional[str], source_url: str) -> Optional[str]:
    """The answer line that cites `source_url`, stripped of link markup and URLs.

    This is the claim the citation supports, so its words are the best anchor
    for the excerpt window. Returns None when the URL is absent or the line
    carries no prose beyond the link itself (a bare citation bullet).
    """
    if not answer_text:
        return None
    for line in answer_text.splitlines():
        if source_url not in line:
            continue
        cleaned = _MD_LINK_RE.sub(" ", line)
        cleaned = cleaned.replace(source_url, " ")
        cleaned = _URL_RE.sub(" ", cleaned)
        cleaned = cleaned.strip()
        return cleaned or None
    return None


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


def extract_excerpt(
    chunk_content: str,
    query: str,
    max_chars: int = 200,
    claim_text: Optional[str] = None,
    exclude_tokens: Optional[Iterable[str]] = None,
) -> str:
    """Verbatim window from chunk_content around the densest keyword cluster.

    Keywords come from the answer sentence citing this source (`claim_text`,
    weight 2) and the user query (weight 1). Each keyword occurrence anchors a
    candidate window; the window with the highest sum of *distinct* keyword
    weights wins (earliest anchor on ties), so one ubiquitous term repeated in
    boilerplate never outranks an information-rich cluster. `exclude_tokens`
    (the citation's title words) cannot anchor a window — titles repeat in page
    headers/nav text, and the chip already sits under the titled link. Falls
    back to the leading max_chars when nothing matches.
    """
    if not chunk_content:
        return ""

    content = chunk_content.strip()
    if len(content) <= max_chars:
        return _WHITESPACE_RE.sub(" ", content).strip()

    excluded = {tok.lower() for tok in (exclude_tokens or ())}
    weights: dict[str, int] = {}
    for kw in _query_keywords(query):
        if kw not in excluded:
            weights[kw] = 1
    for kw in _query_keywords(claim_text or ""):
        if kw not in excluded:
            weights[kw] = 2

    lowered = content.lower()
    occurrences: list[tuple[int, str]] = []
    for kw in weights:
        pos = lowered.find(kw)
        while pos != -1:
            occurrences.append((pos, kw))
            pos = lowered.find(kw, pos + 1)

    if not occurrences:
        if excluded:
            # Retry with title tokens allowed: a title-anchored window is
            # weaker, but still better than the blind leading window.
            return extract_excerpt(content, query, max_chars, claim_text=claim_text)
        window = content[:max_chars]
        return _WHITESPACE_RE.sub(" ", window).strip() + "…"

    occurrences.sort()
    lead = max_chars // 4  # anchor sits a quarter in, so context reads forward

    best_start = 0
    best_score = -1
    for anchor, _kw in occurrences:
        w_start = anchor - lead
        w_end = w_start + max_chars
        in_window = {kw for pos, kw in occurrences if w_start <= pos < w_end}
        score = sum(weights[kw] for kw in in_window)
        if score > best_score:
            best_score = score
            best_start = w_start

    start, end = _snap_to_whitespace(content, best_start, best_start + max_chars)

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
    answer_text: Optional[str] = None,
) -> list[dict]:
    """Flatten Agno references into a deduplicated citation list.

    - Skips chunks whose `meta_data` lacks `source_url` (so VAX / HeX-GiG
      chunks silently produce no citations).
    - Dedup key: `source_url`. First-seen wins, because Agno returns chunks
      in relevance order.
    - `score` is derived from rank (top = 1.0) since Document.to_dict() does
      not expose the retrieval score.
    - `answer_text` (the agent's full reply) anchors each excerpt on the
      claim sentence that cites the source; title words never anchor.
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
        excerpt = extract_excerpt(
            content,
            query,
            max_chars=max_excerpt_chars,
            claim_text=_claim_text_for_url(answer_text, source_url),
            exclude_tokens=_TOKEN_RE.findall(str(title).lower()),
        )

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
