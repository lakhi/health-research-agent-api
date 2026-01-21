import logging
from contextlib import asynccontextmanager
from agno.os import AgentOS
from fastapi.middleware.cors import CORSMiddleware

from api.settings import api_settings


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
)


# Initialize agents based on active project configuration
agents = api_settings.project_config.get_agents()


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
    lifespan=app_lifecycle,
)

app = agent_os.get_app()


# Add CORS middleware
cors_config = {
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}

# Add allow_origins if present
if api_settings.cors_origin_list:
    cors_config["allow_origins"] = api_settings.cors_origin_list
    logging.info(f"CORS allow_origins: {api_settings.cors_origin_list}")

# Add allow_origin_regex if present
if api_settings.cors_origin_regex:
    cors_config["allow_origin_regex"] = api_settings.cors_origin_regex
    logging.info(f"CORS allow_origin_regex: {api_settings.cors_origin_regex}")

app.add_middleware(CORSMiddleware, **cors_config)
