"""
Temperature comparison evals for the NEX agent.

Compares temperature settings across a curated question bank.

Phase 1 (side-by-side): One run per temperature per question → Markdown comparison file.
Phase 2 (scoring): AccuracyEval with num_iterations=10 per (temp, question) → CSV + summary.

Pre-requisites:
  - docker compose up pgvector -d
  - NEX knowledge already loaded in pgvector (run the app once with LOAD_NEX_KNOWLEDGE=true)
  - Azure OpenAI credentials in environment

Run all:
  pytest tests/evals/test_nex_temperature_comparison.py -v -m "integration and evals"

Run phases separately:
  pytest tests/evals/test_nex_temperature_comparison.py -v -m "integration and evals" -k "SideBySide"
  pytest tests/evals/test_nex_temperature_comparison.py -v -m "integration and evals" -k "Scoring"
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

from agents.llm_models import LLMModel
from agents.nex_agent import get_nex_agent

# ─── Configuration ────────────────────────────────────────────────────────────

TEMPERATURES = [0.5, 0.75, 1.0]
NUM_ITERATIONS = 10
JUDGE_MODEL_ID = LLMModel.GPT_4_1
RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results" / "nex_temperature"


# ─── Question bank ────────────────────────────────────────────────────────────


@dataclass
class EvalQuestion:
    id: str
    input: str
    expected_output: str
    additional_guidelines: str


EVAL_QUESTIONS = [
    EvalQuestion(
        id="topic_search",
        input="Who in the network researches mental health?",
        expected_output=dedent("""\
            The primary network member researching mental health is Julia Reiter, affiliated
            with the Faculty of Psychology, Department of Occupational, Economic, and Social
            Psychology. Her research focuses on the mental health of healthcare professionals,
            particularly during the COVID-19 pandemic. She investigates changes in mental
            health over time, differences between professional groups (nurses, physicians,
            paramedics), the impact of stress factors, and how stigma and help-seeking
            behaviors affect mental health outcomes. Her work also explores the role of team
            climate and professional self-image in facilitating or inhibiting mental health
            support. University profile: https://ucrisportal.univie.ac.at/en/persons/julia-reiter

            Key research: "Mental health of healthcare professionals during the ongoing
            COVID-19 pandemic: a comparative investigation from the first and second
            pandemic years." Studies on mental health stigma, help-seeking, and professional
            differences in mental health outcomes among healthcare staff.
        """).strip(),
        additional_guidelines=dedent("""\
            The response must cite specific network members with their full names.
            Each member must include a University of Vienna profile URL or email address.
            The response must reference specific research papers or topics that connect
            each member to mental health research.
            Members should be organized thematically or by faculty.
        """).strip(),
    ),
    EvalQuestion(
        id="faculty_listing",
        input="Which members are in the Faculty of Psychology?",
        expected_output=dedent("""\
            Members affiliated with the Faculty of Psychology include:
            - Matthew Pelowski — Department of Cognition, Emotion, and Methods in Psychology
            - Robert Böhm — Department of Occupational, Economic, and Social Psychology
            - Julia Reiter — Department of Occupational, Economic, and Social Psychology
            - Ulrich Tran — Senior Lecturer, Department of Cognition, Emotion, and Methods
            - Barbara Schober — Full Professor, Department of Developmental and Educational Psychology
            - Julia Holzer — Scientific Staff, Department of Developmental and Educational Psychology
            - Giorgia Silani — Associate Professor, Clinical and Health Psychology
            - Martina Zemp — Full Professor, Department of Clinical and Health Psychology
            - Urs Markus Nater — Full Professor, Department of Clinical and Health Psychology
            - Laura Maria König — Full Professor, Department of Clinical and Health Psychology
            Each member should include a profile URL or email address.
        """).strip(),
        additional_guidelines=dedent("""\
            The response must list members from the Faculty of Psychology specifically.
            Each member must include their name, academic position, and a profile URL or email.
            The response should indicate how many members were found in this faculty.
            Members not affiliated with the Faculty of Psychology should not be included.
            Finding additional valid Faculty of Psychology members beyond these 10 is acceptable
            and should not reduce the score.
        """).strip(),
    ),
    EvalQuestion(
        id="news_query",
        input="What recent events has the network organized?",
        expected_output=dedent("""\
            Recent events organized by the Health in Society Research Network include:
            1. Research colloquium with Katie Attwell (published 26 Jan 2026) — interdisciplinary
               event on vaccine mandates and vaccination research.
               Link: https://gig.univie.ac.at/en/about-us/news/news-details/research-colloquium-with-katie-attwell
            2. University of Vienna Health Day (published 17 Feb 2026) — workplace health
               presentation and upcoming Health Survey introduction.
               Link: https://gig.univie.ac.at/en/about-us/news/news-details/health-and-well-being-at-the-place-of-work-university
            3. "Immunity and Resistance" international workshop (published 11 Feb 2026) —
               workshop on vaccines and antibiotics in global health.
               Link: https://gig.univie.ac.at/en/about-us/news/news-details/indispensable-but-controversial
            4. Student research seminar final presentations (published 22 Jan 2026) — master's
               students presented on cosmetic surgery, emergency care, gender bias in prescribing.
               Link: https://gig.univie.ac.at/en/about-us/news/news-details/on-cosmetic-procedures-and-medication-enquiries
            5. Circle U. Fifth Anniversary keynotes (published 20 Nov 2025) — keynotes on AI
               and global health.
               Link: https://gig.univie.ac.at/en/about-us/news/news-details/globale-gesundheit-und-ki
            6. Lecture series opening with Helena Hansen (published 23 Mar 2026) — bio-social
               understanding of health.
               Link: https://gig.univie.ac.at/en/about-us/news/news-details/towards-a-bio-social-understanding-of-health
            7. New LinkedIn account launch (published 11 Mar 2026).
        """).strip(),
        additional_guidelines=dedent("""\
            The response must reference actual news articles from the knowledge base.
            Each news item must include the article title, publication date, and link URL.
            The response should present events in reverse chronological order or grouped thematically.
            Events should come from the network's RSS news feed, not from research papers.
            Finding additional valid events beyond these 7 is acceptable and should not reduce the score.
        """).strip(),
    ),
    EvalQuestion(
        id="cross_source",
        input="Who works on physical activity, and have they been in any network news?",
        expected_output=dedent("""\
            Research expertise: Laura Maria König is the primary network member working on
            physical activity. She is a Full Professor in the Faculty of Psychology, Department
            of Clinical and Health Psychology. Her research focuses on digital interventions,
            measurement reactivity, wearable technology, and behavioral feedback for promoting
            physical activity. Her work synthesizes findings from systematic reviews and
            meta-analyses on technology-based interventions (apps, wearables, web platforms).
            Email: laura.koenig@univie.ac.at

            Network news: "Why sport is the best medicine" (published 13 Nov 2025) — Jürgen
            Scharhag discusses the health benefits of exercise in a Rudolphina podcast.
            Link: https://rudolphina.univie.ac.at/podcast-folge-17-warum-sport-das-beste-medikament-ist
        """).strip(),
        additional_guidelines=dedent("""\
            The response must search BOTH research papers and news articles.
            Members found through research papers must include paper-based citations with URLs.
            Any relevant news articles must include title, date, and link URL.
            The response must clearly distinguish between research-based findings and news-based findings.
            Finding additional relevant news articles is acceptable and should not reduce the score.
        """).strip(),
    ),
    EvalQuestion(
        id="no_results",
        input="Does anyone in the network study quantum computing?",
        expected_output=dedent("""\
            The knowledge base does not contain information about quantum computing research
            within the network. The response should honestly acknowledge this gap and redirect
            the user to authoritative sources such as the GiG network portal
            (https://gig.univie.ac.at/en/) or the u:cris research portal
            (https://ucris.univie.ac.at/).
        """).strip(),
        additional_guidelines=dedent("""\
            The response must honestly state that no relevant information was found.
            The response must NOT fabricate any member names or research topics.
            The response should redirect to at least one authoritative source (GiG portal or u:cris).
            The response may suggest a related search the user could try.
        """).strip(),
    ),
]


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_nex_agent(temperature: float):
    """Create a NEX agent at a specific temperature."""
    agent = get_nex_agent()
    agent.model = AzureOpenAI(id=LLMModel.GPT_4_1, temperature=temperature)
    return agent


def _ensure_results_dir():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ─── Phase 1: Side-by-side qualitative comparison ────────────────────────────


@pytest.mark.integration
@pytest.mark.evals
class TestNexTemperatureSideBySide:
    """Run each question once at each temperature, write Markdown comparison file."""

    def test_side_by_side(self):
        _ensure_results_dir()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            "# NEX Temperature Side-by-Side Comparison",
            "",
            f"Generated: {timestamp}",
            "",
            f"Temperatures: {', '.join(str(t) for t in TEMPERATURES)}",
            "",
        ]

        agents = {t: _make_nex_agent(t) for t in TEMPERATURES}

        for q in EVAL_QUESTIONS:
            lines.append("---")
            lines.append("")
            lines.append(f"## {q.id}: {q.input}")
            lines.append("")

            for temp in TEMPERATURES:
                agent = agents[temp]
                response = agent.run(q.input, stream=False)
                content = response.content if response.content else "(empty response)"
                char_count = len(str(content))

                lines.append(f"### Temperature {temp} ({char_count} chars)")
                lines.append("")
                lines.append(str(content))
                lines.append("")

        output_path = RESULTS_DIR / "side_by_side.md"
        output_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n✅ Side-by-side comparison written to {output_path}")


# ─── Phase 2: AccuracyEval scoring ───────────────────────────────────────────


_CSV_FIELDNAMES = [
    "temperature",
    "question_id",
    "question_text",
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


@pytest.mark.integration
@pytest.mark.evals
class TestNexTemperatureScoring:
    """Run AccuracyEval for each (temperature, question) pair → CSV + summary."""

    @pytest.fixture(scope="class", params=TEMPERATURES, ids=[f"temp_{t}" for t in TEMPERATURES])
    def nex_agent_at_temp(self, request):
        return _make_nex_agent(request.param)

    @pytest.mark.parametrize("question", EVAL_QUESTIONS, ids=[q.id for q in EVAL_QUESTIONS])
    def test_temperature_accuracy(self, nex_agent_at_temp, question):
        temperature = nex_agent_at_temp.model.temperature

        eval_case = AccuracyEval(
            model=AzureOpenAI(id=JUDGE_MODEL_ID, temperature=0.1),
            agent=nex_agent_at_temp,
            input=question.input,
            expected_output=question.expected_output,
            additional_guidelines=question.additional_guidelines,
            num_iterations=NUM_ITERATIONS,
        )
        result = eval_case.run(print_results=True)
        assert result is not None, "Eval returned None"

        # Write rows to CSV immediately
        rows = []
        for i, evaluation in enumerate(result.results):
            rows.append(
                {
                    "temperature": temperature,
                    "question_id": question.id,
                    "question_text": question.input,
                    "iteration": i + 1,
                    "judge_score": evaluation.score,
                    "judge_reason": evaluation.reason,
                    "response_length": len(evaluation.output),
                    "response_content": evaluation.output,
                }
            )
        _append_to_csv(rows)


def _write_summary_from_csv(csv_path: Path):
    """Read the completed CSV and generate the Markdown summary."""
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        results = list(reader)

    # Convert types from CSV strings
    for r in results:
        r["temperature"] = float(r["temperature"])
        r["judge_score"] = int(r["judge_score"])
        r["response_length"] = int(r["response_length"])

    if not results:
        return

    print(f"\n✅ Scores CSV at {csv_path} ({len(results)} rows)")
    _write_summary(results)


def _write_summary(results: list[dict]):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Group by temperature
    by_temp: dict[float, list[dict]] = defaultdict(list)
    for r in results:
        by_temp[r["temperature"]].append(r)

    # Group by (temperature, question)
    by_temp_q: dict[tuple[float, str], list[dict]] = defaultdict(list)
    for r in results:
        by_temp_q[(r["temperature"], r["question_id"])].append(r)

    lines = [
        "# NEX Temperature Scoring Summary",
        "",
        f"Generated: {timestamp}  ",
        f"Iterations per cell: {NUM_ITERATIONS}",
        "",
        "## Overall by Temperature",
        "",
        "| Temperature | Avg Score | Std Dev | Min | Max | Avg Response Length |",
        "|---|---|---|---|---|---|",
    ]

    for temp in TEMPERATURES:
        rows = by_temp.get(temp, [])
        if not rows:
            continue
        scores = [r["judge_score"] for r in rows]
        lengths = [r["response_length"] for r in rows]
        avg = statistics.mean(scores)
        std = statistics.stdev(scores) if len(scores) > 1 else 0
        mn = min(scores)
        mx = max(scores)
        avg_len = statistics.mean(lengths)
        lines.append(f"| {temp} | {avg:.2f} | {std:.2f} | {mn} | {mx} | {avg_len:.0f} |")

    lines.extend(
        [
            "",
            "## Breakdown by Question",
            "",
            "| Question | Temp | Avg Score | Std Dev | Min | Max |",
            "|---|---|---|---|---|---|",
        ]
    )

    question_ids = [q.id for q in EVAL_QUESTIONS]
    for qid in question_ids:
        for temp in TEMPERATURES:
            rows = by_temp_q.get((temp, qid), [])
            if not rows:
                continue
            scores = [r["judge_score"] for r in rows]
            avg = statistics.mean(scores)
            std = statistics.stdev(scores) if len(scores) > 1 else 0
            mn = min(scores)
            mx = max(scores)
            lines.append(f"| {qid} | {temp} | {avg:.2f} | {std:.2f} | {mn} | {mx} |")

    output_path = RESULTS_DIR / "summary.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ Summary written to {output_path}")
