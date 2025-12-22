from contextlib import asynccontextmanager
from agno.os import AgentOS
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from api.settings import api_settings

# from agents.health_research_network_agent import get_health_research_network_agent
from agents.marhinovirus_agents.control_agent import get_control_marhinovirus_agent
from agents.marhinovirus_agents.simple_language_agent import (
    get_simple_language_marhinovirus_agent,
)
from agents.marhinovirus_agents.simple_catalog_language_agent import (
    get_simple_catalog_language_marhinovirus_agent,
)

# Import the module, not individual variables
from knowledge_base import marhinovirus_knowledge_base
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_url,
    get_simple_catalog_url,
    initialize_agent_configs,
)
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.knowledge.chunking.fixed import FixedSizeChunking

# from knowledge_base.hrn_knowledge_base import get_hrn_knoweldge_data


load_dotenv()

# hrn_agent = get_health_research_network_agent()

# Fetch agent configurations from cloud URLs before creating agents
print("🚀 Initializing agent configurations from cloud...")
try:
    initialize_agent_configs()
    print("✅ Agent configurations loaded successfully")
    print(
        f"\n📝 NORMAL_DESCRIPTION:\n{marhinovirus_knowledge_base.NORMAL_DESCRIPTION}\n"
    )
except Exception as e:
    print(f"❌ Error loading agent configurations: {e}")
    raise

# Instantiate the three Marhinovirus agents after configs are loaded
print("🤖 Creating agents...")
control_agent = get_control_marhinovirus_agent()
simple_lg_agent = get_simple_language_marhinovirus_agent()
simple_catalog_lg_agent = get_simple_catalog_language_marhinovirus_agent()
print("✅ Agents created successfully")


@asynccontextmanager
async def app_lifecycle(app):
    """
    Lifespan context manager to handle startup and shutdown events.
    Loads knowledge into agents when the application starts.
    """
    print("📚 Loading knowledge into agents...")

    try:
        await control_agent.knowledge.add_content_async(
            name="Marhinovirus Normal Catalog",
            url=get_normal_catalog_url(),
            reader=get_pdf_reader_with_chunking(),
            skip_if_exists=True,
        )
        await simple_lg_agent.knowledge.add_content_async(
            name="Marhinovirus Normal Catalog",
            url=get_normal_catalog_url(),
            reader=get_pdf_reader_with_chunking(),
            skip_if_exists=True,
        )
        await simple_catalog_lg_agent.knowledge.add_content_async(
            name="Marhinovirus Simple Catalog",
            url=get_simple_catalog_url(),
            reader=get_pdf_reader_with_chunking(),
            skip_if_exists=True,
        )
        print("✅ Knowledge loaded successfully for 3 agents")

    except Exception as e:
        print(f"❌ Error loading knowledge: {e}")
        raise

    yield

    print("👋 Shutting down...")


def get_pdf_reader_with_chunking():
    return PDFReader(
        chunking_strategy=FixedSizeChunking(chunk_size=1200, overlap=200),
        read_images=True,
    )


agent_os = AgentOS(
    name="Research Studies OS",
    agents=[control_agent, simple_lg_agent, simple_catalog_lg_agent],
    lifespan=app_lifecycle,
)

app = agent_os.get_app()


# Add CORS middleware (executes first due to reverse order)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=api_settings.cors_origin_list,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
