import shutil
from typing import List

from agno.agent import Agent
from agno.knowledge.reader.pdf_reader import PDFReader

from agents.nex_agent import get_nex_agent
from api.project_configs.project_config import ProjectConfig, ProjectName
from knowledge_base.nex_knowledge_base import get_research_articles_from_ucloud
from knowledge_base.nex_rss_knowledge import get_rss_news_data
from services.nextcloud_client import NextcloudClient
from services.nextcloud_pdf_provider import NextcloudPDFProvider

UCLOUD_WEBDAV_URL = "https://ucloud.univie.ac.at/public.php/webdav/"


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
        """Load Network Explorer knowledge from u:Cloud and RSS into the nex agent."""
        import os

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
            nex_agent = agents[0]

            # Load research papers from u:Cloud (Nextcloud)
            share_token = os.environ.get("UCLOUD_SHARE_TOKEN", "")
            share_password = os.environ.get("UCLOUD_SHARE_PASSWORD", "")

            if not share_token:
                raise ValueError("UCLOUD_SHARE_TOKEN environment variable is required for NEX project")

            client = NextcloudClient(
                webdav_public_url=UCLOUD_WEBDAV_URL,
                share_token=share_token,
                share_password=share_password,
            )
            provider = NextcloudPDFProvider(client)
            discovered, temp_dir = await provider.discover_and_download()

            try:
                kb_data = get_research_articles_from_ucloud(discovered)
                for item in kb_data:
                    await nex_agent.knowledge.ainsert(
                        name=item["name"],
                        path=str(item["path"]),
                        reader=pdf_reader,
                        metadata=item["metadata"],
                        skip_if_exists=True,
                    )
                print(f"✅ Knowledge loaded from u:Cloud ({len(kb_data)} documents)")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

            # Load RSS news
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
