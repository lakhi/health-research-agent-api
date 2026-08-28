from logging import getLogger

from agno.agent import Agent

logger = getLogger(__name__)

_registry: dict[str, Agent] = {}


def register_agents(agents: list[Agent]) -> None:
    """Store startup agents in the registry, keyed by agent.id."""
    for agent in agents:
        if agent.id is None:
            # Agno types Agent.id as Optional. Registering under None would create an entry
            # get_agent() can never reach, so fail at startup instead of dispatching into a hole.
            raise ValueError(f"Agent {agent.name!r} has no id and cannot be registered for dispatch.")
        _registry[agent.id] = agent
        logger.debug("Registered agent: %s", agent.id)


def get_agent(agent_id: str) -> Agent:
    """Look up a pre-built agent by ID. Raises ValueError if not found."""
    agent = _registry.get(agent_id)
    if agent is None:
        raise ValueError(f"Agent '{agent_id}' not found in registry. Available: {list(_registry.keys())}")
    return agent
