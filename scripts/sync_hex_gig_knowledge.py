"""Entrypoint for the HeX-GiG knowledge sync Container Apps Job (daily, and on demand).

Brings the knowledge base in step with u:Cloud papers, the members CSV and the news feed, then
makes sure the vector table is halfvec and HNSW-indexed, then enforces metrics retention. This is
the only writer of the HeX knowledge tables; the API never loads knowledge (#42).

Each source is synced independently, so a u:Cloud outage doesn't stop the news from updating.
The run exits non-zero if any source failed or a deletion was held back by the guard, so the
job execution shows as Failed in Azure.

Usage:
    python scripts/sync_hex_gig_knowledge.py

Locally, against the compose pgvector:
    docker compose run --rm -e PROJECT_NAME=hex-gig api python scripts/sync_hex_gig_knowledge.py
"""

import asyncio
import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable

from knowledge_base import get_azure_embedder
from knowledge_base.hex_gig_knowledge_base import get_hex_gig_knowledge, get_hex_gig_pdf_reader
from knowledge_base.hex_gig_sync import SyncReport, sync_member_profiles, sync_news, sync_research_papers
from knowledge_base.vector_store import ensure_vector_schema, pgvector_of
from services.nextcloud_client import NextcloudClient
from services.nextcloud_pdf_provider import NextcloudPDFProvider

logger = logging.getLogger("hex_gig_knowledge_sync")

UCLOUD_WEBDAV_URL = "https://ucloud.univie.ac.at/public.php/webdav/"

# Retention window for the anonymous agent_usage_metrics table. Read directly from
# the environment (not api.settings) so this lightweight job avoids the budget-var
# validation that ApiSettings enforces for the hex_gig project.
_DEFAULT_METRICS_RETENTION_DAYS = 180


def _purge_old_metrics() -> None:
    """Best-effort retention enforcement; never fails the sync job."""
    try:
        days = int(os.getenv("METRICS_RETENTION_DAYS", str(_DEFAULT_METRICS_RETENTION_DAYS)))
    except ValueError:
        days = _DEFAULT_METRICS_RETENTION_DAYS
        logger.warning("Invalid METRICS_RETENTION_DAYS; falling back to %d days", days)

    from services.metrics_retention import purge_metrics_older_than

    deleted = purge_metrics_older_than(days)
    logger.info("Metrics retention: purged %d rows older than %d days", deleted, days)


def _ucloud_provider() -> NextcloudPDFProvider:
    share_token = os.environ.get("UCLOUD_SHARE_TOKEN", "")
    if not share_token:
        raise ValueError("UCLOUD_SHARE_TOKEN environment variable is required for HeX-GiG")
    client = NextcloudClient(
        webdav_public_url=UCLOUD_WEBDAV_URL,
        share_token=share_token,
        share_password=os.environ.get("UCLOUD_SHARE_PASSWORD", ""),
    )
    return NextcloudPDFProvider(client)


async def _run(source: str, sync: Callable[[], Awaitable[SyncReport]]) -> SyncReport:
    """Run one source's sync; a failure is reported, never allowed to stop the other sources."""
    try:
        return await sync()
    except Exception as exc:
        logger.exception("%s sync failed; nothing was changed for it after the failure", source)
        return SyncReport(source=source, error=f"{type(exc).__name__}: {exc}")


async def _main() -> int:
    started = time.monotonic()

    # Fail fast with a clear message rather than marking every document failed one by one.
    if not get_azure_embedder().get_embedding("test"):
        logger.error("Azure embedder returned no embedding; aborting the sync")
        return 1

    knowledge = get_hex_gig_knowledge()
    reports = [
        await _run(
            "research papers", lambda: sync_research_papers(knowledge, _ucloud_provider(), get_hex_gig_pdf_reader())
        ),
        await _run("member profiles", lambda: sync_member_profiles(knowledge)),
        await _run("news", lambda: sync_news(knowledge)),
    ]

    # After the load, not before: an index built over the finished table is faster to build and
    # a better graph than one grown insert by insert. A no-op once the index exists.
    schema_ok = True
    try:
        await asyncio.to_thread(ensure_vector_schema, pgvector_of(knowledge))
    except Exception:
        schema_ok = False
        logger.exception("Could not make the HeX vector table halfvec and HNSW-indexed")

    _purge_old_metrics()

    for report in reports:
        logger.info(report.summary())
    logger.info("Knowledge sync finished in %.1fs", time.monotonic() - started)
    return 0 if schema_ok and all(report.ok for report in reports) else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        sys.exit(asyncio.run(_main()))
    except Exception:
        logger.exception("HeX knowledge sync failed")
        sys.exit(1)
