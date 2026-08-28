from abc import ABC, abstractmethod
from enum import Enum
from typing import List

from agno.agent import Agent
from agno.knowledge import Knowledge


def require_knowledge(agent: Agent) -> Knowledge:
    """Return *agent*'s attached Knowledge, or fail loudly.

    Agno types ``Agent.knowledge`` as ``KnowledgeProtocol | Callable[..., KnowledgeProtocol] |
    None`` so knowledge can be supplied lazily. Every agent here is built with a concrete
    Knowledge instance, so narrow it once — that keeps the knowledge-loading call sites readable
    and turns a would-be AttributeError deep inside startup into a clear message.
    """
    knowledge = agent.knowledge
    if not isinstance(knowledge, Knowledge):
        raise TypeError(
            f"Agent {agent.id!r} has no Knowledge instance attached "
            f"(got {type(knowledge).__name__}); knowledge loading cannot proceed."
        )
    return knowledge


class ProjectName(str, Enum):
    """Supported project names for multi-project API."""

    VAX_STUDY = "vax-study"
    HEX_GIG = "hex-gig"
    SSC_PSYCH = "ssc-psych"


class ProjectConfig(ABC):
    """
    Abstract base class for project-specific configuration.
    Each project must implement agent initialization, knowledge loading,
    CORS origins, and chunking strategy.
    """

    @property
    @abstractmethod
    def project_name(self) -> str:
        """Unique project identifier."""
        pass

    @property
    @abstractmethod
    def cors_origins(self) -> List[str]:
        """Project-specific CORS origins (UI URLs)."""
        pass

    @abstractmethod
    def get_agents(self) -> List[Agent]:
        """Initialize and return all agents for this project."""
        pass

    @abstractmethod
    async def load_knowledge(self, agents: List[Agent]) -> None:
        """Load knowledge bases into the provided agents."""
        pass
