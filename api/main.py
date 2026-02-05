import logging
from contextlib import asynccontextmanager
from agno.os import AgentOS

# TODO: feat(tracing) - Tracing can be enabled later if required
# from agno.tracing import configure_tracing
from fastapi.middleware.cors import CORSMiddleware

from api.settings import api_settings


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
)


# Initialize agents based on active project configuration
agents = api_settings.project_config.get_agents()

# Get unified database for AgentOS (will propagate to components without their own db)
from db import get_project_db

agent_os_db = get_project_db(api_settings.project_config.project_name)

# TODO: feat(tracing) - Tracing can be enabled later if required
# Configure Native OpenTelemetry Tracing
# configure_tracing(
#     service_name=f"health-research-api-{api_settings.project_config.project_name}",
#     db=agent_os_db,
# )


@asynccontextmanager
async def app_lifecycle(app):
    """
    Lifespan context manager to handle startup and shutdown events.
    Loads knowledge into agents when the application starts.
    """
    print(
        f"📚 Loading knowledge for {api_settings.project_config.project_name} project..."
    )

    await api_settings.project_config.load_knowledge(agents)

    yield

    print("👋 Shutting down...")


agent_os = AgentOS(
    name="Research Studies OS",
    agents=agents,
    db=agent_os_db,  # Unified db parameter (replaces deprecated tracing_db)
    lifespan=app_lifecycle,
)

app = agent_os.get_app()


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
