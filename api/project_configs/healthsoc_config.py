from typing import List

from agno.agent import Agent
from agno.knowledge.chunking.recursive import RecursiveChunking
from agno.knowledge.reader.pdf_reader import PDFReader

from agents.chunking_strategies import ChunkingStrategy
from agents.health_research_network_agent import get_healthsoc_agent
from api.project_configs.project_config import ProjectConfig, ProjectName
from knowledge_base.hrn_knowledge_base import get_research_articles_data


class HealthsocConfig(ProjectConfig):
    """Configuration for Health in Society healthsoc-network-chatbot project."""

    @property
    def project_name(self) -> str:
        return ProjectName.HEALTHSOC.value

    @property
    def cors_origins(self) -> List[str]:
        return [
            "https://hrn-agent-ui.niceground-23078755.westeurope.azurecontainerapps.io"
        ]

    @property
    def chunking_strategy(self) -> ChunkingStrategy:
        return ChunkingStrategy.RECURSIVE

    def get_agents(self) -> List[Agent]:
        """Initialize healthsoc agent."""
        return [get_healthsoc_agent()]

    async def load_knowledge(self, agents: List[Agent]) -> None:
        """Load Health in Society Research Network knowledge into healthsoc agent."""
        # Get PDF reader with project's chunking strategy
        pdf_reader = PDFReader(
            chunking_strategy=RecursiveChunking(
                chunk_size=self.chunking_strategy.chunk_size, overlap=400
            )
        )

        try:
            kb_data = get_research_articles_data()
            healthsoc_agent = agents[0]

            for item in kb_data:
                await healthsoc_agent.knowledge.add_content_async(
                    name=f"HRN Research - {item['metadata'].get('network_member_name', 'Unknown')}",
                    url=item["url"],
                    reader=pdf_reader,
                    metadata=item["metadata"],
                    skip_if_exists=True,
                )
            print(
                f"✅ Knowledge loaded successfully for healthsoc agent ({len(kb_data)} documents)"
            )
        except Exception as e:
            print(f"❌ Error loading Health in Society knowledge: {e}")
            raise
