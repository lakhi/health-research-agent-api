"""Public-surface allow-list for the deployed AgentOS app.

AgentOS mounts a large admin/data surface alongside our public chat route — /sessions
(read/delete other users' conversations), /knowledge mutations, /metrics, /traces,
/eval-runs, /databases, /memories, /learnings, /queue, /service-accounts, schedules and
approvals. Authentication stays disabled unless OS_SECURITY_KEY (or a JWT config) is set,
and these deployments run with external ingress and no key, so the surface has to be closed
here. None of it is used by the public UI, which only calls GET /agents and POST
/agents/{id}/runs (plus /health for its connection check).

This replaces an earlier control (issue #31) that filtered AgentOS's routes out of
``app.router.routes`` after ``get_app()``. That worked only while FastAPI flattened
``include_router`` into concrete routes carrying a ``.path``. FastAPI 0.141 made inclusion
lazy: the parent list now holds opaque ``_IncludedRouter`` wrappers with no ``.path``, so
``getattr(route, "path", "")`` returned "", nothing matched the prefix list, and the filter
silently kept every admin route while still appearing to run. Matching on the request
instead of on FastAPI's route storage removes that whole class of failure — ``scope`` carries
the method and path directly, and no reorganisation upstream can take them away.

It is also an allow-list rather than a deny-list. The prefix list it replaces had already
fallen behind: Agno v3 added /learnings, /queue and /service-accounts, none of which it
named. Enumerating what is public means a route Agno adds in some future release is refused
by default, and the failure mode is a visibly broken feature rather than a silent exposure.

tests/api/test_public_surface.py asserts both halves of this, so the next dependency bump
that changes routing internals fails CI instead of production.
"""

import re
from typing import Final

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# (allowed methods, path pattern). Anything not matched here is refused.
#
# Patterns are anchored and matched against scope["path"], which excludes the query string.
# The optional trailing slash mirrors Starlette's own redirect_slashes behaviour, so
# /agents/ reaches the same handler /agents does rather than being refused before routing.
_PUBLIC_ROUTES: Final[tuple[tuple[frozenset[str], re.Pattern[str]], ...]] = (
    # Liveness check — used by the UI's connection indicator and by Azure's probes.
    (frozenset({"GET"}), re.compile(r"^/health/?$")),
    # Agent list — the UI reads this to populate its agent selector.
    (frozenset({"GET"}), re.compile(r"^/agents/?$")),
    # The chat route itself (ours, in api/routes/agents.py — it overrides AgentOS's own
    # via on_route_conflict="preserve_base_app" so budget enforcement is not bypassed).
    (frozenset({"POST"}), re.compile(r"^/agents/[^/]+/runs/?$")),
    # API documentation. Not used by the UI; kept public because it always has been.
    # Safe to drop these two entries if the schema should stop being advertised.
    (frozenset({"GET", "HEAD"}), re.compile(r"^/(?:docs|redoc|openapi\.json)/?$")),
    (frozenset({"GET"}), re.compile(r"^/docs/oauth2-redirect/?$")),
)


def is_public(method: str, path: str) -> bool:
    """True when *method* + *path* is part of the intended public surface.

    CORS preflight is always allowed through so CORSMiddleware can answer it. Refusing
    OPTIONS here would fail the preflight for the chat route and the browser would then
    block every chat request, even though the POST itself is public.
    """
    if method == "OPTIONS":
        return True
    return any(method in methods and pattern.match(path) for methods, pattern in _PUBLIC_ROUTES)


class PublicSurfaceOnly:
    """ASGI middleware refusing anything outside the public surface with a 404.

    Deliberately raw ASGI rather than ``@app.middleware("http")``: the decorator form is
    BaseHTTPMiddleware, which pumps the response through a memory stream and would buffer
    the SSE frames that chat_response_streamer yields. This class either delegates to the
    wrapped app untouched or never calls it at all, so streaming is unaffected.

    404 rather than 403: a blocked route should be indistinguishable from one that does not
    exist, which is also what the previous route-deletion approach produced.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope_type = scope.get("type")

        if scope_type == "http":
            if not is_public(scope.get("method", ""), scope.get("path", "")):
                await JSONResponse({"detail": "Not Found"}, status_code=404)(scope, receive, send)
                return

        elif scope_type == "websocket":
            # AgentOS serves /workflows/ws. Nothing public is a websocket, so refuse the
            # upgrade outright instead of letting an unlisted scope type through.
            await send({"type": "websocket.close", "code": 1008})
            return

        # "lifespan" and anything else falls through untouched.
        await self.app(scope, receive, send)
