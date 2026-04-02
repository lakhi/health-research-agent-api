"""
Temperature comparison evals for the VAX study simple_language and simple_catalog_language agents.

Compares temperature settings [0.2, 0.6, 1.0] across the three core eval questions
using AccuracyEval with 30 iterations per (agent, temperature, eval case) cell.

Results are written to results/vax_temperature/:
  - simple_agents_scores.csv   — one row per iteration (540 rows total)
  - simple_agents_summary.md   — aggregated stats + per-agent recommendations

Pre-requisites:
  - docker compose up pgvector -d
  - Azure OpenAI credentials in environment

First run: knowledge is loaded from PDF into PgVector (slow, ~1-2 min per agent/temperature).
Subsequent runs: skip_if_exists=True → near-instant startup.

Run:
  pytest tests/evals/test_vax_simple_agents_temperature_comparison.py -v -m "integration and evals"

Run a single condition during development:
  pytest tests/evals/test_vax_simple_agents_temperature_comparison.py -v -m "integration and evals" -k "simple_language_temp_0.2"
"""

import csv
import itertools
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

import pytest
from agno.eval.accuracy import AccuracyEval
from agno.models.azure import AzureOpenAI

from agents.llm_models import VAX_STUDY_GPT_MODEL
from agents.marhinovirus_agents.simple_catalog_language_agent import get_simple_catalog_language_marhinovirus_agent
from agents.marhinovirus_agents.simple_language_agent import get_simple_language_marhinovirus_agent
from knowledge_base.marhinovirus_knowledge_base import initialize_agent_configs, load_normal_catalog, load_simple_catalog

# ─── Configuration ────────────────────────────────────────────────────────────

AGENT_CONDITIONS = ["simple_language", "simple_catalog_language"]
TEMPERATURES = [0.2, 0.6, 1.0]
AGENT_TEMPERATURES = list(itertools.product(AGENT_CONDITIONS, TEMPERATURES))
NUM_ITERATIONS = 30
JUDGE_MODEL_ID = VAX_STUDY_GPT_MODEL
RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results" / "vax_temperature"


# ─── Eval definitions ─────────────────────────────────────────────────────────


@dataclass
class EvalCase:
    id: str
    input: str
    expected_output: str
    additional_guidelines: str


EVAL_CASES = [
    EvalCase(
        id="infection_consequences",
        input="What happens if I catch the virus?",
        expected_output=dedent("""\
            Depending on the severity of your symptoms due to the disease, you can lose different amounts of fitness points.

            In six out of ten cases (60%), people with marhinitis develop nausea, stomach pain and cramping, diarrhea, dizziness and general body aches (40 fitness points loss).

            In three out of ten cases (30%), one can also develop severe diarrhea, vomiting, fever and headaches (60 fitness points loss).

            In one out of ten cases (10%), marhinitis can lead to complications such as inflamed intestines. In this case you might additionally experience severe stomach pain and bloody stool.

            Severe diarrhea and vomiting can also sometimes lead to dehydration, which shows itself in confusion and lethargy, a dry mouth and throat and dizziness when standing up (80 fitness points loss).
        """).strip(),
        additional_guidelines=dedent("""\
            All three severity tiers must be present with correct probabilities and fitness point losses: 60% -> 40 fp, 30% -> 60 fp, 10% -> 80 fp.
            Key symptoms per tier should be mentioned.
            Dehydration may be presented as a separate conditional statement OR bundled into the 10% tier — either structure is acceptable as long as the 80 fp loss is mentioned.
            Mentioning losing all 100 fitness points, extremely rare circumstances, or worst-case outcomes should reduce the score — this information belongs only in responses to direct questions about death or fatal outcomes.
            Minor wording differences are acceptable as long as the facts are numerically correct.
        """).strip(),
    ),
    EvalCase(
        id="vaccination_side_effects",
        input="What happens if I vaccinate myself?",
        expected_output=dedent("""\
            If you get vaccinated it is 85% less likely for you to get infected than when you do not get vaccinated.

            You will lose 10 fitness points for the effort of getting vaccinated (scheduling, travel, waiting).

            Some temporary side effects have been reported from getting vaccinated. There is a probability of 40% that you develop side effects due to vaccination.

            In 24% of all vaccinations, there is only a slight pain at the injection site and some fatigue (15 fitness points loss).
            In 12% of all vaccinations, people develop a headache and muscle pain (20 fitness points loss).
            In 4% of all vaccinations, patients develop fever and severe headache, as well as dizziness (50 fitness points loss).
        """).strip(),
        additional_guidelines=dedent("""\
            The response must state the overall 40% side-effect probability.
            The three severity tiers must be present with correct percentages and fitness point losses:
            24% -> 15 fp, 12% -> 20 fp, 4% -> 50 fp.
            The 10 fitness-point effort cost for getting vaccinated may be mentioned and is acceptable.
            Minor wording differences are acceptable as long as the facts are numerically correct.
        """).strip(),
    ),
    EvalCase(
        id="worst_case_outcome",
        input="Can I die from this virus?",
        expected_output=dedent("""\
            You are not able to lose all 100 fitness points by simply contracting the virus.
            The maximum loss of fitness points from marhinitis is 80 points.
        """).strip(),
        additional_guidelines=dedent("""\
            The response must convey that you cannot lose all 100 fitness points from the virus,
            and that the maximum loss is 80 fitness points.
            The response must not use the words 'death', 'die', 'dies', 'dying', 'died', 'fatal', or 'fatality' — including in disclaimer sentences.
            A neutral closing sentence such as 'No further details are provided' is acceptable.
            Mentioning the virus name (marhinovirus or marhinitis) is acceptable and should not reduce the score.
            Minor wording differences are acceptable as long as the core facts are correct.
        """).strip(),
    ),
]


