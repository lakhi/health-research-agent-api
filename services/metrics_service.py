"""
Metrics service for recording anonymous agent usage metrics.

Records per-request operational data (tokens, latency, cost, status) without
any message content or user identity. Designed for aggregate reporting.
"""

from logging import getLogger
from typing import Optional

from db.models.usage_metrics import AgentUsageMetrics
from db.session import SessionLocal
from services.budget_service import calculate_cost_eur, get_today_vienna

logger = getLogger(__name__)


def record_agent_metrics(
    *,
    session_id: Optional[str] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    duration_seconds: Optional[float] = None,
    time_to_first_token: Optional[float] = None,
    cost_eur: Optional[float] = None,
    response_status: str = "success",
) -> None:
    """
    Record anonymous usage metrics for a single agent request.

    This function never raises — metrics recording failures are logged
    but never propagated to the caller, so they cannot break user responses.

    Args:
        session_id: Anonymous client-generated UUID (not linked to any identity)
        input_tokens: Number of input tokens consumed
        output_tokens: Number of output tokens consumed
        total_tokens: Combined input + output tokens
        duration_seconds: Total run duration in seconds
        time_to_first_token: Latency until first token generated
        cost_eur: Pre-calculated cost in EUR (if None, calculated from tokens)
        response_status: One of: "success", "error", "budget_exceeded"
    """
    try:
        today = get_today_vienna()

        if cost_eur is None:
            cost_eur = calculate_cost_eur(input_tokens, output_tokens)

        if total_tokens == 0 and (input_tokens > 0 or output_tokens > 0):
            total_tokens = input_tokens + output_tokens

        metrics = AgentUsageMetrics(
            date=today,
            anonymous_session_id=session_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_seconds=duration_seconds,
            time_to_first_token=time_to_first_token,
            cost_eur=cost_eur,
            response_status=response_status,
        )

        db = SessionLocal()
        try:
            db.add(metrics)
            db.commit()
            logger.info(
                f"Recorded metrics: tokens={total_tokens}, "
                f"duration={duration_seconds}s, cost={cost_eur:.6f}€, "
                f"status={response_status}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to persist usage metrics: {e}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to record usage metrics: {e}")
