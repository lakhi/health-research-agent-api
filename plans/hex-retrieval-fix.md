# Fix: HeX misses knowledge it holds — invented filter values and single-source scoping (issue #47)

## Context

Asked *"are there any professors who have won some grants?"*, the HeX agent answers
*"I don't have information about professors in the GiG network who have won grants in my
current knowledge base"* — while the RSS feed holds **LEO Foundation grant for David Gómez
Varela** (2026-08-12) and **ÖAW APART scholarship for Johanna Chovanec**, and the paper
corpus holds funding-acknowledgement sections for Böttcher, Bergheim, Schwab and others.

Reproduced three times against the live deployment (`hex-gig-agent-api--gh-118-1`) on
2026-09-13. There are **two independent causes**, and the reported symptom comes from the
one that is *not* about integrating the three knowledge sources.

## Cause A — invented filter *values* return zero rows, silently

```
TOOL: search_knowledge_base
ARGS: {"query": "grant", "filters": [{"key": "academic_position", "value": "Professor"}]}
TOOL RESULT: "No documents found"
```

`academic_position` never holds the bare string `"Professor"`. Across the 84 members:
`Full Professor` (18), *empty* (17), `University Assistant (post doc)` (15),
`Associate Professor/Ao. Professor` (13), `Assistant Professor` (10), `Scientific Staff` (5),
`Senior Scientist` (4), `Senior Lecturer` (1), `University Assistant (prae doc)` (1).

Dict filters reach pgvector as JSONB containment —
`stmt.where(self.table.c.meta_data.contains(filters))`
(`.venv/.../agno/vectordb/pgvector/pgvector.py:988`) — i.e. exact string equality. No
substring, no case folding. The filter matched nothing, so the vector search never ran
against a candidate set.

Two things make this silent rather than loud:

1. **Agno validates filter keys, never values.** `Knowledge._validate_filters`
   (`.venv/.../agno/knowledge/knowledge.py:1129-1160`) only checks
   `base_key in valid_metadata_filters`. `academic_position` *is* a harvested key, so
   `"Professor"` passed through untouched. A bad key is dropped with a warning; a bad
   *value* yields an empty result set indistinguishable from an empty knowledge base.
2. **News rows have no `academic_position` key at all** (`guid, title, link, pub_date,
   pub_date_iso, language, source_type, image_url, content_hash`). Containment on an absent
   key never matches, so the LEO article was structurally unreachable for this query.

**The trap inside the trap:** David Gomez Varela, who actually won the LEO grant, is a
`Senior Scientist`. Even a correctly spelled `academic_position: "Full Professor"` filter
would have excluded him. Role words in this corpus cannot be answered by filtering on role.

### Where the pressure comes from

`enable_agentic_knowledge_filters=True` (`agents/hex_gig_agent.py:43`) makes agno inject,
with our ~19 metadata keys interpolated:

> "Always use filters when the user query indicates specific metadata… **Use the most
> specific filter(s) possible to narrow down results**… you MUST use the
> search_knowledge_base tool with the filters parameter set to
> `{'<valid key>': '<valid value based on the user query>'}`"

It advertises keys but never legal values — "valid value based on the user query" is an
explicit instruction to invent one.

Our own prompt pushes the same way: `<search_strategy>` currently says *"also use
`faculty_affiliation` or `discipline` metadata filters to narrow results"*. `discipline`
holds values like `Molecular Nutritional Science`, so a user asking about "nutrition" gets
a zero-row filter. **The current instructions steer into the bug alongside agno's.**

## Cause B — single-source scoping loses the other two sources

Second probe, *"what grants have network members received?"*:

```
ARGS: {"query": "grant funding awards", "filters": [{"key": "source_type", "value": "research_paper"}]}
TOOL RESULT: 10,903 chars -> a good, well-cited answer
```

