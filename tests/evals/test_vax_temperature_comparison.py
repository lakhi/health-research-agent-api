"""
Temperature comparison evals for the VAX study control agent.

Compares temperature settings [0.2, 0.6, 1.0] across the three core eval questions
using AccuracyEval with 30 iterations per (temperature, eval case) cell.

Results are written to results/vax_temperature/:
  - scores.csv   — one row per iteration (270 rows total)
  - summary.md   — aggregated stats + recommendation

Pre-requisites:
  - docker compose up pgvector -d
  - Azure OpenAI credentials in environment

First run: knowledge is loaded from PDF into PgVector (slow, ~1-2 min per temperature).
Subsequent runs: skip_if_exists=True → near-instant startup.

Run:
  pytest tests/evals/test_vax_temperature_comparison.py -v -m "integration and evals"

Run a single temperature during development:
  pytest tests/evals/test_vax_temperature_comparison.py -v -m "integration and evals" -k "temp_0.2"
"""

import csv
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
from agents.marhinovirus_agents.control_agent import get_control_marhinovirus_agent
from knowledge_base.marhinovirus_knowledge_base import initialize_agent_configs, load_normal_catalog

# ─── Configuration ────────────────────────────────────────────────────────────

TEMPERATURES = [0.2, 0.6, 1.0]
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


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _ensure_results_dir():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ─── Lifecycle fixture ────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _scoring_lifecycle():
    """Clear the CSV before scoring tests run; write summary after all tests finish."""
    _ensure_results_dir()
    csv_path = RESULTS_DIR / "scores.csv"
    if csv_path.exists():
        csv_path.unlink()

    yield

    if csv_path.exists():
        _write_summary_from_csv(csv_path)


# ─── Agent fixture ────────────────────────────────────────────────────────────


@pytest.fixture(
    scope="session",
    params=TEMPERATURES,
    ids=[f"temp_{t}" for t in TEMPERATURES],
)
async def control_agent_at_temp(request):
    """
    Session-scoped fixture: creates one control agent per temperature value and loads
    knowledge once. Knowledge loading is skipped on subsequent runs (skip_if_exists=True).
    """
    initialize_agent_configs()
    agent = get_control_marhinovirus_agent()
    agent.model = AzureOpenAI(id=VAX_STUDY_GPT_MODEL, temperature=request.param)
    await load_normal_catalog(agent.knowledge, skip_if_exists=True)
    return agent


# ─── CSV helpers ──────────────────────────────────────────────────────────────

_CSV_FIELDNAMES = [
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
    csv_path = RESULTS_DIR / "scores.csv"
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


# ─── Scoring tests ────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.evals
class TestVaxControlTemperatureScoring:
    """Run AccuracyEval for each (temperature, eval case) pair → CSV + summary."""

    @pytest.mark.parametrize("eval_case", EVAL_CASES, ids=[e.id for e in EVAL_CASES])
    def test_temperature_accuracy(self, control_agent_at_temp, eval_case):
        temperature = control_agent_at_temp.model.temperature

        eval_run = AccuracyEval(
            model=AzureOpenAI(id=JUDGE_MODEL_ID, temperature=0.1),
            agent=control_agent_at_temp,
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
                    "temperature": temperature,
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

    by_temp: dict[float, list[dict]] = defaultdict(list)
    for r in results:
        by_temp[r["temperature"]].append(r)

    by_temp_case: dict[tuple[float, str], list[dict]] = defaultdict(list)
    for r in results:
        by_temp_case[(r["temperature"], r["eval_case"])].append(r)

    lines = [
        "# VAX Study Control Agent — Temperature Scoring Summary",
        "",
        f"Generated: {timestamp}  ",
        f"Temperatures tested: {', '.join(str(t) for t in TEMPERATURES)}  ",
        f"Eval cases: {len(EVAL_CASES)}  ",
        f"Iterations per cell: {NUM_ITERATIONS}",
        "",
        "## Overall by Temperature",
        "",
        "| Temperature | Avg Score | Std Dev | Min | Max | Avg Response Length |",
        "|---|---|---|---|---|---|",
    ]

    temp_avgs: dict[float, float] = {}
    for temp in TEMPERATURES:
        rows = by_temp.get(temp, [])
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
            "## Breakdown by Eval Case",
            "",
            "| Eval Case | Temperature | Avg Score | Std Dev | Min | Max |",
            "|---|---|---|---|---|---|",
        ]
    )

    for case in EVAL_CASES:
        for temp in TEMPERATURES:
            rows = by_temp_case.get((temp, case.id), [])
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
        lines.extend(
            [
                "",
                "## Recommendation",
                "",
                f"Temperature **{best_temp}** achieved the highest overall average score of **{best_avg:.2f}**.",
                "This temperature is recommended as the default for the control agent in the VAX study.",
                "",
                "> Note: This is an exploratory comparison. No pass/fail threshold was applied.",
                "> Re-run with more iterations to confirm if scores across temperatures are close.",
            ]
        )

    output_path = RESULTS_DIR / "summary.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSummary written to {output_path}")
