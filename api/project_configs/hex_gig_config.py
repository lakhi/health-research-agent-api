import asyncio
import logging
from typing import List

from agno.agent import Agent

from agents.hex_gig_agent import get_hex_gig_agent
from api.project_configs.project_config import ProjectConfig, ProjectName, require_knowledge
from knowledge_base.vector_store import pgvector_of, vector_schema_problems

logger = logging.getLogger(__name__)


class HexGigConfig(ProjectConfig):
    """Configuration for the HeX-GiG (Health Network Explorer) project."""

    @property
    def project_name(self) -> str:
        return ProjectName.HEX_GIG.value

    @property
    def cors_origins(self) -> List[str]:
        return [
            "https://hex-gig.univie.ac.at",
            "https://hex-gig-agent-ui.bravemeadow-0cb4208f.swedencentral.azurecontainerapps.io",  # Azure-hosted UI; drop when it is retired in favour of the ZID webspace
            "https://statsbot.univie.ac.at",  # TEMPORARY (11 Aug 2026): ZID-webspace hosting feasibility test — remove once concluded
        ]

    def get_agents(self) -> List[Agent]:
        """Initialize hex_gig agent."""
        return [get_hex_gig_agent()]

    async def load_knowledge(self, agents: List[Agent]) -> None:
        """Check the knowledge base is searchable; loading it is the sync job's work, not startup's.

        The ``hex-gig-knowledge-sync`` job (scripts/sync_hex_gig_knowledge.py) keeps the knowledge
        base in step with u:Cloud, the members CSV and the news feed. Loading here used to take
        ~4 min on every replica start, rewrite all ~26k chunk rows, and stop the API from starting
        whenever u:Cloud or the embedder was down (#42) — and Azure replaces the replica every few
        days, unannounced. Startup now takes seconds and depends only on the database.

        A missing index is logged, not raised: the API still answers without it, just slowly.
        """
        knowledge = require_knowledge(agents[0])
        try:
            problems = await asyncio.to_thread(vector_schema_problems, pgvector_of(knowledge))
        except Exception:
            logger.exception("Could not check the HeX vector table")
            return

        for problem in problems:
            logger.error("HeX vector search is not ready: %s", problem)
        if not problems:
            logger.info("HeX vector table is halfvec and HNSW-indexed")
