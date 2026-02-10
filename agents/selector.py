from typing import List, Optional

from agents.agent_types import AgentType
from agents.llm_models import LLMModel
from agents.health_research_network_agent import get_healthsoc_agent
from agents.marhinovirus_agents.control_agent import get_control_marhinovirus_agent
from agents.marhinovirus_agents.simple_language_agent import (
    get_simple_language_marhinovirus_agent,
)
from agents.marhinovirus_agents.simple_catalog_language_agent import (
    get_simple_catalog_language_marhinovirus_agent,
)


def get_available_agents() -> List[str]:
    """Returns a list of all available agent IDs."""
    return [agent.id for agent in AgentType]


def get_agent(
    model_id: str = LLMModel.GPT_4O,
    agent_id: Optional[AgentType] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
):
    if agent_id == AgentType.HEALTHSOC_CHATBOT:
        # No parameters - session storage disabled for this agent
        return get_healthsoc_agent()
    elif agent_id == AgentType.CONTROL_MARHINOVIRUS:
        return get_control_marhinovirus_agent(
            model_id=model_id,
            user_id=user_id,
            session_id=session_id,
            debug_mode=debug_mode,
        )
    elif agent_id == AgentType.SIMPLE_LANGUAGE_MARHINOVIRUS:
        return get_simple_language_marhinovirus_agent(
            model_id=model_id,
            user_id=user_id,
            session_id=session_id,
            debug_mode=debug_mode,
        )
    elif agent_id == AgentType.SIMPLE_CATALOG_LANGUAGE_MARHINOVIRUS:
        return get_simple_catalog_language_marhinovirus_agent(
            model_id=model_id,
            user_id=user_id,
            session_id=session_id,
            debug_mode=debug_mode,
        )

    raise ValueError(f"Agent: {agent_id} not found")
