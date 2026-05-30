# Fix: VAX side-effect answers drop a severity tier (issue #40)

## Context

The vax-study (Marhinovirus) chatbot is supposed to list **all three** vaccine
side-effect severity tiers whenever asked about side effects:

- 24% of vaccinations → slight injection-site pain + fatigue (15 fp loss)
- 12% → headache + muscle pain (20 fp loss)
- 4% → fever, severe headache, dizziness (50 fp loss)

The study's results spreadsheet (sheet 2, "Vaccine Side effects Question
variation") shows it frequently **does not**. Every failing row drops a tier —
almost always the mildest **24% / 15 fp** one — or truncates after the first
tier with "let me know if you want more". The first sheet corroborates this:
"Did not give all possible outcomes for the vaccine" recurs across participants.

Yet `tests/evals/test_vax_evals.py::test_vaccination_side_effects` passes
(~9.27/10). It tests a **single, clean, single-turn** input
(`"What happens if I vaccinate myself?"`). The real failures use **varied
phrasings** — "should i get the vaccine", "what are the probability and severity
of vaccine side effects", "Are there any side effects to vaccination?" — which
push the model to summarise/compress and drop a tier.

**Root cause is adherence, not a missing rule.** The Azure-hosted instruction
files already mandate it: *"…you must list every outcome level that exists in the
catalogue with its probability and fitness-point loss. Do not merge categories."*
plus a self-check *"Did I include the probability for each outcome?"*. The model
just doesn't reliably obey it under varied phrasing.

There are two candidate fault layers:
- **Retrieval** — hybrid search doesn't surface the mild-tier chunk for some
  phrasings (reranker is disabled, `max_results` is commented out).
- **Adherence** — all tiers are in context but the model compresses the answer.

Strategy: reproduce the failure with new evals, then **try the cheaper repo-side
retrieval fix first and gate it on the eval suite**; only fall through to the
external Azure-blob instruction edit if retrieval alone doesn't fix it.

### On "Reliability eval" (why we are NOT using it)
Agno's `ReliabilityEval` only checks **whether expected tool calls were made**
(e.g. `search_knowledge`); it does **not** judge content completeness, so it
cannot catch the dropped-tier failure. The correct tool is more `AccuracyEval`
cases (LLM-as-judge on content).

---

## Phase 1 — Reproduce the failure (repo: `tests/evals/test_vax_evals.py`)

Reuse the existing `expected_output` + `additional_guidelines` from
`test_vaccination_side_effects` (lines 100–121) so the gold standard stays
identical; only the *inputs* change.

1. Extract the shared `expected_output` and `additional_guidelines` into
   module-level constants (e.g. `SIDE_EFFECTS_EXPECTED`,
   `SIDE_EFFECTS_GUIDELINES`) so the existing test and the new ones share one
   source of truth. Refactor `test_vaccination_side_effects` to use them.

2. Add a `pytest.mark.parametrize` test over the real failing phrasings, each
   building an `AccuracyEval` with the shared `expected_output`/guidelines and
   asserting `avg_score >= 8.5`:
   - `"Are there any side effects to vaccination?"`
   - `"should i get the vaccine"`
   - `"what are the probability and severity of vaccine side effects"`
   - `"What is the exact fitness point deduction for choosing to get vaccinated"`

   For `"should i get the vaccine"` the guidelines must allow extra
   infection/recommendation content — only require that all three side-effect
   tiers are present (do not penalise the additional infection-outcome info).
   Add a small guideline note to that effect, or use a separate guidelines
   constant for that case.

   Use `num_iterations=10–15` per phrasing (several phrasings × judge calls —
   keep cost bounded; the existing single case uses 30).

> **Multi-turn case is intentionally skipped** (not required for now).

Confirm these new cases actually fail (or score below threshold) on the current
agent before applying any fix — that proves they reproduce the bug.

```bash
docker compose up pgvector -d
pytest tests/evals/test_vax_evals.py -v -m "integration and evals"
```

---

## Phase 2 — Apply retrieval fix (repo: `knowledge_base/marhinovirus_knowledge_base.py`)

In `get_normal_catalog_knowledge()` (lines ~86–109) and `load_normal_catalog()`:
- **Keep all three tiers in one chunk** — verify the PDF's side-effect section
  isn't split by `AgenticChunking` (max 3000 chars); if it is, adjust chunking so
  the tier list stays contiguous (retrieval can't return a tier it never chunked
  together).
- **Enable the reranker** — `reranker=CohereReranker()` is commented out
  (line ~103); enabling it pushes the most relevant tier chunks to the top.
- **Raise/set `max_results`** explicitly (commented `# max_results=5`,
  line ~105) so all tier chunks fit in the returned set.

Reloading the catalog is required after a chunking change: drop the
`marhino_normal_catalog` pgvector table (or otherwise clear it) so
`load_normal_catalog` re-embeds with the new chunking.

---

## Phase 3 — Gate on the eval suite (decision point)

Re-run Phase 1's evals (reload the catalog first if chunking changed):

```bash
pytest tests/evals/test_vax_evals.py -v -m "integration and evals"
```

- **If all cases (existing + new phrasings) hold `avg_score >= 8.5` with no
  regressions → DONE. Keep the Phase 2 retrieval fix and skip Phase 4.**
- **If not fixed → revert the Phase 2 change entirely** (restore
  `knowledge_base/marhinovirus_knowledge_base.py` to its original state, reload
  the original catalog) so the retrieval and adherence fixes are never
  conflated, then proceed to Phase 4.

---

## Phase 4 — Adherence fix (Azure blob, only if Phase 3 failed)

Files live in Azure Blob (`socialeconpsystorage` / `marhinovirus-study`
container): `normal-instructions.txt` and `simple-instructions.txt`. Changes are
made there and picked up at app startup via `initialize_agent_configs()`.

Tighten the **generic** rule (per project convention: keep instructions generic —
do **not** hard-code the 24/12/4% numbers into the prompt). Add:
- An explicit anti-truncation clause: *never* stop after one outcome level or
  offer to provide the remaining levels on request — list every level in one
  response.
- Reinforce the existing self-check with: *"Did I list EVERY outcome level from
  the catalogue, including the mildest, without deferring any to a follow-up?"*

Then re-run the eval suite (Phase 3 commands) and confirm all cases hold
`avg_score >= 8.5`. If still failing, iterate on the instruction wording (and
reconsider re-applying the retrieval fix on top).

---

## Phase 5 — Verify

All cases (existing + new phrasings) must hold `avg_score >= 8.5`:

```bash
docker compose up pgvector -d
pytest tests/evals/test_vax_evals.py -v -m "integration and evals"
```

Confirm the previously-failing phrasings now consistently include all three
tiers across iterations, not just on average.

---

## Files

| File | Change |
|---|---|
| `tests/evals/test_vax_evals.py` | Extract shared expected_output/guidelines constants; add parametrized varied-phrasing cases (no multi-turn) |
| `knowledge_base/marhinovirus_knowledge_base.py` | Phase 2 retrieval fix: reranker, `max_results`, chunk-contiguity. Reverted if Phase 3 fails |
| `normal-instructions.txt` / `simple-instructions.txt` (Azure Blob, external) | Phase 4 (only if Phase 3 fails): generic anti-truncation + reinforced self-check |

## Notes
- Reuse existing patterns: the `vax_agent` session fixture, `AccuracyEval` setup,
  and the `>= 8.5` threshold already in `test_vax_evals.py`.
- The retrieval fix (Phase 2) and adherence fix (Phase 4) are mutually exclusive
  in this plan: apply 2, test, and only do 4 after reverting 2 if 2 didn't work.
