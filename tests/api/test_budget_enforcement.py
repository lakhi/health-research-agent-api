"""
API tests for budget enforcement in agent routes.

Tests follow TDD approach - written before implementation.
Run with: pytest tests/api/test_budget_enforcement.py -v
"""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from api.main import app
from agents.selector import AgentType


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


class TestBudgetEnforcementHeader:
    """Tests for X-Budget-Remaining-EUR header in successful responses."""

    @patch("api.routes.agents.check_budget_available")
    @patch("api.routes.agents.record_usage")
    @patch("api.routes.agents.get_agent")
    def test_successful_response_has_remaining_eur_header(
        self, mock_get_agent, mock_record, mock_check, client
    ):
        """Successful response should include X-Budget-Remaining-EUR header."""
        # Setup mocks
        mock_check.return_value = (True, 1.50, datetime.now(ZoneInfo("UTC")))
        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(
            return_value=MagicMock(
                content="Test response",
                metrics=MagicMock(input_tokens=100, output_tokens=50),
            )
        )
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/v1/agents/hrn_agent/runs", json={"message": "Hello", "stream": False}
        )

        assert response.status_code == 200
        assert "X-Budget-Remaining-EUR" in response.headers
        assert float(response.headers["X-Budget-Remaining-EUR"]) == pytest.approx(
            1.50, rel=0.01
        )

    @patch("api.routes.agents.check_budget_available")
    @patch("api.routes.agents.get_agent")
    def test_non_healthsoc_agent_has_no_budget_header(
        self, mock_get_agent, mock_check, client
    ):
        """Non-healthsoc agents should not have budget headers."""
        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(return_value=MagicMock(content="Test response"))
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/v1/agents/control_agent/runs", json={"message": "Hello", "stream": False}
        )

        # Should succeed but without budget header
        assert response.status_code == 200
        assert "X-Budget-Remaining-EUR" not in response.headers
        # check_budget_available should not be called for non-healthsoc agents
        mock_check.assert_not_called()


class TestBudgetExceeded429:
    """Tests for 429 response when budget is exceeded."""

    @patch("api.routes.agents.check_budget_available")
    def test_429_when_budget_exceeded(self, mock_check, client):
        """Should return 429 when daily budget is exceeded."""
        reset_time = datetime.now(ZoneInfo("UTC")) + timedelta(hours=5)
        mock_check.return_value = (False, 0.0, reset_time)

        response = client.post(
            "/v1/agents/hrn_agent/runs", json={"message": "Hello", "stream": False}
        )

        assert response.status_code == 429

    @patch("api.routes.agents.check_budget_available")
    def test_429_body_includes_error_type(self, mock_check, client):
        """429 response body should include error type."""
        reset_time = datetime.now(ZoneInfo("UTC")) + timedelta(hours=5)
        mock_check.return_value = (False, 0.0, reset_time)

        response = client.post(
            "/v1/agents/hrn_agent/runs", json={"message": "Hello", "stream": False}
        )

        body = response.json()
        assert body["error"] == "daily_budget_exceeded"

    @patch("api.routes.agents.check_budget_available")
    def test_429_body_includes_reset_time_utc(self, mock_check, client):
        """429 response body should include reset_time_utc in ISO format."""
        reset_time = datetime(2026, 1, 30, 23, 0, 0, tzinfo=ZoneInfo("UTC"))
        mock_check.return_value = (False, 0.0, reset_time)

        response = client.post(
            "/v1/agents/hrn_agent/runs", json={"message": "Hello", "stream": False}
        )

        body = response.json()
        assert "reset_time_utc" in body
        assert body["reset_time_utc"] == "2026-01-30T23:00:00+00:00"

    @patch("api.routes.agents.check_budget_available")
    def test_429_body_includes_remaining_eur(self, mock_check, client):
        """429 response body should include remaining_eur (0.0 when exceeded)."""
        reset_time = datetime.now(ZoneInfo("UTC")) + timedelta(hours=5)
        mock_check.return_value = (False, 0.0, reset_time)

        response = client.post(
            "/v1/agents/hrn_agent/runs", json={"message": "Hello", "stream": False}
        )

        body = response.json()
        assert "remaining_eur" in body
        assert body["remaining_eur"] == 0.0


class TestBudgetOnlyAppliesToHealthsoc:
    """Tests ensuring budget enforcement only applies to healthsoc agent."""

    @patch("api.routes.agents.check_budget_available")
    @patch("api.routes.agents.get_agent")
    def test_budget_only_applies_to_healthsoc_agent(
        self, mock_get_agent, mock_check, client
    ):
        """Budget check should only apply to hrn_agent (healthsoc)."""
        # Mock agent to avoid actual LLM calls
        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(return_value=MagicMock(content="Test response"))
        mock_get_agent.return_value = mock_agent

        # Call a non-healthsoc agent
        response = client.post(
            "/v1/agents/control_agent/runs", json={"message": "Hello", "stream": False}
        )

        # check_budget_available should not be called
        mock_check.assert_not_called()
        assert response.status_code == 200

    @patch("api.routes.agents.check_budget_available")
    @patch("api.routes.agents.get_agent")
    def test_healthsoc_agent_checks_budget(self, mock_get_agent, mock_check, client):
        """hrn_agent should always check budget availability."""
        reset_time = datetime.now(ZoneInfo("UTC")) + timedelta(hours=5)
        mock_check.return_value = (True, 1.50, reset_time)

        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(
            return_value=MagicMock(
                content="Test response",
                metrics=MagicMock(input_tokens=100, output_tokens=50),
            )
        )
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/v1/agents/hrn_agent/runs", json={"message": "Hello", "stream": False}
        )

        mock_check.assert_called_once()


class TestMetricsCapture:
    """Tests for capturing and recording usage metrics."""

    @patch("api.routes.agents.check_budget_available")
    @patch("api.routes.agents.record_usage")
    @patch("api.routes.agents.get_agent")
    def test_agent_run_captures_and_records_metrics(
        self, mock_get_agent, mock_record, mock_check, client
    ):
        """After successful run, metrics should be recorded."""
        reset_time = datetime.now(ZoneInfo("UTC")) + timedelta(hours=5)
        mock_check.return_value = (True, 1.50, reset_time)

        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(
            return_value=MagicMock(
                content="Test response",
                metrics=MagicMock(input_tokens=1500, output_tokens=800),
            )
        )
        mock_get_agent.return_value = mock_agent

        response = client.post(
            "/v1/agents/hrn_agent/runs", json={"message": "Hello", "stream": False}
        )

        assert response.status_code == 200
        mock_record.assert_called_once_with(input_tokens=1500, output_tokens=800)
