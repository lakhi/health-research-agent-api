"""
Unit tests for the metrics service.

Tests that record_agent_metrics correctly constructs records and never raises.
Run with: pytest tests/services/test_metrics_service.py -v
"""

from unittest.mock import MagicMock, patch

import pytest

from services.metrics_service import record_agent_metrics


class TestRecordAgentMetrics:
    """Unit tests for record_agent_metrics."""

    @patch("services.metrics_service.SessionLocal")
    @patch("services.metrics_service.get_today_vienna")
    def test_records_successful_request(self, mock_today, mock_session_local):
        """A successful request should persist a row with all metrics fields."""
        from datetime import date

        mock_today.return_value = date(2026, 3, 28)
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        record_agent_metrics(
            session_id="test-session-uuid",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            duration_seconds=2.5,
            time_to_first_token=0.3,
            response_status="success",
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

        added_record = mock_db.add.call_args[0][0]
        assert added_record.date == date(2026, 3, 28)
        assert added_record.anonymous_session_id == "test-session-uuid"
        assert added_record.input_tokens == 1000
        assert added_record.output_tokens == 500
        assert added_record.total_tokens == 1500
        assert added_record.duration_seconds == 2.5
        assert added_record.time_to_first_token == 0.3
        assert added_record.response_status == "success"

    @patch("services.metrics_service.SessionLocal")
    @patch("services.metrics_service.get_today_vienna")
    def test_calculates_total_tokens_when_zero(self, mock_today, mock_session_local):
        """total_tokens should be auto-calculated from input + output when not provided."""
        from datetime import date

        mock_today.return_value = date(2026, 3, 28)
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        record_agent_metrics(
            input_tokens=800,
            output_tokens=200,
            total_tokens=0,
        )

        added_record = mock_db.add.call_args[0][0]
        assert added_record.total_tokens == 1000

    @patch("services.metrics_service.SessionLocal")
    @patch("services.metrics_service.get_today_vienna")
    def test_calculates_cost_when_not_provided(self, mock_today, mock_session_local):
        """cost_eur should be auto-calculated from tokens when not provided."""
        from datetime import date

        mock_today.return_value = date(2026, 3, 28)
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        record_agent_metrics(
            input_tokens=1_000_000,
            output_tokens=0,
        )

        added_record = mock_db.add.call_args[0][0]
        assert added_record.cost_eur == pytest.approx(1.87, rel=0.01)

    @patch("services.metrics_service.SessionLocal")
    @patch("services.metrics_service.get_today_vienna")
    def test_uses_provided_cost_when_given(self, mock_today, mock_session_local):
        """cost_eur should use the provided value rather than calculating."""
        from datetime import date

        mock_today.return_value = date(2026, 3, 28)
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        record_agent_metrics(
            input_tokens=1000,
            output_tokens=500,
            cost_eur=0.42,
        )

        added_record = mock_db.add.call_args[0][0]
        assert added_record.cost_eur == 0.42

    @patch("services.metrics_service.SessionLocal")
    @patch("services.metrics_service.get_today_vienna")
    def test_records_budget_exceeded_status(self, mock_today, mock_session_local):
        """Budget-exceeded events should be recorded with zero tokens."""
        from datetime import date

        mock_today.return_value = date(2026, 3, 28)
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        record_agent_metrics(
            session_id="some-session",
            response_status="budget_exceeded",
        )

        added_record = mock_db.add.call_args[0][0]
        assert added_record.response_status == "budget_exceeded"
        assert added_record.input_tokens == 0
        assert added_record.output_tokens == 0

    @patch("services.metrics_service.SessionLocal")
    @patch("services.metrics_service.get_today_vienna")
    def test_handles_nullable_session_id(self, mock_today, mock_session_local):
        """Metrics should be recorded even without a session_id."""
        from datetime import date

        mock_today.return_value = date(2026, 3, 28)
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        record_agent_metrics(
            input_tokens=100,
            output_tokens=50,
        )

        added_record = mock_db.add.call_args[0][0]
        assert added_record.anonymous_session_id is None
        mock_db.commit.assert_called_once()


class TestMetricsNeverRaises:
    """Ensure metrics recording never propagates exceptions to the caller."""

    @patch("services.metrics_service.SessionLocal")
    @patch("services.metrics_service.get_today_vienna")
    def test_db_commit_failure_does_not_raise(self, mock_today, mock_session_local):
        """Database commit failures should be logged, not raised."""
        from datetime import date

        mock_today.return_value = date(2026, 3, 28)
        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("DB connection lost")
        mock_session_local.return_value = mock_db

        # Should not raise
        record_agent_metrics(input_tokens=100, output_tokens=50)

        mock_db.rollback.assert_called_once()
        mock_db.close.assert_called_once()

    @patch("services.metrics_service.get_today_vienna")
    def test_complete_failure_does_not_raise(self, mock_today):
        """Even total infrastructure failure should not raise."""
        mock_today.side_effect = Exception("Timezone database corrupted")

        # Should not raise
        record_agent_metrics(input_tokens=100, output_tokens=50)
