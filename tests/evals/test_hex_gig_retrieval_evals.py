"""
Retrieval regression evals for the HeX-GiG agent (issue #47).

These assert on the *retrieval trace*, not on prose. The failures in #47 are mechanical —
a filter value that matches no row, a source_type that excludes two of the three sources —
and they are visible in the tool calls long before they reach the answer. Reading the trace
directly makes the gate deterministic and judge-free: no AccuracyEval variance, no judge
tokens, and a failure message that names the offending filter instead of a score.

`test_hex_gig_model_comparison.py` and `test_hex_gig_temperature_comparison.py` stay what
they are — comparison harnesses that write reports. This file is the regression gate.

Pre-requisites:
  - docker compose up pgvector -d
  - HeX-GiG knowledge loaded in that pgvector (run the app once with LOAD_HEX_GIG_KNOWLEDGE=true)
  - Azure OpenAI credentials in environment

Run: pytest tests/evals/test_hex_gig_retrieval_evals.py -v -m "integration and evals"
"""

import json
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import pytest

from agents.hex_gig_agent import get_hex_gig_agent

# ─── Configuration ────────────────────────────────────────────────────────────

# The agent runs at temperature 0.75, so a single trial proves nothing either way.
# Five is the smallest number that distinguishes "usually works" from "got lucky".
TRIALS = 5

SEARCH_TOOL = "search_knowledge_base"
NEWS_TOOL = "get_latest_hex_news"

# What agno's search tool returns when a filter matched no rows. Indistinguishable, to the
# model, from a genuinely empty knowledge base — which is exactly how #47 produced a
# confident "I don't have information about that".
EMPTY_RESULT = "No documents found"

# Metadata keys whose values are free text, so the model cannot guess one that matches.
# `academic_position` holds 'Full Professor', 'Associate Professor/Ao. Professor',
# 'University Assistant (post doc)', … — never the bare role word a user types. Because
# dict filters reach pgvector as JSONB containment (exact string equality), a near-miss
# returns zero rows rather than a near match. `source_type` and `faculty_affiliation` are
# closed vocabularies and stay allowed.
FREE_TEXT_FILTER_KEYS = frozenset({"academic_position", "discipline", "department_affiliation"})


# ─── Trace capture ────────────────────────────────────────────────────────────


@dataclass
class Search:
    """One knowledge-tool call and what came back from it."""

    tool_name: str
    args: dict[str, Any]
    docs: list[dict[str, Any]]
    empty: bool

    @property
    def filter_keys(self) -> set[str]:
        """Metadata keys this call filtered on, across both shapes agno accepts.

        The tool signature takes `List[KnowledgeFilter]`, which the model fills in as either
        `[{"key": k, "value": v}]` or `[{k: v}]` — both are flattened to one dict downstream
        (`_default_tools._resolve_filters`), so both have to be read here.
        """
        keys: set[str] = set()
        for filt in self.args.get("filters") or []:
            if not isinstance(filt, dict):
                continue
            if "key" in filt:
                keys.add(str(filt["key"]))
            else:
                keys.update(str(k) for k in filt)
        return keys

    @property
    def source_types(self) -> set[str]:
        """`source_type` of every chunk this call actually returned."""
        return {
            str(doc.get("meta_data", {}).get("source_type"))
            for doc in self.docs
            if isinstance(doc, dict) and doc.get("meta_data")
        }


@dataclass
class Trial:
    """One run of one question: the answer, plus every knowledge call behind it."""

    answer: str
    searches: list[Search] = field(default_factory=list)

    @property
    def retrieved_source_types(self) -> set[str]:
        found: set[str] = set()
        for search in self.searches:
            if search.tool_name == NEWS_TOOL and not search.empty:
                # The recency tool reads news rows straight from SQL, so it returns text
                # rather than chunk dicts. A non-empty result is news, by construction.
                found.add("news_article")
            found |= search.source_types
        return found

    @property
    def all_searches_empty(self) -> bool:
        return bool(self.searches) and all(s.empty for s in self.searches)

    def tools_used(self) -> set[str]:
        return {s.tool_name for s in self.searches}


