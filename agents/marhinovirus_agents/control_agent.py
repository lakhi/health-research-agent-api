from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from knowledge_base import marhinovirus_knowledge_base
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_knowledge,
)
from agents.llm_models import VAX_STUDY_GPT_MODEL
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
    model_id: str = VAX_STUDY_GPT_MODEL,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
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
        instructions=[
            marhinovirus_knowledge_base.NORMAL_INSTRUCTIONS,
            "When the knowledge base describes a consequence as a possible or occasional additional outcome (e.g. 'can also sometimes lead to...'), preserve that conditional framing in your response. Do not present conditional outcomes as guaranteed accompaniments of another tier.",
            "If asked about death or fatal outcomes, respond with exactly two statements: (1) that under extremely rare circumstances one can lose all 100 fitness points, and (2) that this results in losing all bonus payment. Do not use the words 'death', 'die', 'dies', 'dying', 'died', 'fatal', or 'fatality'. Do not add any other statements.",
        ],
        knowledge=get_normal_catalog_knowledge(
            knowledge_name="Marhinovirus Normal Catalog - Control",
            contents_db_name="marhino_normal_contents_control",
        ),
        search_knowledge=True,
        read_chat_history=True,
        store_history_messages=True,
        add_history_to_context=True,
        num_history_runs=5,
        debug_mode=debug_mode,
    )

    return control_agent
