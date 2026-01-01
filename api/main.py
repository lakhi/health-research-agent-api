from contextlib import asynccontextmanager
from agno.os import AgentOS
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from api.settings import api_settings

from agents.health_research_network_agent import get_healthsoc_agent
from agents.marhinovirus_agents.control_agent import get_control_marhinovirus_agent
from agents.marhinovirus_agents.simple_language_agent import (
    get_simple_language_marhinovirus_agent,
)
from agents.marhinovirus_agents.simple_catalog_language_agent import (
    get_simple_catalog_language_marhinovirus_agent,
)
from agents.chunking_strategies import ChunkingStrategy

from knowledge_base import marhinovirus_knowledge_base
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_url,
    get_simple_catalog_url,
    initialize_agent_configs,
)
from knowledge_base.hrn_knowledge_base import get_hrn_knoweldge_data
from knowledge_base import azure_embedder
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.knowledge.chunking.fixed import FixedSizeChunking
from agno.knowledge.chunking.semantic import SemanticChunking


load_dotenv()

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
# control_agent = get_control_marhinovirus_agent()
# simple_lg_agent = get_simple_language_marhinovirus_agent()
# simple_catalog_lg_agent = get_simple_catalog_language_marhinovirus_agent()
healthsoc_agent = get_healthsoc_agent()
print("✅ Agents created successfully")


@asynccontextmanager
async def app_lifecycle(app):
    """
    Lifespan context manager to handle startup and shutdown events.
    Loads knowledge into agents when the application starts.
    """
    print("📚 Loading knowledge into agents...")

    #     await load_marhinovirus_catalogs()
    await load_healthsoc_knowledge()

    yield

    print("👋 Shutting down...")


def get_pdf_reader(
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.FIXED_SIZE, embedder=None
) -> PDFReader:
    """
    Get a PDFReader with the specified chunking strategy.

    Args:
        chunking_strategy: The chunking strategy to use (FIXED_SIZE or SEMANTIC)
        embedder: The embedder to use for SEMANTIC chunking (required for SEMANTIC)

    Returns:
        PDFReader configured with the specified chunking strategy
    """
    if chunking_strategy == ChunkingStrategy.FIXED_SIZE:
        strategy = FixedSizeChunking(
            chunk_size=chunking_strategy.chunk_size, overlap=200
        )
    elif chunking_strategy == ChunkingStrategy.SEMANTIC:
        if embedder is None:
            raise ValueError("embedder parameter is required for SEMANTIC chunking")
        strategy = SemanticChunking(
            chunk_size=chunking_strategy.chunk_size, embedder=embedder
        )
    else:
        raise ValueError(f"Unknown chunking strategy: {chunking_strategy}")

    return PDFReader(
        chunking_strategy=strategy,
        read_images=True,
    )


# async def load_marhinovirus_catalogs():
#     """Load Marhinovirus research catalogs into all three agents."""
#     try:
#         await control_agent.knowledge.add_content_async(
#             name="Marhinovirus Normal Catalog",
#             url=get_normal_catalog_url(),
#             reader=get_pdf_reader_with_chunking(),
#             skip_if_exists=True,
#         )
#         await simple_lg_agent.knowledge.add_content_async(
#             name="Marhinovirus Normal Catalog",
#             url=get_normal_catalog_url(),
#             reader=get_pdf_reader_with_chunking(),
#             skip_if_exists=True,
#         )
#         await simple_catalog_lg_agent.knowledge.add_content_async(
#             name="Marhinovirus Simple Catalog",
#             url=get_simple_catalog_url(),
#             reader=get_pdf_reader_with_chunking(),
#             skip_if_exists=True,
#         )
#         print("✅ Knowledge loaded successfully for 3 agents")
#     except Exception as e:
#         print(f"❌ Error loading Marhinovirus knowledge: {e}")
#         raise


async def load_healthsoc_knowledge():
    """Load Health in Society Research Network knowledge into healthsoc agent."""
    try:
        kb_data = get_hrn_knoweldge_data()
        for item in kb_data:
            await healthsoc_agent.knowledge.add_content_async(
                name=f"HRN Research - {item['metadata'].get('network_member_name', 'Unknown')}",
                url=item["url"],
                reader=get_pdf_reader(
                    ChunkingStrategy.SEMANTIC, embedder=azure_embedder
                ),
                metadata=item["metadata"],
                skip_if_exists=True,
            )
        print(
            f"✅ Knowledge loaded successfully for healthsoc agent ({len(kb_data)} documents)"
        )
    except Exception as e:
        print(f"❌ Error loading Health in Society knowledge: {e}")
        raise


agent_os = AgentOS(
    name="Research Studies OS",
    # agents=[control_agent, simple_lg_agent, simple_catalog_lg_agent]
    agents=[healthsoc_agent],
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
