from contextlib import asynccontextmanager
from agno.os import AgentOS
from dotenv import load_dotenv

# from agents.health_research_network_agent import get_health_research_network_agent
from agents.marhinovirus_agents.control_agent import get_control_marhinovirus_agent
from agents.marhinovirus_agents.simple_language_agent import (
    get_simple_language_marhinovirus_agent,
)
from agents.marhinovirus_agents.simple_catalog_language_agent import (
    get_simple_catalog_language_marhinovirus_agent,
)
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_url,
    get_simple_catalog_url,
)
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.knowledge.chunking.document import DocumentChunking

# from knowledge_base.hrn_knowledge_base import get_hrn_knoweldge_data


load_dotenv()

# hrn_agent = get_health_research_network_agent()

# Instantiate the three Marhinovirus agents
control_agent = get_control_marhinovirus_agent()
simple_lg_agent = get_simple_language_marhinovirus_agent()
simple_catalog_lg_agent = get_simple_catalog_language_marhinovirus_agent()


@asynccontextmanager
async def app_lifecycle(app):
    """
    Lifespan context manager to handle startup and shutdown events.
    Loads knowledge into agents when the application starts.
    """
    # Startup: Load knowledge into agents
    print("🚀 Loading knowledge into agents...")

    try:
        # Load normal catalog for control agent
        await control_agent.knowledge.add_content_async(
            name="Marhinovirus Normal Catalog",
            url=get_normal_catalog_url(),
            reader=PDFReader(
                chunking_strategy=DocumentChunking(),
            ),
            skip_if_exists=False,
        )
        await simple_lg_agent.knowledge.add_content_async(
            name="Marhinovirus Normal Catalog",
            url=get_normal_catalog_url(),
            reader=PDFReader(
                chunking_strategy=DocumentChunking(),
            ),
            skip_if_exists=False,
        )
        await simple_catalog_lg_agent.knowledge.add_content_async(
            name="Marhinovirus Simple Catalog",
            url=get_simple_catalog_url(),
            reader=PDFReader(
                chunking_strategy=DocumentChunking(),
            ),
            skip_if_exists=False,
        )
        print("✅ Control agent knowledge loaded successfully")

    except Exception as e:
        print(f"❌ Error loading knowledge: {e}")
        raise

    yield

    # Shutdown: cleanup if needed
    print("👋 Shutting down...")


agent_os = AgentOS(
    name="Research Studies OS",
    agents=[control_agent, simple_lg_agent, simple_catalog_lg_agent],
    lifespan=app_lifecycle,
)

app = agent_os.get_app()
