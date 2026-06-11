"""
Unit tests for the metrics retention purge.

Run with: pytest tests/services/test_metrics_retention.py -v
"""

from unittest.mock import MagicMock, patch

from services.metrics_retention import purge_metrics_older_than


class TestPurgeMetricsOlderThan:
    """Unit tests for purge_metrics_older_than."""

    @patch("services.metrics_retention.SessionLocal")
    def test_deletes_old_rows_and_returns_count(self, mock_session_local):
        """Rows older than the cutoff are deleted; the deleted count is returned."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.delete.return_value = 7
        mock_session_local.return_value = mock_db

        deleted = purge_metrics_older_than(180)

        assert deleted == 7
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    @patch("services.metrics_retention.SessionLocal")
    def test_non_positive_days_is_noop(self, mock_session_local):
        """days <= 0 disables retention: no DB session is opened, returns 0."""
        assert purge_metrics_older_than(0) == 0
        assert purge_metrics_older_than(-5) == 0
        mock_session_local.assert_not_called()

    @patch("services.metrics_retention.SessionLocal")
    def test_delete_failure_returns_zero_and_rolls_back(self, mock_session_local):
        """A DB failure is swallowed: rollback + close run, returns 0, never raises."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.delete.side_effect = Exception("DB gone")
        mock_session_local.return_value = mock_db

        assert purge_metrics_older_than(30) == 0
        mock_db.rollback.assert_called_once()
        mock_db.close.assert_called_once()
