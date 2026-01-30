"""
Budget service for tracking and enforcing daily usage limits for healthsoc chatbot.

This service tracks token usage and costs, enforcing a configurable daily budget
in EUR. The budget resets at midnight Vienna time (Europe/Vienna timezone).
"""

from datetime import date, datetime, timedelta
from logging import getLogger
from typing import Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import func

from api.settings import api_settings, BUDGET_TIMEZONE
from db.session import SessionLocal
from db.models.budget import DailyHealthsocChatbotUsage

logger = getLogger(__name__)


def calculate_cost_eur(input_tokens: int, output_tokens: int) -> float:
    """
    Calculate the cost in EUR for a given number of input and output tokens.

    Uses the GPT-4.1 Data Zone pricing configured in settings:
    - Input: €1.87 per 1M tokens (default)
    - Output: €7.48 per 1M tokens (default)

    Args:
        input_tokens: Number of input tokens consumed
        output_tokens: Number of output tokens consumed

    Returns:
        Cost in EUR
    """
    input_cost = (input_tokens / 1_000_000) * api_settings.model_pricing_input_eur
    output_cost = (output_tokens / 1_000_000) * api_settings.model_pricing_output_eur
    return input_cost + output_cost


def get_today_vienna() -> date:
    """
    Get the current date in Vienna timezone.

    Returns:
        Current date in Europe/Vienna timezone
    """
    vienna_tz = ZoneInfo(BUDGET_TIMEZONE)
    return datetime.now(vienna_tz).date()


def get_next_reset_time_utc() -> datetime:
    """
    Get the next budget reset time (midnight Vienna) in UTC.

    The budget resets at midnight Vienna time. This function returns
    the next midnight in Vienna timezone, converted to UTC.

    Returns:
        Next reset time as UTC datetime
    """
    vienna_tz = ZoneInfo(BUDGET_TIMEZONE)
    utc_tz = ZoneInfo("UTC")

    # Get current time in Vienna
    now_vienna = datetime.now(vienna_tz)

    # Next midnight in Vienna
    tomorrow_vienna = now_vienna.date() + timedelta(days=1)
    midnight_vienna = datetime(
        tomorrow_vienna.year,
        tomorrow_vienna.month,
        tomorrow_vienna.day,
        0,
        0,
        0,
        tzinfo=vienna_tz,
    )

    # Convert to UTC
    return midnight_vienna.astimezone(utc_tz)


def get_daily_spend_eur() -> float:
    """
    Get the total spend in EUR for today (Vienna timezone).

    Sums all cost_eur values from the database for today's date
    in Vienna timezone.

    Returns:
        Total spend in EUR for today
    """
    today = get_today_vienna()

    db = SessionLocal()
    try:
        result = (
            db.query(func.coalesce(func.sum(DailyHealthsocChatbotUsage.cost_eur), 0.0))
            .filter(DailyHealthsocChatbotUsage.date == today)
            .scalar()
        )

        return float(result)
    finally:
        db.close()


def check_budget_available() -> Tuple[bool, float, datetime]:
    """
    Check if budget is available for the healthsoc chatbot.

    Returns:
        Tuple of:
        - available (bool): True if budget is available
        - remaining_eur (float): Remaining budget in EUR (0 if exceeded)
        - reset_time_utc (datetime): When the budget resets (midnight Vienna in UTC)
    """
    daily_budget = api_settings.daily_budget_eur
    current_spend = get_daily_spend_eur()
    remaining = max(0.0, daily_budget - current_spend)
    reset_time = get_next_reset_time_utc()

    available = current_spend < daily_budget

    logger.debug(
        f"Budget check: spend={current_spend:.4f} EUR, "
        f"budget={daily_budget:.2f} EUR, "
        f"remaining={remaining:.4f} EUR, "
        f"available={available}"
    )

    return available, remaining, reset_time


def record_usage(input_tokens: int, output_tokens: int) -> None:
    """
    Record token usage for the healthsoc chatbot.

    Creates a new record in the database with the token counts
    and calculated cost.

    Args:
        input_tokens: Number of input tokens consumed
        output_tokens: Number of output tokens consumed
    """
    today = get_today_vienna()
    cost = calculate_cost_eur(input_tokens, output_tokens)

    db = SessionLocal()
    try:
        usage = DailyHealthsocChatbotUsage(
            date=today,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_eur=cost,
        )
        db.add(usage)
        db.commit()

        logger.info(
            f"Recorded usage: input={input_tokens}, output={output_tokens}, "
            f"cost={cost:.6f} EUR"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to record usage: {e}")
        raise
    finally:
        db.close()
