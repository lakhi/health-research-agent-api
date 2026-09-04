"""
Regression tests for the public-surface allow-list (api/security.py).

These exist because the control they replace failed silently. The previous approach
filtered AgentOS's admin routes out of app.router.routes after get_app(); FastAPI 0.141
made include_router lazy, the filter stopped matching anything, and the entire admin
surface became publicly reachable without raising or logging (issue #46).

The trigger was a transitive dependency bump, not an edit to api/main.py, so the only
thing that can catch a recurrence is a test that issues real requests against a real
AgentOS app. That is what TestPublicSurfaceAgainstAgentOS does.

Run with: pytest tests/api/test_public_surface.py -v
"""

import pytest
from agno.agent import Agent
from agno.db.in_memory import InMemoryDb
from agno.os import AgentOS
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from api.security import PublicSurfaceOnly, is_public

# Every top-level prefix AgentOS v3 serves that must never be publicly reachable.
# /learnings, /queue and /service-accounts are v3 additions the old deny-list never named —
# the reason this is an allow-list.
ADMIN_PATHS = [
    "/sessions",
    "/memories",
    "/memory_topics",
    "/user_memory_stats",
    "/optimize-memories",
    "/learnings",
    "/queue",
    "/service-accounts",
    "/knowledge/content",
    "/metrics",
    "/traces",
    "/trace_session_stats",
    "/eval-runs",
    "/databases",
    "/components",
    "/schedules",
    "/approvals",
    "/registry",
    "/teams",
    "/workflows",
    "/config",
    "/info",
    "/",
]

# Reachable under the old prefix filter because they live below /agents, but not part of
# the chat surface and never called by the UI.
NON_PUBLIC_AGENT_PATHS = [
    "/agents/hex/runs/run-1",
    "/agents/hex/runs/run-1/checkpoints",
    "/agents/hex/sessions/sess-1/fork",
    "/agents/hex/knowledge/load",
]

ORIGIN = "https://hex-gig.univie.ac.at"


@pytest.fixture(scope="module")
def client():
    """A TestClient over an app shaped exactly like api/main.py builds.

    Mirrors the real construction: our chat router on a base FastAPI app, AgentOS layered
    over it with preserve_base_app, then PublicSurfaceOnly and CORS in that order. Uses
    InMemoryDb so nothing touches Postgres.
    """
    chat_router = APIRouter(prefix="/agents", tags=["Agents"])

    @chat_router.post("/{agent_id}/runs")
    async def run(agent_id: str):
        async def gen():
            for i in range(3):
                yield f"event: message\ndata: chunk-{i}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    base_app = FastAPI(title="Health Research Agent API (test)")
    base_app.include_router(chat_router)

    agent_os = AgentOS(
        name="Research Studies OS (test)",
        agents=[Agent(id="hex", name="hex", db=InMemoryDb())],
        base_app=base_app,
        on_route_conflict="preserve_base_app",
        telemetry=False,
    )
    app = agent_os.get_app()
    app.add_middleware(PublicSurfaceOnly)
    app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_credentials=True, allow_methods=["*"])

    with TestClient(app) as test_client:
        yield test_client


class TestIsPublic:
    """The allow-list predicate itself."""

    @pytest.mark.parametrize("path", ["/health", "/agents", "/agents/"])
    def test_get_public_paths_allowed(self, path):
        assert is_public("GET", path)

    def test_chat_route_allowed(self):
        assert is_public("POST", "/agents/hex-gig-agent/runs")

    @pytest.mark.parametrize("path", ADMIN_PATHS + NON_PUBLIC_AGENT_PATHS)
    def test_admin_paths_refused(self, path):
        assert not is_public("GET", path)
        assert not is_public("POST", path)

    def test_method_is_part_of_the_match(self):
        """The chat route is POST-only; listing agents is GET-only."""
        assert not is_public("GET", "/agents/hex/runs")
        assert not is_public("DELETE", "/agents")

    def test_preflight_always_allowed(self):
        """OPTIONS must reach CORSMiddleware or the browser blocks every chat request."""
        assert is_public("OPTIONS", "/agents/hex/runs")
        assert is_public("OPTIONS", "/sessions")


class TestPublicSurfaceAgainstAgentOS:
    """End-to-end against a real AgentOS app — the test that catches a routing-internals change."""

    @pytest.mark.parametrize("path", ADMIN_PATHS + NON_PUBLIC_AGENT_PATHS)
    def test_admin_surface_is_not_reachable(self, client, path):
        assert client.get(path).status_code == 404, f"{path} is publicly reachable"

    @pytest.mark.parametrize("path", ["/health", "/agents"])
    def test_public_surface_is_reachable(self, client, path):
        assert client.get(path).status_code == 200

    def test_chat_route_streams_incrementally(self, client):
        """Guards the choice of raw ASGI over BaseHTTPMiddleware, which would buffer SSE."""
        with client.stream("POST", "/agents/hex/runs") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            lines = [line for line in response.iter_lines() if line]

        assert lines == [
            "event: message",
            "data: chunk-0",
            "event: message",
            "data: chunk-1",
            "event: message",
            "data: chunk-2",
        ]

    def test_cors_preflight_survives(self, client):
        """Regression guard on middleware ordering: CORS must sit outside the allow-list."""
        response = client.options(
            "/agents/hex/runs",
            headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST"},
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ORIGIN

    def test_blocked_response_still_carries_cors_headers(self, client):
        """So the browser reports a clean 404 rather than an opaque CORS failure."""
        response = client.get("/sessions", headers={"Origin": ORIGIN})
        assert response.status_code == 404
        assert response.headers["access-control-allow-origin"] == ORIGIN
