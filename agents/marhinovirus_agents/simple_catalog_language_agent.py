from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from knowledge_base import marhinovirus_knowledge_base
from knowledge_base.marhinovirus_knowledge_base import (
    get_simple_catalog_knowledge,
)
from agents.llm_models import LLMModel
from db import simple_cat_lg_db

from typing import Optional
from logging import getLogger

logger = getLogger(__name__)


def get_simple_catalog_language_marhinovirus_agent(
    model_id: str = LLMModel.GPT_4O,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
) -> Agent:
    """
    Simple catalog and language Marhinovirus agent using simple catalog with simplified language instructions.
    """
    if (
        marhinovirus_knowledge_base.SIMPLE_DESCRIPTION is None
        or marhinovirus_knowledge_base.SIMPLE_INSTRUCTIONS is None
    ):
        raise RuntimeError(
            "Agent configurations not initialized. "
            "Call initialize_agent_configs() before creating agents."
        )

    simple_catalog_language_agent = Agent(
        id="simple_catalog_lg_agent",
        name="Simple Catalog and Language Marhinovirus Agent",
        model=AzureOpenAI(id=model_id),
        db=simple_cat_lg_db,
        description=marhinovirus_knowledge_base.SIMPLE_DESCRIPTION,
        instructions=marhinovirus_knowledge_base.SIMPLE_INSTRUCTIONS,
        knowledge=get_simple_catalog_knowledge(),
        search_knowledge=True,
        read_chat_history=True,
        add_history_to_context=True,
        num_history_runs=5,
        enable_tracing=True,  # v2.3.5: Enable Native OpenTelemetry Tracing
        # debug_mode=True,
    )

    return simple_catalog_language_agent
