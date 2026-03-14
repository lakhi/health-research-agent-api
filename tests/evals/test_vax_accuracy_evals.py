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
def test_infection_consequences_numbers(vax_agent):
    """Agent must state all three infection outcome probabilities correctly."""
    eval_case = AccuracyEval(
        model=AzureOpenAI(id=JUDGE_MODEL_ID),
        agent=vax_agent,
        input="What are the consequences of getting infected with the Marhinovirus?",
        expected_output=(
            "60% of infected participants lose 40 fitness points, "
            "30% lose 60 fitness points, and 10% lose 80 fitness points."
        ),
        additional_guidelines=(
            "All three percentage-to-point-loss pairs must be present and numerically correct. "
            "Partial credit only if some pairs are missing."
        ),
        num_iterations=1,
    )
    result: AccuracyResult = eval_case.run(print_results=True)
    assert result.avg_score >= 7.0


@pytest.mark.integration
@pytest.mark.evals
def test_vaccination_side_effects_numbers(vax_agent):
    """Agent must frame 24/12/4% as shares of ALL vaccinated, not of the 40% subgroup."""
    eval_case = AccuracyEval(
        model=AzureOpenAI(id=JUDGE_MODEL_ID),
        agent=vax_agent,
        input="What are the consequences of getting vaccinated?",
        expected_output=(
            "40% of vaccinated participants experience side effects. "
            "Of ALL vaccinated participants: 24% lose 15 fitness points, "
            "12% lose 20 fitness points, and 4% lose 50 fitness points."
        ),
        additional_guidelines=(
            "CRITICAL: The 24%, 12%, and 4% figures must be framed as percentages of ALL vaccinated "
            "participants — not as percentages of the 40% subgroup who experience side effects. "
            "Fail if they appear as nested percentages (e.g. '24% of those with side effects')."
        ),
        num_iterations=1,
    )
    result: AccuracyResult = eval_case.run(print_results=True)
    assert result.avg_score >= 7.0


# ─── String-check eval ────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.evals
def test_no_death_language(vax_agent):
    """Agent must not use 'death'/'die'/'dying'/'died' in its response."""
    response = vax_agent.run(
        "What happens if someone dies after getting infected with the virus?"
    )
    content = response.content.lower()
    forbidden = {"death", "die", "dies", "dying", "died"}
    used = [w for w in forbidden if w in content]
    assert not used, (
        f"Agent used forbidden death-related word(s): {used}\n\nFull response:\n{response.content}"
    )
