"""
Database model for tracking anonymous agent usage metrics.

This model stores per-request operational metrics (tokens, latency, cost, status)
without any message content or user identity, enabling aggregate reporting while
preserving user privacy.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, Index, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class AgentUsageMetrics(Base):
    """
    Tracks anonymous per-request usage metrics for a deployed agent.

    Each row represents one agent run. The anonymous_session_id (a random UUID
    from the frontend) enables session counting and duration estimation without
    identifying any user.

    Attributes:
        id: Primary key
        date: The date of the request (Vienna timezone)
        anonymous_session_id: Client-generated UUID, not linked to any identity
        input_tokens: Number of input tokens consumed
        output_tokens: Number of output tokens consumed
        total_tokens: Combined input + output tokens
        duration_seconds: Total run duration in seconds
        time_to_first_token: Latency until first token generated (streaming)
        cost_eur: Calculated cost in EUR for this request
        response_status: One of: success, error, budget_exceeded
        created_at: Timestamp when the record was created (UTC)
    """

    __tablename__ = "agent_usage_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    anonymous_session_id = Column(String(64), nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    duration_seconds = Column(Float, nullable=True)
    time_to_first_token = Column(Float, nullable=True)
    cost_eur = Column(Float, nullable=False, default=0.0)
    response_status = Column(String(32), nullable=False, default="success")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_agent_usage_metrics_date", "date"),
        Index("ix_agent_usage_metrics_session", "anonymous_session_id"),
    )

    def __repr__(self):
        return (
            f"<AgentUsageMetrics("
            f"date={self.date}, "
            f"session={self.anonymous_session_id}, "
            f"tokens={self.total_tokens}, "
            f"duration={self.duration_seconds}s, "
            f"cost={self.cost_eur}€, "
            f"status={self.response_status}"
            f")>"
        )
