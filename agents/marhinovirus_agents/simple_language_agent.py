from logging import getLogger

from agno.agent import Agent
from agno.models.azure import AzureOpenAI

from agents.agent_types import AgentType
from agents.llm_models import VAX_STUDY_GPT_MODEL
from agents.marhinovirus_agents.shared_instructions import SHARED_MARHINOVIRUS_INSTRUCTIONS
from db import simple_language_db
from knowledge_base import marhinovirus_knowledge_base
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_knowledge,
)

logger = getLogger(__name__)


def get_simple_language_marhinovirus_agent() -> Agent:
    """Simple language Marhinovirus agent using normal catalog with simplified language instructions."""
    if (
        marhinovirus_knowledge_base.SIMPLE_DESCRIPTION is None
        or marhinovirus_knowledge_base.SIMPLE_INSTRUCTIONS is None
    ):
        raise RuntimeError(
            "Agent configurations not initialized. Call initialize_agent_configs() before creating agents."
        )

    simple_language_agent = Agent(
        id=AgentType.SIMPLE_LANGUAGE_MARHINOVIRUS.id,
        name=AgentType.SIMPLE_LANGUAGE_MARHINOVIRUS.name,
        db=simple_language_db,
        model=AzureOpenAI(id=VAX_STUDY_GPT_MODEL),
        description=marhinovirus_knowledge_base.SIMPLE_DESCRIPTION,
        instructions=[
            marhinovirus_knowledge_base.SIMPLE_INSTRUCTIONS,
            *SHARED_MARHINOVIRUS_INSTRUCTIONS,
        ],
        knowledge=get_normal_catalog_knowledge(
            knowledge_name="Marhinovirus Normal Catalog - Simple Language",
            contents_db_name="marhino_normal_contents_simple_language",
        ),
        search_knowledge=True,
        read_chat_history=True,
        store_history_messages=True,
        add_history_to_context=True,
        num_history_runs=5,
        debug_mode=True,
    )

    return simple_language_agent
