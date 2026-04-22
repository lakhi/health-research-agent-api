import asyncio
from typing import List

from agno.agent import Agent

from agents.marhinovirus_agents.control_agent import get_control_marhinovirus_agent
from agents.marhinovirus_agents.simple_language_agent import get_simple_language_marhinovirus_agent
from api.project_configs.project_config import ProjectConfig, ProjectName
from knowledge_base.marhinovirus_knowledge_base import (
    initialize_agent_configs,
    load_normal_catalog,
)


class VaxStudyConfig(ProjectConfig):
    """Configuration for Marhinovirus vax-study-chatbot project."""

    @property
    def project_name(self) -> str:
        return ProjectName.VAX_STUDY.value

    @property
    def cors_origins(self) -> List[str]:
        # TODO: remove CORS-coupling between FE and BE projects
        return ["https://marhinovirus-infobot.wittywave-d78264d4.swedencentral.azurecontainerapps.io"]

    def get_agents(self) -> List[Agent]:
        """Initialize vax-study agents (c, sl)."""
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
        ]

    async def load_knowledge(self, agents: List[Agent]) -> None:
        """Load Marhinovirus research catalog into both agents."""
        try:
            await asyncio.gather(*(load_normal_catalog(agent.knowledge, skip_if_exists=False) for agent in agents))
            print(f"✅ Knowledge loaded successfully for {len(agents)} vax-study agents")
        except Exception as e:
            print(f"❌ Error loading Marhinovirus knowledge: {e}")
            raise
