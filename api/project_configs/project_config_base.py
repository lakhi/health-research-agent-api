import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import List

from agno.agent import Agent

from agents.chunking_strategies import ChunkingStrategy


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

    @property
    @abstractmethod
    def chunking_strategy(self) -> ChunkingStrategy:
        """Default chunking strategy for knowledge loading."""
        pass

    @abstractmethod
    def get_agents(self) -> List[Agent]:
        """Initialize and return all agents for this project."""
        pass

    @abstractmethod
    async def load_knowledge(self, agents: List[Agent]) -> None:
        """Load knowledge bases into the provided agents."""
        pass


def get_project_config() -> ProjectConfig:
    """
    Factory function to get project configuration based on PROJECT_NAME env var.

    Returns:
        ProjectConfig instance for the active project

    Raises:
        ValueError: If PROJECT_NAME is missing or invalid
    """
    from api.project_configs.vax_study_config import VaxStudyConfig
    from api.project_configs.healthsoc_config import HealthsocConfig

    project = os.getenv("PROJECT_NAME")

    if not project:
        raise ValueError(
            "PROJECT_NAME environment variable must be set. "
            f"Valid values: {', '.join([p.value for p in ProjectName])}"
        )

    if project == ProjectName.VAX_STUDY.value:
        return VaxStudyConfig()
    elif project == ProjectName.HEALTHSOC.value:
        return HealthsocConfig()
    else:
        raise ValueError(
            f"Invalid PROJECT_NAME: '{project}'. "
            f"Must be one of: {', '.join([p.value for p in ProjectName])}"
        )
