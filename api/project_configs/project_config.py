from abc import ABC, abstractmethod
from enum import Enum
from typing import List

from agno.agent import Agent


class ProjectName(str, Enum):
    """Supported project names for multi-project API."""

    VAX_STUDY = "vax-study"
    HEALTHSOC = "healthsoc"


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
