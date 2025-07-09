from enum import Enum
from typing import List, Optional

from agents.marhonivirus_agent import get_marhinovirus_agent


class AgentType(Enum):
    MARHONIVIRUS_AGENT = "marhonivirus_agent"


def get_available_agents() -> List[str]:
    """Returns a list of all available agent IDs."""
    return [agent.value for agent in AgentType]


def get_agent(
    model_id: str = "gpt-4.1",
    agent_id: Optional[AgentType] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
):
    if agent_id == AgentType.MARHONIVIRUS_AGENT:
        return get_marhinovirus_agent(
            model_id=model_id,
            user_id=user_id,
            session_id=session_id,
            debug_mode=debug_mode,
        )
    # elif agent_id == AgentType.AGNO_debug_mode)

    raise ValueError(f"Agent: {agent_id} not found")
