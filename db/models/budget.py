"""
Database model for tracking daily healthsoc chatbot usage.

This model stores daily token usage and costs for budget enforcement.
"""

from datetime import date, datetime

from sqlalchemy import Column, Integer, Float, Date, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class DailyHealthsocChatbotUsage(Base):
    """
    Tracks daily token usage and costs for the healthsoc chatbot.

    Each row represents one usage event (API call) on a specific date.
    The budget service aggregates all rows for a given date to calculate
    total daily spend.

    Attributes:
        id: Primary key
        date: The date of usage (Vienna timezone)
        input_tokens: Number of input tokens consumed
        output_tokens: Number of output tokens consumed
        cost_eur: Calculated cost in EUR for this usage
        created_at: Timestamp when the record was created
    """

    __tablename__ = "daily_healthsoc_chatbot_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost_eur = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Composite index for efficient daily queries
    __table_args__ = (Index("ix_daily_healthsoc_usage_date", "date"),)

    def __repr__(self):
        return (
            f"<DailyHealthsocChatbotUsage("
            f"date={self.date}, "
            f"input_tokens={self.input_tokens}, "
            f"output_tokens={self.output_tokens}, "
            f"cost_eur={self.cost_eur}"
            f")>"
        )