def _parse_docs(result: str | None) -> list[dict[str, Any]]:
    """Return the chunk dicts in a search result, or [] for the news tool / an empty search."""
    if not result or result.strip().startswith(EMPTY_RESULT):
        return []
    try:
        parsed = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _run_trial(agent, question: str) -> Trial:
    response = agent.run(question, stream=False)
    trial = Trial(answer=str(response.content or ""))

    for execution in response.tools or []:
        if execution.tool_name not in (SEARCH_TOOL, NEWS_TOOL):
            continue
        result = execution.result
        docs = _parse_docs(result)
        trial.searches.append(
            Search(
                tool_name=execution.tool_name,
                args=execution.tool_args or {},
                docs=docs,
                empty=not docs and (not result or result.strip().startswith(EMPTY_RESULT)),
            )
        )

    return trial


def _fold(text: str) -> str:
    """Casefold and strip accents, so 'Gómez' and 'Gomez' compare equal.

    The members CSV spells him 'Gomez Varela'; the RSS article spells him 'Gómez Varela'.
    An answer is correct with either.
    """
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


# ─── Cases ────────────────────────────────────────────────────────────────────


@dataclass
class RetrievalCase:
    id: str
    question: str
    # Sources whose chunks must appear in the retrieval trace, every trial.
    require_sources: frozenset[str] = frozenset()
    # The answer must contain at least one of these (accent- and case-insensitive).
    require_any_of: tuple[str, ...] = ()
    # The answer must contain none of these.
    forbid_any_of: tuple[str, ...] = ()
    # The run must call this tool at least once.
    require_tool: str | None = None
    # Whether a free-text filter key is a failure. False only for the honest-gap case,
    # where an empty result is the correct outcome however it was reached.
    forbid_free_text_filters: bool = True
    # Trials that must satisfy every assertion above. Below TRIALS where the behaviour is
    # genuinely a judgement call rather than a mechanism.
    must_pass: int = TRIALS


CASES = [
    # The reported case. Note the trap inside it: David Gomez Varela, who actually won the
    # LEO Foundation grant, is a 'Senior Scientist' — so even a *correctly spelled*
    # academic_position filter for professors would have excluded him. Role words in this
    # corpus cannot be answered by filtering on role.
    RetrievalCase(
        id="grants_across_sources",
        question="are there any professors who have won some grants?",
        require_sources=frozenset({"research_paper"}),
        require_any_of=("Varela", "LEO", "Chovanec", "APART", "Horizon 2020", "FWF"),
        forbid_any_of=("I don't have information",),
    ),
    # Cause B on its own: the grant news exists and must reach the answer. Held at 3/5
    # because tier 1 is a prompt nudge and the model still chooses its own filters —
    # raise this to TRIALS once tier 2 makes the three-source fan-out structural (#47).
    RetrievalCase(
        id="grants_surface_news_too",
        question="are there any professors who have won some grants?",
        require_sources=frozenset({"news_article"}),
        must_pass=3,
    ),
    # The same failure shape from the other direction: 'postdocs' invites
    # academic_position='Postdoc', which matches none of the 15 rows spelled
    # 'University Assistant (post doc)'. Deliberately asserts no particular source —
    # any of the three can answer this, and the bug under test is the empty search,
    # not the routing.
    RetrievalCase(
        id="role_word_does_not_empty_the_search",
        question="are there any postdocs in the network working on nutrition or diet?",
        forbid_any_of=("I don't have information",),
        must_pass=4,
    ),
    # A member who exists in two sources at once. Answering from papers alone is a
    # silently incomplete answer, which is the #47 cause-B gap.
    RetrievalCase(
        id="member_spans_papers_and_news",
        question="tell me about David Gomez Varela's work",
        require_sources=frozenset({"research_paper"}),
        require_any_of=("Varela",),
        must_pass=4,
    ),
    # Regression guard for #45: recency questions must keep routing to the SQL tool.
    # Tier-1 prompt edits push toward breadth, and must not blunt that routing.
    RetrievalCase(
        id="recency_still_routes_to_news_tool",
        question="what is the latest news from the network?",
        require_tool=NEWS_TOOL,
    ),
    # faculty_affiliation is a closed vocabulary and must stay usable — the fix narrows
    # which keys may be filtered, it does not ban filtering.
    RetrievalCase(
        id="faculty_filter_still_works",
        question="which members are in the Faculty of Psychology?",
        require_sources=frozenset({"member_profile"}),
        require_any_of=("Psychology",),
        forbid_any_of=("I don't have information",),
    ),
    # The counterweight to every case above: when the corpus genuinely holds nothing,
    # retrying unfiltered must not turn into invention.
    RetrievalCase(
        id="honest_when_the_gap_is_real",
        question="does anyone in the network study quantum computing?",
        require_any_of=("gig.univie.ac.at", "ucris.univie.ac.at"),
        forbid_free_text_filters=False,
    ),
]


