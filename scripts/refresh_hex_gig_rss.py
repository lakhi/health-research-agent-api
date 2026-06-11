"""Standalone entrypoint for the HeX-GiG RSS refresh Container Apps Job.

Runs the same RSS-loading code path as app startup, but without booting the
FastAPI server. Designed to be invoked once per scheduled run (daily cron).

Usage:
    python scripts/refresh_hex_gig_rss.py
"""

import asyncio
import logging
import os
import sys
import time

from knowledge_base.hex_gig_knowledge_base import get_hex_gig_knowledge
from knowledge_base.hex_gig_rss_knowledge import aload_rss_into_knowledge

logger = logging.getLogger("hex_gig_rss_refresh")

# Retention window for the anonymous agent_usage_metrics table. Read directly from
# the environment (not api.settings) so this lightweight job avoids the budget-var
# validation that ApiSettings enforces for the hex_gig project.
_DEFAULT_METRICS_RETENTION_DAYS = 180


def _purge_old_metrics() -> None:
    """Best-effort retention enforcement; never fails the RSS refresh job."""
    try:
        days = int(os.getenv("METRICS_RETENTION_DAYS", str(_DEFAULT_METRICS_RETENTION_DAYS)))
    except ValueError:
        days = _DEFAULT_METRICS_RETENTION_DAYS
        logger.warning("Invalid METRICS_RETENTION_DAYS; falling back to %d days", days)

    from services.metrics_retention import purge_metrics_older_than

    deleted = purge_metrics_older_than(days)
    logger.info("Metrics retention: purged %d rows older than %d days", deleted, days)


async def _main() -> int:
    knowledge = get_hex_gig_knowledge()
    started = time.monotonic()
    seen, _ = await aload_rss_into_knowledge(knowledge)
    elapsed = time.monotonic() - started
    logger.info("RSS refresh: %d items processed in %.1fs", seen, elapsed)

    # Piggyback the daily metrics-retention purge on this scheduled run.
    _purge_old_metrics()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        sys.exit(asyncio.run(_main()))
    except Exception:
        logger.exception("RSS refresh failed")
        sys.exit(1)
