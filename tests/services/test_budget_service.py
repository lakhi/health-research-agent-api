"""
Unit and integration tests for the budget service.

Tests follow TDD approach - written before implementation.
Run with: pytest tests/services/test_budget_service.py -v
"""

from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

import pytest

# These imports will fail until implementation is complete
from services.budget_service import (
    BUDGET_TIMEZONE,
    calculate_cost_eur,
    get_daily_spend_eur,
    check_budget_available,
    record_usage,
    get_today_vienna,
    get_next_reset_time_utc,
)
from api.settings import api_settings


class TestCalculateCostEur:
    """Unit tests for EUR cost calculation."""

    def test_calculate_cost_input_only(self):
        """1M input tokens should cost €1.87 (default GPT-4.1 Data Zone rate)."""
        cost = calculate_cost_eur(input_tokens=1_000_000, output_tokens=0)
        assert cost == pytest.approx(1.87, rel=0.01)

    def test_calculate_cost_output_only(self):
        """1M output tokens should cost €7.48 (default GPT-4.1 Data Zone rate)."""
        cost = calculate_cost_eur(input_tokens=0, output_tokens=1_000_000)
        assert cost == pytest.approx(7.48, rel=0.01)

    def test_calculate_cost_mixed_tokens(self):
        """500K input + 500K output should cost (0.5 * 1.87) + (0.5 * 7.48) = €4.675."""
        cost = calculate_cost_eur(input_tokens=500_000, output_tokens=500_000)
        expected = (0.5 * 1.87) + (0.5 * 7.48)
        assert cost == pytest.approx(expected, rel=0.01)

    def test_calculate_cost_zero_tokens(self):
        """Zero tokens should cost €0."""
        cost = calculate_cost_eur(input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_calculate_cost_small_tokens(self):
        """1000 tokens should cost proportionally less."""
        cost = calculate_cost_eur(input_tokens=1000, output_tokens=1000)
        expected = (1000 / 1_000_000 * 1.87) + (1000 / 1_000_000 * 7.48)
        assert cost == pytest.approx(expected, rel=0.01)


class TestBudgetAvailability:
    """Unit tests for budget availability checks."""

    @patch("services.budget_service.get_daily_spend_eur")
    def test_check_budget_available_under_limit(self, mock_spend):
        """Budget should be available when spend is under limit."""
        mock_spend.return_value = 1.0  # €1 spent

        available, remaining, reset_time = check_budget_available()

        assert available is True
        assert remaining == pytest.approx(api_settings.daily_budget_eur - 1.0, rel=0.01)
        assert isinstance(reset_time, datetime)

    @patch("services.budget_service.get_daily_spend_eur")
    def test_check_budget_available_exceeded(self, mock_spend):
        """Budget should not be available when spend exceeds limit."""
        mock_spend.return_value = 3.0  # €3 spent, default budget is €2

        available, remaining, reset_time = check_budget_available()

        assert available is False
        assert remaining <= 0
        assert isinstance(reset_time, datetime)

    @patch("services.budget_service.get_daily_spend_eur")
    def test_check_budget_available_at_exact_limit(self, mock_spend):
        """Budget should not be available when spend equals limit."""
        mock_spend.return_value = api_settings.daily_budget_eur

        available, remaining, reset_time = check_budget_available()

        assert available is False
        assert remaining == 0


class TestTimezoneHandling:
    """Tests for Vienna timezone handling."""

    def test_budget_timezone_is_vienna(self):
        """Budget timezone should be Europe/Vienna."""
        assert BUDGET_TIMEZONE == "Europe/Vienna"

    def test_get_today_vienna_returns_date(self):
        """get_today_vienna should return a date object."""
        today = get_today_vienna()
        assert isinstance(today, date)

    def test_get_next_reset_time_is_utc(self):
        """Reset time should be in UTC."""
        reset_time = get_next_reset_time_utc()
        assert reset_time.tzinfo is not None
        # Should be midnight Vienna time converted to UTC

    def test_reset_time_is_midnight_vienna(self):
        """Reset time should correspond to midnight Vienna time."""
        reset_time = get_next_reset_time_utc()
        vienna_tz = ZoneInfo("Europe/Vienna")

        # Convert reset time to Vienna timezone
        reset_vienna = reset_time.astimezone(vienna_tz)

        # Should be midnight (00:00)
        assert reset_vienna.hour == 0
        assert reset_vienna.minute == 0


class TestDatabaseIntegration:
    """Integration tests for database persistence.

    These tests require a test database connection.
    Run with: pytest tests/services/test_budget_service.py -v -m integration
    """

    @pytest.fixture
    def clean_db(self):
        """Fixture to clean up test data before and after tests."""
        # Setup: clean any existing test data
        from db.session import SessionLocal
        from db.models.budget import DailyHealthsocChatbotUsage

        db = SessionLocal()
        try:
            # Delete today's test entries
            today = get_today_vienna()
            db.query(DailyHealthsocChatbotUsage).filter(
                DailyHealthsocChatbotUsage.date == today
            ).delete()
            db.commit()
            yield db
        finally:
            # Cleanup after test
            db.query(DailyHealthsocChatbotUsage).filter(
                DailyHealthsocChatbotUsage.date == today
            ).delete()
            db.commit()
            db.close()

    @pytest.mark.integration
    def test_record_usage_creates_new_entry(self, clean_db):
        """Recording usage should create a new database entry."""
        record_usage(input_tokens=1000, output_tokens=500)

        spend = get_daily_spend_eur()
        expected_cost = calculate_cost_eur(1000, 500)

        assert spend == pytest.approx(expected_cost, rel=0.01)

    @pytest.mark.integration
    def test_record_usage_accumulates_same_day(self, clean_db):
        """Multiple usages on the same day should accumulate."""
        record_usage(input_tokens=1000, output_tokens=500)
        record_usage(input_tokens=2000, output_tokens=1000)

        spend = get_daily_spend_eur()
        expected_cost = calculate_cost_eur(3000, 1500)

        assert spend == pytest.approx(expected_cost, rel=0.01)

    @pytest.mark.integration
    def test_daily_reset_at_midnight_vienna(self, clean_db):
        """Usage from yesterday should not count towards today's spend."""
        from db.models.budget import DailyHealthsocChatbotUsage

        # Insert yesterday's usage directly
        yesterday = get_today_vienna() - timedelta(days=1)
        yesterday_usage = DailyHealthsocChatbotUsage(
            date=yesterday,
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cost_eur=9.35,  # High cost
        )
        clean_db.add(yesterday_usage)
        clean_db.commit()

        # Today's spend should be 0
        spend = get_daily_spend_eur()
        assert spend == 0.0
