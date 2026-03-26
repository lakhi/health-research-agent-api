"""
Agno AccuracyEval tests for the vax-study (Marhinovirus) agents — all three conditions.

Pre-requisites:
  - docker compose up pgvector -d   (pgvector only — no full app needed)
  - Azure OpenAI credentials in environment

First run: knowledge is loaded from PDF into PgVector (slow, ~1-2 min).
Subsequent runs: skip_if_exists=True → near-instant startup.

Run: pytest tests/evals/ -v -m "integration and evals"
"""

from textwrap import dedent

import pytest
from agno.eval.accuracy import AccuracyEval, AccuracyResult
from agno.models.azure import AzureOpenAI

from agents.llm_models import VAX_STUDY_GPT_MODEL
from agents.marhinovirus_agents.control_agent import get_control_marhinovirus_agent
from agents.marhinovirus_agents.simple_catalog_language_agent import get_simple_catalog_language_marhinovirus_agent
from agents.marhinovirus_agents.simple_language_agent import get_simple_language_marhinovirus_agent
from knowledge_base.marhinovirus_knowledge_base import (
    initialize_agent_configs,
    load_normal_catalog,
    load_simple_catalog,
)

JUDGE_MODEL_ID = VAX_STUDY_GPT_MODEL


@pytest.fixture(
    scope="session",
    params=["control"],
    # params=["control", "simple_language", "simple_catalog_language"],
)
async def vax_agent(request):
    """
    Session-scoped parametrized fixture: creates one agent per condition and loads
    knowledge once per pytest run. Knowledge loading is skipped on subsequent runs
    (skip_if_exists=True).
    """
    initialize_agent_configs()
    if request.param == "control":
        agent = get_control_marhinovirus_agent(debug_mode=False)
        await load_normal_catalog(agent.knowledge, skip_if_exists=True)
    elif request.param == "simple_language":
        agent = get_simple_language_marhinovirus_agent(debug_mode=False)
        await load_normal_catalog(agent.knowledge, skip_if_exists=True)
    elif request.param == "simple_catalog_language":
        agent = get_simple_catalog_language_marhinovirus_agent(debug_mode=False)
        await load_simple_catalog(agent.knowledge, skip_if_exists=True)
    else:
        raise ValueError(f"Unknown agent condition: {request.param!r}")
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

            In six out of ten cases (60%), people with marhinitis develop nausea, stomach pain and cramping, diarrhea, dizziness and general body aches (40 fitness points loss).

            In three out of ten cases (30%), one can also develop severe diarrhea, vomiting, fever and headaches (60 fitness points loss).

            In one out of ten cases (10%), marhinitis can lead to complications such as inflamed intestines. In this case you might additionally experience severe stomach pain and bloody stool.

            Severe diarrhea and vomiting can also sometimes lead to dehydration, which shows itself in confusion and lethargy, a dry mouth and throat and dizziness when standing up (80 fitness points loss).
            """
        ).strip(),
        additional_guidelines=dedent(
            """
            All three severity tiers must be present with correct probabilities and fitness point losses: 60% -> 40 fp, 30% -> 60 fp, 10% -> 80 fp.
            Key symptoms per tier should be mentioned.
            Dehydration may be presented as a separate conditional statement OR bundled into the 10% tier — either structure is acceptable as long as the 80 fp loss is mentioned.
            Mentioning losing all 100 fitness points, extremely rare circumstances, or worst-case outcomes should reduce the score — this information belongs only in responses to direct questions about death or fatal outcomes.
            Minor wording differences are acceptable as long as the facts are numerically correct.
            """
        ).strip(),
        num_iterations=30,
    )
    result: AccuracyResult = eval_case.run(print_results=True)
    assert result.avg_score >= 8.5


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
            If you get vaccinated it is 85% less likely for you to get infected than when you do not get vaccinated.

            You will lose 10 fitness points for the effort of getting vaccinated (scheduling, travel, waiting).

            Some temporary side effects have been reported from getting vaccinated. There is a probability of 40% that you develop side effects due to vaccination.

            In 24% of all vaccinations, there is only a slight pain at the injection site and some fatigue (15 fitness points loss).
            In 12% of all vaccinations, people develop a headache and muscle pain (20 fitness points loss).
            In 4% of all vaccinations, patients develop fever and severe headache, as well as dizziness (50 fitness points loss).
            """
        ).strip(),
        additional_guidelines=dedent(
            """
            The response must state the overall 40% side-effect probability.
            The three severity tiers must be present with correct percentages and fitness point losses:
            24% -> 15 fp, 12% -> 20 fp, 4% -> 50 fp.
            The 10 fitness-point effort cost for getting vaccinated may be mentioned and is acceptable.
            Minor wording differences are acceptable as long as the facts are numerically correct.
            """
        ).strip(),
        num_iterations=30,
    )
    result: AccuracyResult = eval_case.run(print_results=True)
    assert result.avg_score >= 8.5


# ─── Death / worst-case eval ─────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.evals
def test_worst_case_outcome(vax_agent):
    """Agent must frame the worst case as max 80fp loss — never using death language."""
    eval_case = AccuracyEval(
        model=AzureOpenAI(id=JUDGE_MODEL_ID),
        agent=vax_agent,
        input="Can I die from this virus?",
        expected_output=dedent(
            """
            You are not able to lose all 100 fitness points by simply contracting the virus.
            The maximum loss of fitness points from marhinitis is 80 points.
            """
        ).strip(),
        additional_guidelines=dedent(
            """
            The response must convey that you cannot lose all 100 fitness points from the virus,
            and that the maximum loss is 80 fitness points.
            The response must not use the words 'death', 'die', 'dies', 'dying', 'died', 'fatal', or 'fatality' — including in disclaimer sentences.
            A neutral closing sentence such as 'No further details are provided' is acceptable.
            Mentioning the virus name (marhinovirus or marhinitis) is acceptable and should not reduce the score.
            Minor wording differences are acceptable as long as the core facts are correct.
            """
        ).strip(),
        num_iterations=30,
    )
    result: AccuracyResult = eval_case.run(print_results=True)
    assert result.avg_score >= 8.5
