from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from knowledge_base import marhinovirus_knowledge_base
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_knowledge,
)
from agents.llm_models import VAX_STUDY_GPT_MODEL
from agents.agent_types import AgentType
from db import simple_language_db

from typing import Optional
from logging import getLogger

logger = getLogger(__name__)


def get_simple_language_marhinovirus_agent(
    model_id: str = VAX_STUDY_GPT_MODEL,
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
        id=AgentType.SIMPLE_LANGUAGE_MARHINOVIRUS.id,
        name=AgentType.SIMPLE_LANGUAGE_MARHINOVIRUS.name,
        db=simple_language_db,
        model=AzureOpenAI(id=model_id),
        description=marhinovirus_knowledge_base.SIMPLE_DESCRIPTION,
        instructions=[
            marhinovirus_knowledge_base.SIMPLE_INSTRUCTIONS,
            "When the knowledge base describes a consequence as a possible or occasional additional outcome (e.g. 'can also sometimes lead to...'), preserve that conditional framing in your response. Do not present conditional outcomes as guaranteed accompaniments of another tier.",
            "If asked about death or fatal outcomes, respond with exactly two statements: (1) that under extremely rare circumstances one can lose all 100 fitness points, and (2) that this results in losing all bonus payment. Do not use the words 'death', 'die', 'dies', 'dying', 'died', 'fatal', or 'fatality'. Do not add any other statements.",
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
        # debug_mode=True,
    )

    return simple_language_agent
