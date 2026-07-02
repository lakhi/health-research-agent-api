"""
Unit tests for user_id threading and error-status capture in agent runs.

Calls chat_response_streamer / create_agent_run directly (no TestClient),
so no app startup or database is required.
Run with: pytest tests/api/test_agent_run_metrics.py -v
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.routes.agents import RunRequest, chat_response_streamer, create_agent_run
from api.settings import api_settings


def make_chunk(content="hello", metrics=None):
    return SimpleNamespace(content=content, metrics=metrics, references=None)


def make_streaming_agent(chunks, error=None):
    """Agent whose arun returns an async generator yielding chunks, optionally raising at the end."""
    agent = MagicMock()

    async def arun(message, stream=True, stream_events=True, session_id=None):
        for chunk in chunks:
            yield chunk
        if error is not None:
            raise error

    agent.arun = arun
    return agent


class TestStreamingMetrics:
    """chat_response_streamer should thread user_id and record failures."""

    async def test_success_passes_user_id_to_metrics(self):
        metrics = SimpleNamespace(
            input_tokens=10, output_tokens=5, total_tokens=15, duration=1.2, time_to_first_token=0.3
        )
        agent = make_streaming_agent([make_chunk(metrics=metrics)])

        with (
            patch("api.routes.agents.record_agent_metrics") as mock_record,
            patch("api.routes.agents.record_usage"),
        ):
            async for _ in chat_response_streamer(agent, "msg", has_budget=True, session_id="sess-1", user_id="user-1"):
                pass

        mock_record.assert_called_once()
        kwargs = mock_record.call_args.kwargs
        assert kwargs["user_id"] == "user-1"
        assert kwargs["session_id"] == "sess-1"
        assert kwargs.get("response_status", "success") == "success"

    async def test_stream_failure_records_error_and_reraises(self):
        agent = make_streaming_agent([make_chunk()], error=RuntimeError("model exploded"))

        with (
            patch("api.routes.agents.record_agent_metrics") as mock_record,
            patch("api.routes.agents.record_usage"),
        ):
            with pytest.raises(RuntimeError, match="model exploded"):
                async for _ in chat_response_streamer(
                    agent, "msg", has_budget=True, session_id="sess-1", user_id="user-1"
                ):
                    pass

        mock_record.assert_called_once()
        kwargs = mock_record.call_args.kwargs
        assert kwargs["response_status"] == "error"
        assert kwargs["session_id"] == "sess-1"
        assert kwargs["user_id"] == "user-1"
        assert kwargs["duration_seconds"] is not None

    async def test_stream_failure_without_budget_records_nothing(self):
        """Metrics recording stays gated on has_budget, also on the error path."""
        agent = make_streaming_agent([make_chunk()], error=RuntimeError("boom"))

        with patch("api.routes.agents.record_agent_metrics") as mock_record:
            with pytest.raises(RuntimeError):
                async for _ in chat_response_streamer(agent, "msg", has_budget=False):
                    pass

        mock_record.assert_not_called()


class TestNonStreamingMetrics:
    """create_agent_run (stream=False) should thread user_id and record failures."""

    async def test_run_failure_records_error_and_reraises(self, monkeypatch):
        monkeypatch.setattr(api_settings, "daily_budget_eur", 2.0)
        reset_time = datetime.now(timezone.utc) + timedelta(hours=5)

        agent = MagicMock()
        agent.arun = AsyncMock(side_effect=RuntimeError("azure timeout"))

        with (
            patch("api.routes.agents.check_budget_available", return_value=(True, 1.5, reset_time)),
            patch("api.routes.agents.get_agent", return_value=agent),
            patch("api.routes.agents.record_agent_metrics") as mock_record,
        ):
            request = RunRequest(message="hi", stream=False, session_id="sess-2", user_id="user-2")
            with pytest.raises(RuntimeError, match="azure timeout"):
                await create_agent_run(agent_id="hex", body=request)

        mock_record.assert_called_once()
        kwargs = mock_record.call_args.kwargs
        assert kwargs["response_status"] == "error"
        assert kwargs["session_id"] == "sess-2"
        assert kwargs["user_id"] == "user-2"

    async def test_budget_exceeded_records_user_id(self, monkeypatch):
        monkeypatch.setattr(api_settings, "daily_budget_eur", 2.0)
        reset_time = datetime.now(timezone.utc) + timedelta(hours=5)

        with (
            patch("api.routes.agents.check_budget_available", return_value=(False, 0.0, reset_time)),
            patch("api.routes.agents.record_agent_metrics") as mock_record,
        ):
            request = RunRequest(message="hi", stream=False, session_id="sess-3", user_id="user-3")
            response = await create_agent_run(agent_id="hex", body=request)

        assert response.status_code == 429
        kwargs = mock_record.call_args.kwargs
        assert kwargs["response_status"] == "budget_exceeded"
        assert kwargs["user_id"] == "user-3"
