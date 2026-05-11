"""Standalone entrypoint for the HeX-GiG RSS refresh Container Apps Job.

Runs the same RSS-loading code path as app startup, but without booting the
FastAPI server. Designed to be invoked once per scheduled run (daily cron).

Usage:
    python scripts/refresh_hex_gig_rss.py
"""

import asyncio
import logging
import sys
import time

from knowledge_base.hex_gig_knowledge_base import get_hex_gig_knowledge
from knowledge_base.hex_gig_rss_knowledge import aload_rss_into_knowledge

logger = logging.getLogger("hex_gig_rss_refresh")


async def _main() -> int:
    knowledge = get_hex_gig_knowledge()
    started = time.monotonic()
    seen, _ = await aload_rss_into_knowledge(knowledge)
    elapsed = time.monotonic() - started
    logger.info("RSS refresh: %d items processed in %.1fs", seen, elapsed)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        sys.exit(asyncio.run(_main()))
    except Exception:
        logger.exception("RSS refresh failed")
        sys.exit(1)
