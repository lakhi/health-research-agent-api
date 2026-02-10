from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from knowledge_base import marhinovirus_knowledge_base
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_knowledge,
)
from agents.llm_models import LLMModel
from agents.agent_types import AgentType
from db import control_agent_db
from typing import Optional
from logging import getLogger

logger = getLogger(__name__)

# TODO #0: try better-agents framework using Antigravity? https://github.com/langwatch/better-agents
# TODO NOW: contents db proper implementation
# TODO #0: figure out SESSIONS for chat storage: https://docs.agno.com/basics/sessions/overview https://docs.agno.com/basics/state/overview
# TODO #1: impl the search and retrieval best practices: https://docs.agno.com/basics/knowledge/search-and-retrieval/overview


def get_control_marhinovirus_agent(
    model_id: str = LLMModel.GPT_4O,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = False,
) -> Agent:
    """
    Control condition Marhinovirus agent using normal catalog and standard language instructions.
    """
    if (
        marhinovirus_knowledge_base.NORMAL_DESCRIPTION is None
        or marhinovirus_knowledge_base.NORMAL_INSTRUCTIONS is None
    ):
        raise RuntimeError(
            "Agent configurations not initialized. "
            "Call initialize_agent_configs() before creating agents."
        )

    control_agent = Agent(
        id=AgentType.CONTROL_MARHINOVIRUS.id,
        name=AgentType.CONTROL_MARHINOVIRUS.name,
        model=AzureOpenAI(id=model_id),
        user_id=user_id,
        session_id=session_id,
        db=control_agent_db,
        description=marhinovirus_knowledge_base.NORMAL_DESCRIPTION,
        instructions=marhinovirus_knowledge_base.NORMAL_INSTRUCTIONS,
        knowledge=get_normal_catalog_knowledge(),
        search_knowledge=True,
        read_chat_history=True,
        add_history_to_context=True,
        num_history_runs=5,
        debug_mode=debug_mode,
    )

    return control_agent