# ─── Agent wrapper ────────────────────────────────────────────────────────────


@dataclass
class AgentAtTemp:
    agent: object
    agent_condition: str
    temperature: float


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _ensure_results_dir():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ─── Lifecycle fixture ────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _scoring_lifecycle():
    """Clear the CSV before scoring tests run; write summary after all tests finish."""
    _ensure_results_dir()
    csv_path = RESULTS_DIR / "simple_agents_scores.csv"
    if csv_path.exists():
        csv_path.unlink()

    yield

    if csv_path.exists():
        _write_summary_from_csv(csv_path)


# ─── Agent fixture ────────────────────────────────────────────────────────────


@pytest.fixture(
    scope="session",
    params=AGENT_TEMPERATURES,
    ids=[f"{a}_temp_{t}" for a, t in AGENT_TEMPERATURES],
)
async def vax_simple_agent_at_temp(request):
    """
    Session-scoped fixture: one agent instance per (agent_condition, temperature) pair.
    Knowledge loading is skipped on subsequent runs (skip_if_exists=True).
    """
    agent_condition, temperature = request.param
    initialize_agent_configs()

    if agent_condition == "simple_language":
        agent = get_simple_language_marhinovirus_agent()
        await load_normal_catalog(agent.knowledge, skip_if_exists=True)
    else:
        agent = get_simple_catalog_language_marhinovirus_agent()
        await load_simple_catalog(agent.knowledge, skip_if_exists=True)

    agent.model = AzureOpenAI(id=VAX_STUDY_GPT_MODEL, temperature=temperature)
    return AgentAtTemp(agent=agent, agent_condition=agent_condition, temperature=temperature)


# ─── CSV helpers ──────────────────────────────────────────────────────────────

_CSV_FIELDNAMES = [
    "agent_condition",
    "temperature",
    "eval_case",
    "eval_input",
    "iteration",
    "judge_score",
    "judge_reason",
    "response_length",
    "response_content",
]


def _append_to_csv(rows: list[dict]):
    """Append scoring rows to the CSV, creating it with a header if needed."""
    csv_path = RESULTS_DIR / "simple_agents_scores.csv"
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


# ─── Scoring tests ────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.evals
class TestVaxSimpleAgentsTemperatureScoring:
    """Run AccuracyEval for each (agent, temperature, eval case) combination → CSV + summary."""

    @pytest.mark.parametrize("eval_case", EVAL_CASES, ids=[e.id for e in EVAL_CASES])
    def test_temperature_accuracy(self, vax_simple_agent_at_temp, eval_case):
        agent_at_temp: AgentAtTemp = vax_simple_agent_at_temp

        eval_run = AccuracyEval(
            model=AzureOpenAI(id=JUDGE_MODEL_ID, temperature=0.1),
            agent=agent_at_temp.agent,
            input=eval_case.input,
            expected_output=eval_case.expected_output,
            additional_guidelines=eval_case.additional_guidelines,
            num_iterations=NUM_ITERATIONS,
        )
        result = eval_run.run(print_results=True)
        assert result is not None, "Eval returned None"

        rows = []
        for i, evaluation in enumerate(result.results):
            rows.append(
                {
                    "agent_condition": agent_at_temp.agent_condition,
                    "temperature": agent_at_temp.temperature,
                    "eval_case": eval_case.id,
                    "eval_input": eval_case.input,
                    "iteration": i + 1,
                    "judge_score": evaluation.score,
                    "judge_reason": evaluation.reason,
                    "response_length": len(evaluation.output),
                    "response_content": evaluation.output,
                }
            )
        _append_to_csv(rows)


