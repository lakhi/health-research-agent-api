from typing import List

from agno.agent import Agent

from agents.marhinovirus_agents.control_agent import get_control_marhinovirus_agent
from agents.marhinovirus_agents.simple_catalog_language_agent import get_simple_catalog_language_marhinovirus_agent
from agents.marhinovirus_agents.simple_language_agent import get_simple_language_marhinovirus_agent
from api.project_configs.project_config import ProjectConfig, ProjectName
from knowledge_base.marhinovirus_knowledge_base import (
    initialize_agent_configs,
    load_normal_catalog,
    load_simple_catalog,
)


class VaxStudyConfig(ProjectConfig):
    """Configuration for Marhinovirus vax-study-chatbot project."""

    @property
    def project_name(self) -> str:
        return ProjectName.VAX_STUDY.value

    @property
    def cors_origins(self) -> List[str]:
        # TODO: remove CORS-coupling between FE and BE projects
        return ["https://marhinovirus-study-ui.whitedesert-10483e06.westeurope.azurecontainerapps.io"]

    def get_agents(self) -> List[Agent]:
        """Initialize vax-study agents (control, simple_lg, simple_catalog_lg)."""
        try:
            print("🚀 Initializing vax-study agent configurations from cloud...")
            initialize_agent_configs()
            print("✅ Agent configurations loaded successfully")
        except Exception as e:
            print(f"❌ Error loading agent configurations: {e}")
            raise

        return [
            get_control_marhinovirus_agent(),
            get_simple_language_marhinovirus_agent(),
            get_simple_catalog_language_marhinovirus_agent(),
        ]

    async def load_knowledge(self, agents: List[Agent]) -> None:
        """Load Marhinovirus research catalogs into all three agents."""
        try:
            await load_normal_catalog(agents[0].knowledge, skip_if_exists=False)
            await load_normal_catalog(agents[1].knowledge, skip_if_exists=False)
            await load_simple_catalog(agents[2].knowledge, skip_if_exists=False)
            print("✅ Knowledge loaded successfully for 3 vax-study agents")
        except Exception as e:
            print(f"❌ Error loading Marhinovirus knowledge: {e}")
            raise
