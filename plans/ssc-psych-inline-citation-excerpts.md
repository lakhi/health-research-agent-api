# Phase-1 Feature — Inline source excerpts under each SSC-Psych citation

> Status: **design only — not yet implemented** (phase-1 blocking for SSC public launch)
> Related issue: [#19](https://github.com/lakhi/health-research-agent-api/issues/19) — SSC Psychologie agent (WIP)
> Inspiration: Robert Böhm's "quality check" requirement (`it would be great if any information provided by the chatbot would be referenced to the associated material — this is also important as a quality check`). Dash's grounded-citation pattern; Scout's web-search Citation objects.

## Context

The SSC-Psych agent already emits `[Page Title](source_url)` inline markdown citations (enforced by the `<citation_format>` block in `agents/ssc_psych_agent.py`). A bare link forces the reader to click through to verify the claim — too high-friction to serve as a real *quality check*. This feature adds a short verbatim excerpt of the retrieved chunk under each cited link so the reader can verify the source supports the claim without leaving the chat.

The agent already retrieves chunks via Agno; the chunk text + metadata is exposed on `RunOutput.references` (`agno/run/agent.py:648`, `agno/models/message.py:13`). The plan exposes those existing references as a typed `citations` array on the response payload and documents the UI contract.

## Design decisions (locked in)

| Decision | Choice | Reasoning |
|---|---|---|
| Excerpt placement | Inline under each cited link (UI-rendered) | Reader-friendly; doesn't fragment the answer into "answer + sources block" |
| Excerpt text source | Backend, verbatim from retrieved chunk content | Guaranteed faithful — no risk of LLM paraphrasing the quote. Robert's "quality check" only holds if the excerpt is exactly what the page says. |
| Cross-walk key | `source_url` exact match between answer markdown links and `citations[].source_url` | The prompt already mandates this URL shape; no agent-prompt change needed for matching |
| Excerpt length | ~200 chars max, single contiguous window | Long enough to verify context; short enough not to clutter |
| Multiple chunks per URL | Keep only the highest-scoring chunk per `source_url` | Avoids redundancy; one excerpt per cited link |
| Duplicate inline mentions of same URL | UI shows excerpt only on first mention | Subsequent mentions get a bare link; avoids visual repetition |
| Streaming behaviour | Emit a final `citations` SSE event after content finishes streaming | Don't make the user wait for citations before content renders |
| Scope | SSC-Psych project only at first; same machinery available to VAX / HeX-GiG if/when they want it | Don't fork the response shape per-project; just don't surface UI rendering for projects that haven't opted in |

## Changes

### 1. New utility — `services/citations_service.py`

Pure functions (no I/O), easy to unit-test:

```python
def build_citations(
    references: list[MessageReferences] | None,
    query: str,
    max_excerpt_chars: int = 200,
) -> list[dict]:
    """
    Flatten Agno's MessageReferences into a deduplicated, ranked citation list.

    Returns a list of {source_url, title, source_type, language, excerpt, score}
    dicts, deduped by source_url (keeping the highest-scoring chunk per URL).
    """

def extract_excerpt(chunk_content: str, query: str, max_chars: int = 200) -> str:
    """
    Return a ~max_chars verbatim window from chunk_content centered on the
    strongest term overlap with `query`. Falls back to the leading max_chars
    if no overlap. Strips excessive whitespace and adds ellipses on truncation.
    """
```

Excerpt selection algorithm (simple and predictable):
1. Tokenize `query`, drop stopwords + tokens < 3 chars.
2. For each query term, find first occurrence in `chunk_content` (case-insensitive).
3. Pick the earliest match; centre a `max_chars` window on it.
4. Snap window boundaries to nearest sentence/whitespace if possible.
5. Prepend/append `…` if truncated. Collapse internal whitespace.
6. If no terms match, return `chunk_content[:max_chars]` with trailing `…`.

### 2. Backend — extend the response payload

**`api/routes/agents.py`** — three edits:

1. **Non-streaming path** (around line 196-200): build citations from `response.references` and inject into `response_payload`:
   ```python
   from services.citations_service import build_citations

   response_payload = response.to_dict() if hasattr(response, "to_dict") else {"content": ...}
   response_payload["citations"] = build_citations(
       getattr(response, "references", None),
       query=run_request.message,
   )
   ```

2. **Streaming path** — in `chat_response_streamer` (line 29-94): after the `async for chunk in run_response` loop completes, locate the final `RunOutput` and emit a `citations` SSE event before the function returns:
   ```python
   # After the stream loop, before metrics recording
   final_references = getattr(chunk, "references", None) if chunk else None
   citations = build_citations(final_references, query=message)
   yield f"event: citations\ndata: {json.dumps({'citations': citations})}\n\n"
   ```
   *Note*: Agno's streaming yields different event types; the final `RunOutputCompletedEvent` carries `references`. Verify the exact event class name during implementation (`agno/run/agent.py`).

3. **No prompt change.** The existing `<citation_format>` block already mandates `[Title](source_url)`. The backend's job is to *expose* the chunk metadata it already retrieves; the agent's job stays the same.

### 3. Prompt — minor reinforcement (one line)

**`agents/ssc_psych_agent.py`** — append one line to `<citation_format>`:

> Always use the exact `source_url` value from the retrieved chunk's metadata as the link target — do not modify, shorten, or fabricate URLs.

This is *implicit* today but worth making explicit so the URL cross-walk between answer text and `citations` is reliable.

### 4. UI contract (separate UI repo — documented here only)

The `health-research-agent-ui` repo will need a separate PR. Document in the backend PR description and link to this file:

| Field | Value |
|---|---|
| New response field | `citations: Citation[]` on the JSON response, and an `event: citations` SSE frame in the streamed response (after `content` events finish, before the stream closes) |
| `Citation` shape | `{ source_url: string, title: string, source_type: "web_page" \| "pdf_document" \| "curated_faq", language: "de" \| "en", excerpt: string, score: number }` |
| Rendering rule | While rendering the markdown answer, for each `[text](url)` inline link, look up `url` in `citations`. On the *first* occurrence of that URL, render the excerpt block immediately below the link's containing paragraph. Subsequent occurrences of the same URL render as plain links. |
| Excerpt block styling | Indented blockquote or muted-italic block; max 2 lines visually; show language badge if non-default |
| Backwards compat | Old clients ignore `citations`; backend never omits the field but may return an empty array |
| Empty/error case | If `citations` is empty (e.g. agent refused, no knowledge retrieved), render the answer with bare links only |

## Files touched

| File | Change |
|---|---|
| `services/citations_service.py` | **NEW** — `build_citations`, `extract_excerpt` utility functions |
| `tests/services/test_citations_service.py` | **NEW** — unit tests for excerpt extraction (windowing, ellipses, no-match fallback, dedup) |
| `api/routes/agents.py` | Inject `citations` into non-streaming JSON response; emit `event: citations` SSE event at end of stream |
| `agents/ssc_psych_agent.py` | One-line prompt reinforcement in `<citation_format>` |

## Verification plan

1. **Unit tests** for `citations_service`:
   - Window centered on the matched keyword.
   - Ellipses prepended/appended only when truncated.
   - Dedup keeps highest score per `source_url`.
   - No-keyword-match falls back to leading window.
   - Empty/None references returns `[]`.

2. **Manual integration** — run SSC agent locally with a few representative questions:
   ```bash
   curl -sS -X POST http://localhost:8000/v1/agents/ssc-psych-agent/runs \
     -H "Content-Type: application/json" \
     -d '{"message":"Wie bewerbe ich mich für den Bachelor Psychologie?","stream":false}' | jq '.citations'
   ```
   Expect: array of citations with `excerpt` matching verbatim from the source PDF/page. Spot-check that the `source_url` values in `citations` also appear as `[…](url)` links in `content`.

3. **Streaming smoke test** — confirm a final SSE event of type `citations` appears after content events:
   ```bash
   curl -sN -X POST http://localhost:8000/v1/agents/ssc-psych-agent/runs \
     -H "Content-Type: application/json" \
     -d '{"message":"What are the admission requirements?","stream":true}'
   ```

4. **Refusal case** — ask an out-of-scope question; expect `citations: []` and the existing refuse-and-redirect message in `content`.

5. **Lint/type**: `ruff check .` and `mypy . --config-file pyproject.toml`.

## Coordination dependency

Phase-1 launch is blocked on **both** PRs landing:
- Backend PR (this plan) — adds `citations` field.
- UI PR (separate repo) — renders inline excerpts.

Without the UI work, the backend change is invisible to users and the quality-check requirement isn't met. Surface the UI dependency in the backend PR description.

## Non-goals / explicitly out of scope

- LLM-generated excerpts. Backend-verbatim only.
- "Sources" block at bottom of answer. Inline placement only.
- Tooltip/hover rendering. Inline block only (mobile-friendly).
- Reranking the retrieved chunks. Trust Agno's score ordering as-is.
- Citation excerpts for VAX / HeX-GiG. Same machinery available, but UI rendering opt-in per project.
- Cross-walk by anything other than `source_url`. (No fuzzy title matching; URL is the contract.)
