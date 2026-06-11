"""
Retention enforcement for the anonymous agent_usage_metrics table.

Kept deliberately separate from ``metrics_service`` so it can be imported by the
lightweight scheduled job (scripts/refresh_hex_gig_rss.py) without pulling in
``services.budget_service`` → ``api.settings`` (which validates budget env vars
the job does not set). This module imports only the model and a DB session.
"""

from datetime import datetime, timedelta, timezone
from logging import getLogger

from db.models.usage_metrics import AgentUsageMetrics
from db.session import SessionLocal

logger = getLogger(__name__)


def purge_metrics_older_than(days: int) -> int:
    """Delete anonymous usage-metrics rows older than ``days`` days.

    Enforces a bounded retention period for the (already anonymous, content-free)
    ``agent_usage_metrics`` table. Daily aggregates in ``daily_agent_usage`` are
    left untouched.

    Returns the number of rows deleted (0 on any error — this never raises).

    Args:
        days: Retention window. Rows with ``created_at`` older than now-UTC minus
            this many days are deleted. Values <= 0 are treated as a no-op.
    """
    if days <= 0:
        logger.info("Metrics retention disabled (days=%s); skipping purge", days)
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        deleted = (
            db.query(AgentUsageMetrics).filter(AgentUsageMetrics.created_at < cutoff).delete(synchronize_session=False)
        )
        db.commit()
        logger.info("Purged %d usage-metrics rows older than %d days (cutoff=%s)", deleted, days, cutoff.isoformat())
        return deleted
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to purge old usage metrics: {e}")
        return 0
    finally:
        db.close()
