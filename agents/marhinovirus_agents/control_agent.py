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

# TODO 0: update the model on the Azure end and link it with the research studies resource group
# TODO 1: check the logs, some error comes regarding the session retrieval (usually in the first chat response)

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
        user_id=user_id,
        session_id=session_id,
        db=agent_db,
        description=NORMAL_DESCRIPTION,
        instructions=NORMAL_INSTRUCTIONS,
        markdown=True,
        knowledge=get_normal_catalog_knowledge(),
        add_knowledge_to_context=True,
        read_chat_history=True,
        add_history_to_context=True,
        num_history_runs=3,
    )

    return control_agent
