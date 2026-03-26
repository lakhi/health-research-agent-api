from typing import List

from agno.agent import Agent
from agno.knowledge.reader.pdf_reader import PDFReader

from agents.nex_agent import get_nex_agent
from api.project_configs.project_config import ProjectConfig, ProjectName
from knowledge_base.nex_knowledge_base import get_research_articles_data
from knowledge_base.nex_rss_knowledge import get_rss_news_data


class NexConfig(ProjectConfig):
    """Configuration for the Network Explorer project."""

    @property
    def project_name(self) -> str:
        return ProjectName.NEX.value

    @property
    def cors_origins(self) -> List[str]:
        return ["https://nex-agent-ui.niceground-23078755.westeurope.azurecontainerapps.io"]

    def get_agents(self) -> List[Agent]:
        """Initialize nex agent."""
        return [get_nex_agent()]

    async def load_knowledge(self, agents: List[Agent]) -> None:
        """Load Network Explorer knowledge into nex agent."""
        from agno.knowledge.chunking.semantic import SemanticChunking

        from knowledge_base import get_azure_embedder

        pdf_reader = PDFReader(
            chunking_strategy=SemanticChunking(
                embedder=get_azure_embedder(),
                chunk_size=2000,
                similarity_threshold=0.5,
                similarity_window=3,
            )
        )

        try:
            kb_data = get_research_articles_data()
            nex_agent = agents[0]

            for item in kb_data:
                first_name = item["metadata"].get("first_name", "").strip()
                last_name = item["metadata"].get("last_name", "").strip()
                member_name = " ".join(part for part in [first_name, last_name] if part) or "Unknown"

                await nex_agent.knowledge.ainsert(
                    name=f"NEX Research - {member_name}",
                    url=item["url"],
                    reader=pdf_reader,
                    metadata=item["metadata"],
                    skip_if_exists=True,
                )
            print(f"✅ Knowledge loaded successfully for nex agent ({len(kb_data)} documents)")

            news_items = get_rss_news_data()
            for item in news_items:
                await nex_agent.knowledge.ainsert(
                    name=item["name"],
                    text_content=item["text_content"],
                    metadata=item["metadata"],
                    skip_if_exists=True,
                )
            print(f"✅ RSS news loaded for nex agent ({len(news_items)} articles)")
        except Exception as e:
            print(f"❌ Error loading Network Explorer knowledge: {e}")
            raise
