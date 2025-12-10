from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from knowledge_base.marhinovirus_knowledge_base import (
    SIMPLE_DESCRIPTION,
    SIMPLE_INSTRUCTIONS,
    get_normal_catalog_knowledge,
)
from agents.llm_models import LLMModel

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

    simple_language_agent = Agent(
        id="simple_lg_agent",
        name="Simple Language Marhinovirus Agent",
        model=AzureOpenAI(id=model_id),
        description=SIMPLE_DESCRIPTION,
        instructions=SIMPLE_INSTRUCTIONS,
        markdown=True,
        knowledge=get_normal_catalog_knowledge(),
        search_knowledge=True,
        read_chat_history=True,  # Agent decides when to look up
        add_history_to_context=True,
        num_history_runs=3,
        debug_mode=True,
    )

    return simple_language_agent
