from typing import List

from agno.agent import Agent
from agno.knowledge.reader.pdf_reader import PDFReader

from agents.hex_gig_agent import get_hex_gig_agent
from api.project_configs.project_config import ProjectConfig, ProjectName
from knowledge_base.hex_gig_knowledge_base import get_member_profiles_data, get_research_articles_from_ucloud
from knowledge_base.hex_gig_rss_knowledge import aload_rss_into_knowledge
from services.nextcloud_client import NextcloudClient
from services.nextcloud_pdf_provider import NextcloudPDFProvider

UCLOUD_WEBDAV_URL = "https://ucloud.univie.ac.at/public.php/webdav/"


class HexGigConfig(ProjectConfig):
    """Configuration for the HeX-GiG (Health Network Explorer) project."""

    @property
    def project_name(self) -> str:
        return ProjectName.HEX_GIG.value

    @property
    def cors_origins(self) -> List[str]:
        return [
            "https://hex-gig.univie.ac.at",
            "https://hex-gig-agent-ui.bravemeadow-0cb4208f.swedencentral.azurecontainerapps.io",  # remove after ZID CNAME is live
        ]

    def get_agents(self) -> List[Agent]:
        """Initialize hex_gig agent."""
        return [get_hex_gig_agent()]

    async def load_knowledge(self, agents: List[Agent]) -> None:
        """Load HeX-GiG knowledge from u:Cloud and RSS into the hex_gig agent."""
        import os

        load_knowledge = os.environ.get("LOAD_HEX_GIG_KNOWLEDGE", "true").lower() == "true"
        if not load_knowledge:
            print("⏭️  Skipping HeX knowledge loading (LOAD_HEX_GIG_KNOWLEDGE=false)")
            return

        from knowledge_base import get_azure_embedder

        embedder = get_azure_embedder()
        try:
            test_result = embedder.get_embedding("test")
            if not test_result:
                raise ValueError("Embedder returned empty result")
            print("✅ Azure embedder verified")
        except Exception as e:
            print(f"❌ Azure embedder check failed — aborting knowledge load: {e}")
            raise

        from agno.knowledge.chunking.semantic import SemanticChunking

        pdf_reader = PDFReader(
            chunking_strategy=SemanticChunking(
                embedder="minishlab/potion-base-32M",
                chunk_size=2000,
                similarity_threshold=0.5,
                similarity_window=3,
            )
        )

        try:
            hex_gig_agent = agents[0]

            # Load research papers from u:Cloud (Nextcloud)
            share_token = os.environ.get("UCLOUD_SHARE_TOKEN", "")
            share_password = os.environ.get("UCLOUD_SHARE_PASSWORD", "")

            if not share_token:
                raise ValueError("UCLOUD_SHARE_TOKEN environment variable is required for HeX-GiG project")

            client = NextcloudClient(
                webdav_public_url=UCLOUD_WEBDAV_URL,
                share_token=share_token,
                share_password=share_password,
            )
            provider = NextcloudPDFProvider(client)
            discovered = await provider.discover_and_download()

            kb_data = get_research_articles_from_ucloud(discovered)
            for i, item in enumerate(kb_data, 1):
                print(f"  [{i}/{len(kb_data)}] Embedding: {item['name']}")
                await hex_gig_agent.knowledge.ainsert(
                    name=item["name"],
                    path=str(item["path"]),
                    reader=pdf_reader,
                    metadata=item["metadata"],
                    skip_if_exists=True,
                )
            print(f"✅ Knowledge loaded from u:Cloud ({len(kb_data)} documents)")

            # Load RSS news
            seen, _ = await aload_rss_into_knowledge(hex_gig_agent.knowledge)
            print(f"✅ RSS news loaded for hex_gig agent ({seen} articles processed)")

            # Load member profiles from CSV
            member_profiles = get_member_profiles_data()
            for item in member_profiles:
                await hex_gig_agent.knowledge.ainsert(
                    name=item["name"],
                    text_content=item["text_content"],
                    metadata=item["metadata"],
                    skip_if_exists=True,
                )
            print(f"✅ Member profiles loaded ({len(member_profiles)} members)")
        except Exception as e:
            print(f"❌ Error loading HeX-GiG knowledge: {e}")
            raise
