from typing import List

from agno.agent import Agent

from agents.chunking_strategies import ChunkingStrategy
from api.project_configs.project_config import ProjectConfig, ProjectName
from agno.knowledge.chunking.recursive import RecursiveChunking
from agno.knowledge.reader.pdf_reader import PDFReader
from agents.marhinovirus_agents.control_agent import get_control_marhinovirus_agent
from agents.marhinovirus_agents.simple_catalog_language_agent import (
    get_simple_catalog_language_marhinovirus_agent,
)
from agents.marhinovirus_agents.simple_language_agent import (
    get_simple_language_marhinovirus_agent,
)
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_url,
    get_simple_catalog_url,
    initialize_agent_configs,
)


class VaxStudyConfig(ProjectConfig):
    """Configuration for Marhinovirus vax-study-chatbot project."""

    @property
    def project_name(self) -> str:
        return ProjectName.VAX_STUDY.value

    @property
    def cors_origins(self) -> List[str]:
        # TODO: remove CORS-coupling between FE and BE projects
        return [
            "https://marhinovirus-study-ui.whitedesert-10483e06.westeurope.azurecontainerapps.io"
        ]

    @property
    def chunking_strategy(self) -> ChunkingStrategy:
        return ChunkingStrategy.RECURSIVE

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
        pdf_reader = PDFReader(
            chunking_strategy=RecursiveChunking(chunk_size=1200, overlap=120)
        )

        try:
            # Load normal catalog for control_agent and simple_lg_agent
            await agents[0].knowledge.add_content_async(
                name="Marhinovirus Normal Catalog",
                url=get_normal_catalog_url(),
                reader=pdf_reader,
                skip_if_exists=True,
            )
            await agents[1].knowledge.add_content_async(
                name="Marhinovirus Normal Catalog",
                url=get_normal_catalog_url(),
                reader=pdf_reader,
                skip_if_exists=True,
            )
            # Load simple catalog for simple_catalog_lg_agent
            await agents[2].knowledge.add_content_async(
                name="Marhinovirus Simple Catalog",
                url=get_simple_catalog_url(),
                reader=pdf_reader,
                skip_if_exists=True,
            )
            print("✅ Knowledge loaded successfully for 3 vax-study agents")
        except Exception as e:
            print(f"❌ Error loading Marhinovirus knowledge: {e}")
            raise
