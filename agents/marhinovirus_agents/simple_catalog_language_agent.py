from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from knowledge_base.marhinovirus_knowledge_base import (
    SIMPLE_DESCRIPTION,
    SIMPLE_INSTRUCTIONS,
    get_simple_catalog_knowledge,
)
from agents.llm_models import LLMModel
from db import agent_db

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

    simple_catalog_language_agent = Agent(
        id="simple_catalog_lg_agent",
        name="Simple Catalog and Language Marhinovirus Agent",
        model=AzureOpenAI(id=model_id),
        db=agent_db,
        description=SIMPLE_DESCRIPTION,
        instructions=SIMPLE_INSTRUCTIONS,
        knowledge=get_simple_catalog_knowledge(),
        search_knowledge=True,
        read_chat_history=True,
        add_history_to_context=True,
        num_history_runs=5,
        # debug_mode=True,
    )

    return simple_catalog_language_agent
