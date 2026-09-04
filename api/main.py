import logging
from contextlib import asynccontextmanager

from agno.agent import Agent
from agno.agent.factory import AgentFactory
from agno.agent.protocol import AgentProtocol
from agno.agent.remote import RemoteAgent
from agno.os import AgentOS

# TODO: feat(tracing) - Tracing can be enabled later if required
# from agno.tracing import configure_tracing
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.registry import register_agents
from api.routes.agents import agents_router
from api.security import PublicSurfaceOnly
from api.settings import api_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# Initialize agents based on active project configuration
agents = api_settings.project_config.get_agents()
register_agents(agents)
# `list` is invariant, so list[Agent] is not a list[Agent | RemoteAgent | AgentProtocol |
# AgentFactory]. A widened copy satisfies AgentOS without loosening anything at runtime.
os_agents: list[Agent | RemoteAgent | AgentProtocol | AgentFactory] = list(agents)

# Get unified database for AgentOS (will propagate to components without their own db).
# Deliberately imported here, not at the top: db.session resolves the DB URL from the
# environment at import time, so it has to run after api.settings has loaded it.
from db import get_project_db  # noqa: E402

agent_os_db = get_project_db(api_settings.project_config.project_name)

# TODO: feat(tracing) - Tracing can be enabled later if required
# Configure Native OpenTelemetry Tracing
# configure_tracing(
#     service_name=f"hex-gig-agent-api-{api_settings.project_config.project_name}",
#     db=agent_os_db,
# )


@asynccontextmanager
async def app_lifecycle(app):
    """
    Lifespan context manager to handle startup and shutdown events.
    Loads knowledge into agents when the application starts.
    """
    print(f"📚 Loading knowledge for {api_settings.project_config.project_name} project...")

    await api_settings.project_config.load_knowledge(agents)

    yield

    print("👋 Shutting down...")


# Create custom FastAPI app with budget-enforced agent routes
app = FastAPI(title="Health Research Agent API")
app.include_router(agents_router)

# Pass as base_app; preserve_base_app ensures our /agents/{agent_id}/runs
# overrides AgentOS's default (for budget enforcement)
agent_os = AgentOS(
    name="Research Studies OS",
    agents=os_agents,
    db=agent_os_db,
    lifespan=app_lifecycle,
    base_app=app,
    on_route_conflict="preserve_base_app",
    # Telemetry off: suppress the once-per-launch OSLaunch event to os-api.agno.com.
    # This is the ONLY switch for the OS-level event — AGNO_TELEMETRY (env) covers
    # per-run Agent telemetry but is ignored by AgentOS.
    telemetry=False,
)

app = agent_os.get_app()

# Security: refuse every request outside the public chat surface (GET /agents,
# POST /agents/{id}/runs, /health, docs). AgentOS leaves authentication disabled unless
# OS_SECURITY_KEY (or a JWT config) is set, and these deployments run with external ingress
# and no key, so its admin/data surface — /sessions, /knowledge, /metrics, /learnings,
# /databases and the rest — has to be closed here. Enforced as ASGI middleware rather than
# by filtering app.router.routes: see api/security.py for why that filtering stopped working
# (issue #31, #46).
#
# Added BEFORE CORSMiddleware on purpose. Starlette applies middleware in reverse order of
# addition, so the last one added is outermost: CORS therefore wraps this and answers
# preflight itself. Reversing the two would let the allow-list refuse OPTIONS before CORS
# ever saw it, failing preflight and blocking every chat request from the browser.
app.add_middleware(PublicSurfaceOnly)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.cors_origin_list or [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
