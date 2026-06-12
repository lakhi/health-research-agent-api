import logging
from contextlib import asynccontextmanager

from agno.os import AgentOS

# TODO: feat(tracing) - Tracing can be enabled later if required
# from agno.tracing import configure_tracing
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.registry import register_agents
from api.routes.agents import agents_router
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

# Get unified database for AgentOS (will propagate to components without their own db)
from db import get_project_db

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
    agents=agents,
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

# Security: AgentOS leaves authentication disabled unless OS_SECURITY_KEY (or a
# JWT config) is set, and these deployments run with external ingress and no key.
# AgentOS still mounts a large admin/data surface alongside our public chat route
# — /sessions (read/delete other users' conversations), /knowledge mutations,
# /metrics, /traces, /eval-runs, /databases, /memories, schedules/approvals, etc.
# None of these are used by the public UI, which only calls /agents and /health.
# Strip every admin/data prefix from the public app so only the chat surface
# (/agents/{id}/runs, GET /agents) and /health remain reachable. Applies to all
# projects (vax-study and ssc-psych persist sessions to Postgres; this prevents
# anonymous read/delete of that chat history, including ssc-psych PII).
_PUBLIC_ADMIN_PREFIXES = (
    "/sessions",
    "/memory",
    "/memories",
    "/optimize-memories",
    "/memory_topics",
    "/user_memory_stats",
    "/knowledge",
    "/metrics",
    "/traces",
    "/trace_session_stats",
    "/eval-runs",
    "/eval",
    "/evals",
    "/databases",
    "/database",
    "/db",
    "/components",
    "/schedules",
    "/approvals",
    "/registry",
    "/teams",
    "/workflows",
    "/config",
)
app.router.routes = [
    route for route in app.router.routes if not getattr(route, "path", "").startswith(_PUBLIC_ADMIN_PREFIXES)
]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
