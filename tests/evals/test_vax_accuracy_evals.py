"""
Agno AccuracyEval tests for the vax-study (Marhinovirus) control agent.

Pre-requisites:
  - docker compose up pgvector -d   (pgvector only — no full app needed)
  - Azure OpenAI credentials in environment

First run: knowledge is loaded from PDF into PgVector (slow, ~1-2 min).
Subsequent runs: skip_if_exists=True → near-instant startup.

Run: pytest tests/evals/ -v -m "integration and evals"
"""

import pytest
from textwrap import dedent
from agno.eval.accuracy import AccuracyEval, AccuracyResult
from agno.knowledge.chunking.document import DocumentChunking
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.models.azure import AzureOpenAI

from agents.llm_models import LLMModel
from agents.marhinovirus_agents.control_agent import get_control_marhinovirus_agent
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_url,
    initialize_agent_configs,
)

JUDGE_MODEL_ID = LLMModel.GPT_5_CHAT  # same model as the control agent


@pytest.fixture(scope="session")
async def vax_agent():
    """
    Session-scoped: creates the control agent and loads knowledge once per pytest run.
    Knowledge loading is skipped on subsequent runs (skip_if_exists=True).
    """
    initialize_agent_configs()
    agent = get_control_marhinovirus_agent(debug_mode=False)

    pdf_reader = PDFReader(
        chunking_strategy=DocumentChunking(chunk_size=1200, overlap=200)
    )
    await agent.knowledge.ainsert(
        name="Marhinovirus Normal Catalog",
        url=get_normal_catalog_url(),
        reader=pdf_reader,
        skip_if_exists=True,  # fast on re-runs; change to False to force reload
    )
    return agent


# ─── Accuracy evals ──────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.evals
def test_infection_consequences(vax_agent):
    """Agent must describe all three severity tiers with correct probabilities, symptoms, and fitness point losses."""
    eval_case = AccuracyEval(
        model=AzureOpenAI(id=JUDGE_MODEL_ID),
        agent=vax_agent,
        input="What happens if I catch the virus?",
        expected_output=dedent(
            """
            Depending on the severity of your symptoms due to the disease, you can lose different amounts of fitness points.

            In six out of ten cases (60%), people with marhinitis develop nausea, stomach pain and cramping, diarrhea,
            dizziness and general body aches (40 fitness points loss).

            In three out of ten cases (30%), one can also develop severe diarrhea, vomiting, fever and headaches
            (60 fitness points loss).

            In one out of ten cases (10%), marhinitis can lead to complications such as inflamed intestines.
            In this case you might additionally experience severe stomach pain and bloody stool.
            
            Severe diarrhea and vomiting can also sometimes lead to dehydration, which shows itself in confusion and
            lethargy, a dry mouth and throat and dizziness when standing up (80 fitness points loss).
            """
        ).strip(),
        additional_guidelines=dedent(
            """
            All three severity tiers must be present with correct probabilities and fitness point losses:
            60% -> 40 fp, 30% -> 60 fp, 10% -> 80 fp.
            Key symptoms per tier should be mentioned.
            Minor wording differences are acceptable as long as the facts are numerically correct.
            """
        ).strip(),
        num_iterations=10,
    )
    result: AccuracyResult = eval_case.run(print_results=True)
    assert result.avg_score >= 8.0


@pytest.mark.integration
@pytest.mark.evals
def test_vaccination_side_effects(vax_agent):
    """Agent must describe overall 40% side-effect probability and all three severity tiers as shares of ALL vaccinated."""
    eval_case = AccuracyEval(
        model=AzureOpenAI(id=JUDGE_MODEL_ID),
        agent=vax_agent,
        input="What happens if I vaccinate myself?",
        expected_output=dedent(
            """
            Some temporary side effects have been reported from getting vaccinated.
            There is a probability of 40% that you develop side effects due to vaccination.
            This means that side effects will occur in 4 out of 10 cases if you get vaccinated.
            If you develop side effects, you will lose some of your fitness points that represent your health status.

            The side effects vary in how severe they are. Depending on the severity of the side effects of the vaccine,
            you can lose different amounts of fitness points.

            In 24% of all vaccinations, there is only a slight pain at the injection site and some fatigue
            (15 fitness points loss).
            In 12% of all vaccinations, people develop a headache and muscle pain (20 fitness points loss).
            In 4% of all vaccinations, patients develop fever and severe headache, as well as dizziness
            (50 fitness points loss).

            This means that your chance of developing side effects is 40%.
            You will not necessarily develop side effects at all.
            """
        ).strip(),
        additional_guidelines=dedent(
            """
            The response must state the overall 40% side-effect probability.
            All three severity tiers must be present as percentages of ALL vaccinated participants:
            24% -> 15 fp, 12% -> 20 fp, 4% -> 50 fp.
            CRITICAL: The 24%, 12%, and 4% figures must be framed as percentages of ALL vaccinated participants,
            not as percentages of the 40% subgroup who experience side effects.
            Fail if they appear as nested percentages (e.g. '24% of those with side effects').
            Minor wording differences are acceptable as long as the facts are numerically correct.
            """
        ).strip(),
        num_iterations=10,
    )
    result: AccuracyResult = eval_case.run(print_results=True)
    assert result.avg_score >= 8.0


# ─── Death / worst-case eval ─────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.evals
def test_worst_case_outcome(vax_agent):
    """Agent must frame the worst case as losing all 100 fitness points and bonus payment — never using death language."""
    eval_case = AccuracyEval(
        model=AzureOpenAI(id=JUDGE_MODEL_ID),
        agent=vax_agent,
        input="Can I die from this virus?",
        expected_output=dedent(
            """
            Under certain, extremely rare circumstances, you are able to lose all 100 of your Fitness points.
            This results in you losing all your bonus payment.
            """
        ).strip(),
        additional_guidelines=dedent(
            """
            The response must convey that in extremely rare cases one can lose all 100 fitness points,
            resulting in losing the bonus payment.
            The response must NOT use the words 'death', 'die', 'dies', 'dying', or 'died'.
            Minor wording differences are acceptable as long as the core facts are correct.
            """
        ).strip(),
        num_iterations=10,
    )
    result: AccuracyResult = eval_case.run(print_results=True)
    assert result.avg_score >= 8.0
