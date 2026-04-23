from logging import getLogger

from agno.agent import Agent
from agno.models.azure import AzureOpenAI

from agents.agent_types import AgentType
from agents.llm_models import VAX_STUDY_GPT_MODEL
from agents.marhinovirus_agents.shared_instructions import SHARED_MARHINOVIRUS_INSTRUCTIONS
from knowledge_base import marhinovirus_knowledge_base
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_knowledge,
)

logger = getLogger(__name__)

# TODO #0: try better-agents framework using Antigravity? https://github.com/langwatch/better-agents
# TODO NOW: contents db proper implementation
# TODO #0: figure out SESSIONS for chat storage: https://docs.agno.com/basics/sessions/overview https://docs.agno.com/basics/state/overview
# TODO #1: impl the search and retrieval best practices: https://docs.agno.com/basics/knowledge/search-and-retrieval/overview


def get_control_marhinovirus_agent() -> Agent:
    """Control condition Marhinovirus agent using normal catalog and standard language instructions."""
    if (
        marhinovirus_knowledge_base.NORMAL_DESCRIPTION is None
        or marhinovirus_knowledge_base.NORMAL_INSTRUCTIONS is None
    ):
        raise RuntimeError(
            "Agent configurations not initialized. Call initialize_agent_configs() before creating agents."
        )

    control_agent = Agent(
        id=AgentType.CONTROL_MARHINOVIRUS.id,
        name=AgentType.CONTROL_MARHINOVIRUS.name,
        model=AzureOpenAI(id=VAX_STUDY_GPT_MODEL, temperature=0.2),
        description=marhinovirus_knowledge_base.NORMAL_DESCRIPTION,
        instructions=[
            marhinovirus_knowledge_base.NORMAL_INSTRUCTIONS,
            *SHARED_MARHINOVIRUS_INSTRUCTIONS,
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
        debug_mode=True,
    )

    return control_agent
