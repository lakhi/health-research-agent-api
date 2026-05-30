# Future Features — SSC-Psych Phase-2 Enhancements

> Status: **design only — not yet implemented**
> Related issue: [#19](https://github.com/lakhi/health-research-agent-api/issues/19) — SSC Psychologie agent (WIP)
> Inspiration sources: [`agno-agi/dash`](https://github.com/agno-agi/dash), [`agno-agi/scout`](https://github.com/agno-agi/scout), Ashpreet Bedi's [SQL agent article](https://www.ashpreetbedi.com/articles/sql-agent)

## Context

Phase-1 (issue #19) ships the SSC Psychologie chatbot as a document-RAG agent over scraped `/studium/` web pages and `/downloads/` PDFs, with mandatory citation-back-to-source and bilingual (DE/EN) auto-detect. The four enhancements below are deliberately deferred to phase-2 so we can ship a working MVP first and let Britta's internal QA + real usage shape priorities. Each one is independently optional — none block any other.

The architectural reasoning behind these choices (vs. e.g. cloning Dash or Scout wholesale) is captured in the chat history that produced this doc; in short, SSC is a *small, stable, single-source* doc-RAG use case — most patterns from Dash (SQL agents, schema-on-demand) and Scout (sub-agents, navigation-over-ingestion, multi-source providers) are over-engineering. We borrow only the few patterns that pay off at SSC's scale.

---

## 1. Curated FAQ knowledge layer

**Idea.** Add a hand-curated layer of FAQ entries alongside the scraped corpus. Each entry is a markdown file with frontmatter (`source_url`, `title`, `language`) under `curated_kb/faq/`, loaded into the same `Knowledge` object as scraped pages but tagged with `metadata.source_type = "curated_faq"`. Existing agent prompt + citation contract works unchanged because the metadata shape is identical to scraped pages.

**Inspiration.** Dash's `knowledge/queries/*.sql` and `knowledge/business/*.json` — the "curated overrides on top of raw schema" pattern, applied to documents instead of SQL. Ashpreet's "tribal knowledge matters more than model capability" thesis.

**Utility.**
- Britta's email highlighted *recurring* hot topics (entrance exam, psychotherapy master) where a single hand-written authoritative answer beats whatever the agent assembles from scraped page chunks.
- Lets non-technical authors fix wrong/incomplete answers without redeploying scraper logic or fighting chunk boundaries.
- The agent's existing `enable_agentic_knowledge_filters=True` means it can prefer curated entries when they match, falling back to scraped pages otherwise.
- Feeds item 4 (feedback loop) directly: refusals + thumbs-down become candidate FAQ entries.

**Seed corpus.** 5–10 entries covering Britta's named hot topics: entrance exam process, psychotherapy master clarifications, admission deadlines, application steps, Studienservice redirect language.

---

## 2. Editing surface for curated FAQs

**Idea.** Decide how Britta/Robert *author* the FAQs from item 1. The loader is the same regardless; only the sync step differs. Three options:

| Option | Sync mechanism | Pros | Cons |
|---|---|---|---|
| Private GitHub repo (e.g. `univie-health-research/ssc-psych-faq`) | `git pull` at container startup, or webhook-driven re-load | PR review = built-in quality gate for Robert; audit trail; zero new infra | Requires GitHub accounts; small learning curve |
| Shared Drive / SharePoint folder | `rclone sync` on cron | Familiar editing surface for non-developers | No PR review; trickier auth setup; no diff history |
| Small admin UI (DB-backed) | Direct DB writes | Best UX long-term | Highest dev cost; need auth; another surface to maintain |

**Inspiration.** Scout's git-backed wiki (`wiki/` folder mounted in a private GitHub repo with PR-based audit trail for production knowledge).

**Utility.**
- Decouples *who edits the knowledge* from *who deploys the agent*. Currently any FAQ change requires a developer.
- A PR-based workflow (option A) gives Robert a review gate for what Britta proposes — important for a public-facing university chatbot where wrong claims have reputational cost.
- Defers the build cost until we know which surface Britta actually wants — pending response from Britta/Robert.

**Decision blocker.** Ask Britta + Robert which workflow fits them. Until then, item 1 ships with a filesystem-only loader committed to the main repo; the editor-surface decision is a small follow-up.

---

## 3. Three-tier eval harness

**Idea.** Structure SSC-Psych evals into three independently-runnable tiers under `tests/evals/ssc_psych/`:

| Tier | File | What it asserts | Cost / cadence |
|---|---|---|---|
| **Wiring** | `test_wiring.py` | No-LLM invariants: every scraped page has `source_url`; every curated FAQ has required frontmatter; agent has `search_knowledge` tool wired; metadata filter values are valid | Free; runs on every PR |
| **Behavioral** | `test_behavioral.py` | ~30 golden Q&A pairs (Britta-supplied); assert citation present + `source_url` from `*.univie.ac.at` + LLM-as-judge correctness on a 1–5 scale | Cheap; runs nightly or pre-deploy, marked `@pytest.mark.integration` |
| **Judges** | `test_judges.py` | LLM-scored quality tiers on accuracy / tone / citation fidelity for a larger sample | Expensive; runs on release candidates only |

**Inspiration.** Scout's `python -m evals wiring` / `python -m evals` / `python -m evals judges` split (`docs/EVALS.md`). Dash's 5-axis eval framework (accuracy, routing, security, governance, boundaries).

**Utility.**
- Each tier answers a different question at a different cost — wiring catches refactor regressions, behavioral catches answer-quality regressions, judges catches subtle tone/citation drift.
- Critical for a public-facing bot: catches "the agent stopped citing sources" or "the agent started answering out-of-scope" regressions *before* Britta sees them.
- Golden Q&A set doubles as a regression baseline when iterating on the prompt or swapping models.

**Estimated effort.** ~1–2 days once Britta supplies the golden Q&A set. Reuses existing pytest infra (`asyncio_mode = auto`, integration marker).

---

## 4. Feedback capture + manual FAQ growth loop

**Idea.** Add UI thumbs-up/down + optional free-text comment that writes to a new `ssc_feedback` table. Weekly admin review converts negatives — *especially refusals* (the agent saying "I don't have information about …" under the strict refuse-and-redirect policy) — into new curated FAQ entries (item 1).

**Inspiration.** Dash's automatic "Learning Machine" (errors → diagnose → fix → store), but **deliberately downgraded to manual gate** for SSC. Ashpreet's "poor man's continuous learning" framing.

**Why manual, not automatic.** A public university chatbot can't auto-promote learnings — a wrong "learning" would propagate to all future answers without human review. Manual review by Robert/Britta is appropriate gating; the agent surfaces the candidate, a human decides whether it becomes canonical.

**Utility.**
- Refusals are *the* highest-signal feedback stream under the strict refuse-and-redirect policy: every refusal is, by definition, a question the bot can't answer that someone *did* ask. That's a perfect FAQ candidate list, generated for free.
- Closes the loop: curated FAQ (item 1) → behavioral evals (item 3) → feedback (item 4) → grow curated FAQ.
- Optional comment field gives Britta qualitative signal beyond a thumbs-down — *why* it was wrong.

**Sketch of the data shape** (not locked in — full design happens at implementation time):
```
ssc_feedback (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ,
    anonymous_session_id VARCHAR(64),
    anonymous_user_id VARCHAR(64) NULL,  -- if per-user-usage-reporting also shipped
    question TEXT,
    answer TEXT,
    was_refusal BOOLEAN,                 -- agent said "I don't know"
    rating SMALLINT,                     -- -1, +1
    comment TEXT NULL,
    reviewed_at TIMESTAMPTZ NULL,
    review_outcome VARCHAR(32) NULL      -- e.g. "added_to_faq", "out_of_scope", "wontfix"
)
```

**Dependencies.** Frontend change in the UI repo. Backend changes are additive (new POST endpoint, new table). Pairs naturally with the per-user-usage-reporting feature (shared `anonymous_user_id`).

---

## Suggested ordering when phase-2 starts

1. **Item 1** first — curated FAQ layer with filesystem-only loader. Smallest change, highest user-visible quality lift.
2. **Item 3** next — evals; the curated layer gives you a known-good answer set to write goldens against.
3. **Item 4** third — feedback capture; refusals from a corpus that *includes* curated FAQs are higher-signal than refusals from scraped-only.
4. **Item 2** in parallel with item 1, once Britta/Robert confirm the preferred editing surface.

## Non-goals / explicitly out of scope

- Cloning Dash or Scout architectures wholesale (analyzed and rejected — wrong fit for single-source doc-RAG).
- Multi-agent teams, sub-agent context providers, web fallback, schema-on-demand SQL, Slack/Drive/MCP providers — all over-engineering for SSC's actual scope.
- Externalizing the voice/style guide to a separate markdown file — current dedented strings in `agents/ssc_psych_agent.py` are sufficient until tone iteration starts.
- Auto-promoted "learnings" without human review — incompatible with public university bot quality bar.
