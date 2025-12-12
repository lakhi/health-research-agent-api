from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from knowledge_base.marhinovirus_knowledge_base import (
    NORMAL_DESCRIPTION,
    NORMAL_INSTRUCTIONS,
    get_normal_catalog_knowledge,
)
from agents.llm_models import LLMModel
from db import agent_db
from typing import Optional
from logging import getLogger

logger = getLogger(__name__)

# TODO NOW: contents db proper implementation
# TODO #0: figure out SESSIONS for chat storage: https://docs.agno.com/basics/sessions/overview https://docs.agno.com/basics/state/overview
# TODO #1: impl the search and retrieval best practices: https://docs.agno.com/basics/knowledge/search-and-retrieval/overview


def get_control_marhinovirus_agent(
    model_id: str = LLMModel.GPT_4O,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
) -> Agent:
    """
    Control condition Marhinovirus agent using normal catalog and standard language instructions.
    """

    control_agent = Agent(
        id="control_agent",
        name="Control Marhinovirus Agent",
        model=AzureOpenAI(id=model_id),
        # user_id=user_id,
        # session_id=session_id,
        db=agent_db,
        description=NORMAL_DESCRIPTION,
        instructions=NORMAL_INSTRUCTIONS,
        knowledge=get_normal_catalog_knowledge(),
        search_knowledge=True,
        read_chat_history=True,
        add_history_to_context=True,
        num_history_runs=5,
        # debug_mode=True,
    )

    return control_agent
