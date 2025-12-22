from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from knowledge_base import marhinovirus_knowledge_base
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_knowledge,
)
from agents.llm_models import LLMModel
from db import agent_db

from typing import Optional
from logging import getLogger

logger = getLogger(__name__)


def get_simple_language_marhinovirus_agent(
    model_id: str = LLMModel.GPT_4O,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
) -> Agent:
    """
    Simple language Marhinovirus agent using normal catalog with simplified language instructions.
    """
    if (
        marhinovirus_knowledge_base.SIMPLE_DESCRIPTION is None
        or marhinovirus_knowledge_base.SIMPLE_INSTRUCTIONS is None
    ):
        raise RuntimeError(
            "Agent configurations not initialized. "
            "Call initialize_agent_configs() before creating agents."
        )

    simple_language_agent = Agent(
        id="simple_lg_agent",
        name="Simple Language Marhinovirus Agent",
        db=agent_db,
        model=AzureOpenAI(id=model_id),
        description=marhinovirus_knowledge_base.SIMPLE_DESCRIPTION,
        instructions=marhinovirus_knowledge_base.SIMPLE_INSTRUCTIONS,
        knowledge=get_normal_catalog_knowledge(),
        search_knowledge=True,
        read_chat_history=True,
        add_history_to_context=True,
        num_history_runs=5,
        # debug_mode=True,
    )

    return simple_language_agent
