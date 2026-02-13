from typing import Optional, Union

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


def get_agent(
    model_id: str = LLMModel.GPT_4O,
    agent_id: Optional[Union[AgentType, str]] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
):
    if isinstance(agent_id, str):
        for agent_type in AgentType:
            if agent_id == agent_type.id:
                agent_id = agent_type
                break

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