Correct filter, useful answer — and the LEO news item still absent, excluded by
`source_type`. Our `<search_strategy>` frames `source_type` as a routing decision ("use X
*for* questions about Y"), so each question gets scoped to one source; nothing pushes
toward breadth.

**A caused the reported symptom; B is a second, independent gap.** Fixing B alone leaves
the reported case unchanged — a zero-row `academic_position` filter fails regardless of
fan-out.

Third probe confirmed the news side is reachable: *"is there any network news about grants
or funding awards?"* routed to `get_latest_hex_news` and found LEO immediately. The whole
feed is only 42 articles.

## Done so far

- **Issue [#47](https://github.com/lakhi/health-research-agent-api/issues/47)** opened with
  the full trace evidence.
- **`tests/evals/test_hex_gig_retrieval_evals.py`** written (uncommitted). Six cases,
  `ruff` and `mypy` clean, collects cleanly.
- **`health-research-agent-api-api-1`** (the idle ssc-psych container) stopped and removed.
  `health-research-agent-api-pgvector-1` deliberately kept — the evals need it and its
  `health-research-agent-api_pgdata` volume also holds the SSC-Psych and NEX embeddings.

### Why the eval gate asserts on the retrieval trace, not on prose

Every other file in `tests/evals/` uses `AccuracyEval` with an LLM judge — right for "did
the answer convey all three severity tiers", wrong here. These failures are mechanical and
visible in `response.tools` before they reach the answer: a filter key that should not be
used, a search that came back `"No documents found"` with no retry, a `source_type` that
never appeared in any retrieved chunk. Reading `ToolExecution.tool_args` and
`json.loads(ToolExecution.result)` keeps the gate deterministic, judge-token-free, and makes
failures name the offending filter instead of a score.

The six cases:

| case | asserts | must_pass |
|---|---|---|
| `grants_across_sources` | the reported question retrieves *something* from papers, no free-text filter, no "I don't have information" | 5/5 |
| `grants_surface_news_too` | the same question puts a `news_article` chunk in the trace | **3/5 — the tier-2 ratchet** |
| `role_word_does_not_empty_the_search` | "postdocs … nutrition" does not produce an all-empty search | 4/5 |
| `member_spans_papers_and_news` | "David Gomez Varela's work" reaches the paper corpus | 4/5 |
| `recency_still_routes_to_news_tool` | regression guard for #45 — "latest news" still calls `get_latest_hex_news` | 5/5 |
| `faculty_filter_still_works` | `faculty_affiliation` stays usable; the fix narrows *which* keys, it does not ban filtering | 5/5 |
| `honest_when_the_gap_is_real` | quantum computing still gets an honest no + redirect — the retry clause must not become invention | 5/5 |

`grants_surface_news_too` at 3/5 is deliberate: tier 1 only nudges a model that still picks
its own filters. **Raise it to 5/5 when tier 2 lands** — that threshold is the measurable
definition of "the integration actually happened".

## BLOCKER — the local eval corpus load failed. Start here tomorrow.

The evals need `ai.hex_gig_embeddings` in the local pgvector; it did not exist. A one-off
loader was run at 22:55 on 2026-09-13 and **failed partway with embedding timeouts**.

State left in the local DB (deliberately not cleaned up, so it can be inspected):

| | |
|---|---|
| `ai.hex_gig_embeddings` | 2,955 chunks, only **9 distinct document names** |
| `ai.hex_gig_contents` | 26 `completed`, 23 `failed`, 1 `processing` |
| Failures | 1,671 × `Error embedding document N: Failed to generate embedding: Request timed out.` |
| First failure | document 21 of 126 (`HeX Research - David Gomez Varela`) |
| Log | was in the session scratchpad; re-running regenerates it |

**Do not simply re-run the loader.** `knowledge.ainsert(..., skip_if_exists=True)` keys on
the content hash, and 26 documents are already marked `completed` despite several having no
chunks — a naive resume would skip them and bake the holes in permanently. This is the same
hazard CLAUDE.md already records: *"drop and reload rather than relying on the skip."*

### Resume procedure

1. **Drop the partial HeX tables** (local pgvector only — leaves SSC/NEX untouched):
   ```bash
   docker exec health-research-agent-api-pgvector-1 psql -U ai -d ai \
     -c "drop table if exists ai.hex_gig_embeddings; drop table if exists ai.hex_gig_contents;"
   ```
2. **Diagnose the timeouts before re-running.** The embedder is
   `embedding-3-large-vax-study` on `az-openai-vax-models.openai.azure.com` — the shared VAX
   account. Its deployment is `DataZoneStandard` with capacity **1005**, so a hard quota
   wall is *not* the obvious explanation; suspect client-side request timeout or burst
   throttling under 126 back-to-back documents. Worth trying, in order:
   - pass a longer `timeout` / `max_retries` into `AzureOpenAIEmbedder` via `client_params`
     in `knowledge_base/__init__.py`
   - check Azure metrics on the deployment for 429s during the 22:55–23:26 window
   - if it is throttling, load in batches with a pause between members rather than in one
     continuous run
3. **Re-run the loader.** The 128 cached PDFs in `hex_gig_pdfs_cache/` are bind-mounted to
   `/app/hex_gig_pdfs_cache` by `compose.yaml`, so no u:Cloud download happens. The
   `-e` overrides win over `.env` because `load_dotenv()` does not override real env vars.
   ```bash
   docker compose run --rm \
     -e PROJECT_NAME=hex-gig -e LOAD_HEX_GIG_KNOWLEDGE=true \
     api python -c "$(cat <<'PY'
   import asyncio
   from dotenv import load_dotenv
   load_dotenv()
   from api.project_configs import get_project_config
   config = get_project_config()
   asyncio.run(config.load_knowledge(config.get_agents()))
   print("HEX_LOAD_DONE", flush=True)
   PY
   )"
   ```
4. **Verify before trusting it**: 126 documents `completed`, 0 `failed`, ~39 distinct
   `HeX Research -` names, plus 42 news articles and 84 member profiles.

Alternative if the local load stays painful: extend the `akshays_macbookpro` firewall rule
on `hex-gig-postgres-db` (currently `41.66.96.0/24`; the laptop was at `41.66.99.161`) and
run the evals read-only against the prod corpus. Faster, but adds query load to the B1ms
server that #42 already flags as slow.

## Tier 1 — prompt only (drafted, NOT applied)

Run the six evals against the **unmodified** prompt first to get a baseline, then swap the
`<search_strategy>` block in `agents/hex_gig_agent.py` for the version below and re-run.
Three changes: ban free-text filter keys, port SSC's retry clause, reframe `source_type`
from routing to coverage.

```
<search_strategy>
CRITICAL: You MUST call a knowledge tool — search_knowledge_base, or
get_latest_hex_news for the recency questions described below — before
answering ANY question, even if the answer seems obvious from your
instructions. Never respond with member names, research topics, or network
details without first retrieving them.
- Default to breadth. A question belongs to a single source only when it says
  so; most are answered better by searching more than one:
  - "research_paper" — expertise, publications, methods, collaborations
  - "news_article" — events, outreach, awards, grants, appointments
  - "member_profile" — who is in the network, counts, members by faculty
  Grants, prizes and appointments appear in BOTH papers (in funding
  acknowledgements) and news (in announcements): search both before answering.
- Only `source_type` and `faculty_affiliation` may be used as filters. NEVER
  filter on `academic_position`, `discipline` or `department_affiliation` —
  these hold free text written per member, a filter matches only the exact
  stored string, and a near miss returns nothing at all rather than something
  close. Words like "professors", "postdocs" or "nutrition" describe what you
  are looking for: put them in the query text, never in a filter.
- If a filtered search returns no documents, retry the SAME query WITHOUT any
  filters before concluding that no information is available. An empty result
  usually means the filter was wrong, not that the knowledge base is empty.
- For questions about a specific faculty, add the `faculty_affiliation` filter.
- For "list all members" questions: state the total count, then perform
  multiple searches using faculty_affiliation filters to retrieve members
  in batches (your search returns at most 10 results per query). Organise
  results by faculty.
- If initial results seem sparse, try broadening your search with related
  terms before concluding that no information is available.
- For queries about the "latest", "most recent", "newest", "current" or
  upcoming news and events, or about what happened in a given month or year:
  call get_latest_hex_news. Do NOT use search_knowledge_base for these.
  Search ranks by topic similarity, which says nothing about publication
  date, so it cannot tell you which article is the most recent.
</search_strategy>
```

The retry clause is lifted from `agents/ssc_psych_agent.py:149-152`, which already carries
it from the SSC retrieval RCA. Same bug class; the lesson was never propagated to HeX.

Three clauses land together, against the usual "one clause at a time" rule, because they
are one coherent fix for one issue. If a case regresses, bisect them.

## Tier 2 — own the retrieval (this *is* the knowledge-source integration)

Turn `enable_agentic_knowledge_filters` off and replace the generic tool with a
project-owned `search_hex_knowledge(query)` that runs three scoped searches and returns
labelled sections with fixed quotas (e.g. 5 papers / 3 news / 3 profiles). The model then
never writes a filter, and integration becomes structural instead of hoped-for.

- **Per-source quotas beat one shared pool.** Dropping filters entirely will not work:
  ~15k paper chunks, many of them funding acknowledgements that say "grant" repeatedly,
  versus ~100 news chunks. They saturate the 50-candidate rerank pool
  (`RERANK_CANDIDATE_POOL` in `knowledge_base/rerankers.py`) before the reranker ever sees
  the LEO article.
- **Cost is 3× per search** — three embeddings, three pgvector queries, three billed Cohere
  rerank units. Check against the daily EUR budget and against
  [#42](https://github.com/lakhi/health-research-agent-api/issues/42) (long retrieval time).
  A single-embedding / `source_type IN (...)` / window-function variant avoids the
  multiplier at the price of hand-written SQL. Note `PgVector._dsl_to_sqlalchemy` already
  supports `IN`, `OR` and `AND` via `agno.filters` — but the *agentic* tool path flattens
  everything to a dict (`_default_tools._resolve_filters`), so only a project-owned tool can
  reach that DSL.

## Open questions

- Why did the embedder time out? Quota is not obviously the constraint (capacity 1005).
- Should `member_profile` always be in the fan-out, or only when the query mentions people?
- Should the fan-out quotas be fixed, or proportional to how many results each source
  returns above a similarity floor?