# ─── Fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def hex_agent():
    """One agent for the whole module. Knowledge must already be loaded in pgvector."""
    return get_hex_gig_agent()


# ─── Assertions ───────────────────────────────────────────────────────────────


def _check(trial: Trial, case: RetrievalCase) -> list[str]:
    """Return a list of human-readable failures for one trial. Empty means it passed."""
    failures: list[str] = []

    if not trial.searches:
        failures.append("no knowledge tool was called at all")
        return failures

    if case.forbid_free_text_filters:
        for search in trial.searches:
            offending = search.filter_keys & FREE_TEXT_FILTER_KEYS
            if offending:
                failures.append(f"filtered on free-text key(s) {sorted(offending)} in {search.args!r}")

    # The core #47 regression: every search came back empty and the run stopped there.
    # One empty search is fine — an unfiltered retry after it is exactly the wanted behaviour.
    if trial.all_searches_empty:
        failures.append(f"all {len(trial.searches)} searches returned '{EMPTY_RESULT}' with no recovering retry")

    missing_sources = case.require_sources - trial.retrieved_source_types
    if missing_sources:
        failures.append(
            f"never retrieved from {sorted(missing_sources)} (saw {sorted(trial.retrieved_source_types) or 'nothing'})"
        )

    if case.require_tool and case.require_tool not in trial.tools_used():
        failures.append(f"did not call {case.require_tool} (called {sorted(trial.tools_used())})")

    folded = _fold(trial.answer)
    if case.require_any_of and not any(_fold(needle) in folded for needle in case.require_any_of):
        failures.append(f"answer mentions none of {list(case.require_any_of)}")

    for needle in case.forbid_any_of:
        if _fold(needle) in folded:
            failures.append(f"answer contains forbidden phrase {needle!r}")

    return failures


@pytest.mark.integration
@pytest.mark.evals
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_retrieval_case(hex_agent, case: RetrievalCase):
    """Run one question TRIALS times and require at least `must_pass` clean trials."""
    results: list[tuple[int, list[str]]] = []

    for attempt in range(1, TRIALS + 1):
        trial = _run_trial(hex_agent, case.question)
        results.append((attempt, _check(trial, case)))

    passed = [attempt for attempt, failures in results if not failures]

    if len(passed) < case.must_pass:
        reasons = Counter(reason for _, failures in results for reason in failures)
        report = "\n".join(f"  {count}/{TRIALS} trials: {reason}" for reason, count in reasons.most_common())
        pytest.fail(
            f"{case.id}: {len(passed)}/{TRIALS} trials clean, needed {case.must_pass}.\n"
            f"Question: {case.question!r}\n{report}"
        )