# ─── Summary generation ───────────────────────────────────────────────────────


def _write_summary_from_csv(csv_path: Path):
    """Read the completed CSV and generate the Markdown summary."""
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        results = list(reader)

    for r in results:
        r["temperature"] = float(r["temperature"])
        r["judge_score"] = int(r["judge_score"])
        r["response_length"] = int(r["response_length"])

    if not results:
        return

    print(f"\nScores CSV at {csv_path} ({len(results)} rows)")
    _write_summary(results)


def _write_summary(results: list[dict]):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Group by (agent_condition, temperature)
    by_agent_temp: dict[tuple[str, float], list[dict]] = defaultdict(list)
    for r in results:
        by_agent_temp[(r["agent_condition"], r["temperature"])].append(r)

    # Group by (agent_condition, temperature, eval_case)
    by_agent_temp_case: dict[tuple[str, float, str], list[dict]] = defaultdict(list)
    for r in results:
        by_agent_temp_case[(r["agent_condition"], r["temperature"], r["eval_case"])].append(r)

    lines = [
        "# VAX Study Simple Agents — Temperature Scoring Summary",
        "",
        f"Generated: {timestamp}  ",
        f"Agent conditions: {', '.join(AGENT_CONDITIONS)}  ",
        f"Temperatures tested: {', '.join(str(t) for t in TEMPERATURES)}  ",
        f"Eval cases: {len(EVAL_CASES)}  ",
        f"Iterations per cell: {NUM_ITERATIONS}",
        "",
    ]

    best_temps: dict[str, float] = {}

    for agent_condition in AGENT_CONDITIONS:
        label = agent_condition.replace("_", " ").title()
        lines.extend(
            [
                f"## {label}",
                "",
                "### Overall by Temperature",
                "",
                "| Temperature | Avg Score | Std Dev | Min | Max | Avg Response Length |",
                "|---|---|---|---|---|---|",
            ]
        )

        temp_avgs: dict[float, float] = {}
        for temp in TEMPERATURES:
            rows = by_agent_temp.get((agent_condition, temp), [])
            if not rows:
                continue
            scores = [r["judge_score"] for r in rows]
            lengths = [r["response_length"] for r in rows]
            avg = statistics.mean(scores)
            std = statistics.stdev(scores) if len(scores) > 1 else 0.0
            mn = min(scores)
            mx = max(scores)
            avg_len = statistics.mean(lengths)
            temp_avgs[temp] = avg
            lines.append(f"| {temp} | {avg:.2f} | {std:.2f} | {mn} | {mx} | {avg_len:.0f} |")

        lines.extend(
            [
                "",
                "### Breakdown by Eval Case",
                "",
                "| Eval Case | Temperature | Avg Score | Std Dev | Min | Max |",
                "|---|---|---|---|---|---|",
            ]
        )

        for case in EVAL_CASES:
            for temp in TEMPERATURES:
                rows = by_agent_temp_case.get((agent_condition, temp, case.id), [])
                if not rows:
                    continue
                scores = [r["judge_score"] for r in rows]
                avg = statistics.mean(scores)
                std = statistics.stdev(scores) if len(scores) > 1 else 0.0
                mn = min(scores)
                mx = max(scores)
                lines.append(f"| {case.id} | {temp} | {avg:.2f} | {std:.2f} | {mn} | {mx} |")

        if temp_avgs:
            best_temp = max(temp_avgs, key=lambda t: temp_avgs[t])
            best_avg = temp_avgs[best_temp]
            best_temps[agent_condition] = best_temp
            lines.extend(
                [
                    "",
                    f"**Recommended temperature for `{agent_condition}`:** {best_temp} (avg score {best_avg:.2f})",
                    "",
                ]
            )

    lines.extend(
        [
            "---",
            "",
            "## Summary Recommendations",
            "",
            "| Agent Condition | Recommended Temperature |",
            "|---|---|",
        ]
    )
    for agent_condition, best_temp in best_temps.items():
        lines.append(f"| {agent_condition} | {best_temp} |")

    lines.extend(
        [
            "",
            "> Note: This is an exploratory comparison. No pass/fail threshold was applied.",
            "> Re-run with more iterations to confirm if scores across temperatures are close.",
        ]
    )

    output_path = RESULTS_DIR / "simple_agents_summary.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSummary written to {output_path}")
