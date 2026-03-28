from typing import List

from agno.agent import Agent
from agno.knowledge.reader.pdf_reader import PDFReader

from agents.ssc_psych_agent import get_ssc_psych_agent
from api.project_configs.project_config import ProjectConfig, ProjectName


class SscPsychConfig(ProjectConfig):
    """Configuration for the SSC Psychologie project."""

    @property
    def project_name(self) -> str:
        return ProjectName.SSC_PSYCH.value

    @property
    def cors_origins(self) -> List[str]:
        # TBD — Azure Container App UI URL added once provisioned
        return []

    def get_agents(self) -> List[Agent]:
        """Initialize SSC Psychologie agent."""
        return [get_ssc_psych_agent()]

    async def load_knowledge(self, agents: List[Agent]) -> None:
        """Load SSC Psychologie knowledge from website scraping into the agent."""
        import os

        load_knowledge = os.environ.get("LOAD_SSC_PSYCH_KNOWLEDGE", "true").lower() == "true"
        if not load_knowledge:
            print("⏭️  Skipping SSC Psych knowledge loading (LOAD_SSC_PSYCH_KNOWLEDGE=false)")
            return

        from agno.knowledge.chunking.semantic import SemanticChunking

        from services.ssc_web_scraper import scrape_ssc_downloads, scrape_ssc_web_pages

        pdf_reader = PDFReader(
            chunking_strategy=SemanticChunking(
                embedder="minishlab/potion-base-32M",
                chunk_size=2000,
                similarity_threshold=0.5,
                similarity_window=3,
            )
        )

        try:
            ssc_agent = agents[0]

            # Load web pages from SSC website
            web_pages = scrape_ssc_web_pages()
            for i, item in enumerate(web_pages, 1):
                print(f"  [{i}/{len(web_pages)}] Embedding web page: {item['name']}")
                await ssc_agent.knowledge.ainsert(
                    name=item["name"],
                    text_content=item["text_content"],
                    metadata=item["metadata"],
                    skip_if_exists=True,
                )
            print(f"✅ Web pages loaded ({len(web_pages)} pages)")

            # Load PDF documents from SSC downloads section
            pdf_docs = scrape_ssc_downloads()
            for i, item in enumerate(pdf_docs, 1):
                print(f"  [{i}/{len(pdf_docs)}] Embedding PDF: {item['name']}")
                await ssc_agent.knowledge.ainsert(
                    name=item["name"],
                    path=str(item["path"]),
                    reader=pdf_reader,
                    metadata=item["metadata"],
                    skip_if_exists=True,
                )
            print(f"✅ PDF documents loaded ({len(pdf_docs)} documents)")

        except Exception as e:
            print(f"❌ Error loading SSC Psych knowledge: {e}")
            raise
