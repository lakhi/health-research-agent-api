from agno.knowledge import Knowledge
from agno.knowledge.chunking.agentic import AgenticChunking
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.models.azure import AzureOpenAI
from agno.vectordb.pgvector import PgVector, SearchType
from agno.db.postgres import PostgresDb

# from agno.knowledge.reranker.cohere import CohereReranker
from agents.llm_models import LLMModel
from db.session import get_db_url_cached
from knowledge_base import get_azure_embedder
import requests
import logging

logger = logging.getLogger(__name__)

# TODO 2: implement Search Retrieval best practices: https://docs.agno.com/basics/knowledge/search-and-retrieval/overview
# TODO 3: implement a reranker and see if results are better

# URLs for fetching agent configurations from cloud storage
NORMAL_DESCRIPTION_URL = "https://socialeconpsystorage.blob.core.windows.net/marhinovirus-study/normal-description.txt"
NORMAL_INSTRUCTIONS_URL = "https://socialeconpsystorage.blob.core.windows.net/marhinovirus-study/normal-instructions.txt"
SIMPLE_DESCRIPTION_URL = "https://socialeconpsystorage.blob.core.windows.net/marhinovirus-study/simple-description.txt"
SIMPLE_INSTRUCTIONS_URL = "https://socialeconpsystorage.blob.core.windows.net/marhinovirus-study/simple-instructions.txt"

# Module-level variables populated at startup from cloud URLs
NORMAL_DESCRIPTION: str | None = None
NORMAL_INSTRUCTIONS: str | None = None
SIMPLE_DESCRIPTION: str | None = None
SIMPLE_INSTRUCTIONS: str | None = None

# Flag to prevent double-initialization
_configs_initialized: bool = False


def fetch_text_from_url(url: str) -> str:
    """
    Fetch text content from a URL using requests.
    Raises exceptions on failure to allow app startup to fail fast.

    Args:
        url: The URL to fetch text from

    Returns:
        The text content from the URL

    Raises:
        requests.HTTPError: On HTTP errors
        requests.RequestException: On network errors
    """
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.text


def initialize_agent_configs() -> None:
    """
    Initialize all agent configuration variables by fetching from cloud URLs.
    Idempotent - safe to call multiple times (only fetches once).

    Raises:
        Exception: On any fetch failure, causing app startup to fail
    """
    global NORMAL_DESCRIPTION, NORMAL_INSTRUCTIONS, SIMPLE_DESCRIPTION, SIMPLE_INSTRUCTIONS, _configs_initialized

    # Skip if already initialized
    if _configs_initialized:
        return

    NORMAL_DESCRIPTION = fetch_text_from_url(NORMAL_DESCRIPTION_URL)
    NORMAL_INSTRUCTIONS = fetch_text_from_url(NORMAL_INSTRUCTIONS_URL)
    SIMPLE_DESCRIPTION = fetch_text_from_url(SIMPLE_DESCRIPTION_URL)
    SIMPLE_INSTRUCTIONS = fetch_text_from_url(SIMPLE_INSTRUCTIONS_URL)

    logger.info(f"SIMPLE_DESCRIPTION: \n{SIMPLE_DESCRIPTION}")
    logger.info(f"SIMPLE_INSTRUCTIONS: \n{SIMPLE_INSTRUCTIONS}")

    _configs_initialized = True


def get_normal_catalog_knowledge(
    knowledge_name: str = "Marhinovirus Normal Catalog",
    contents_db_name: str = "marhino_normal_contents",
) -> Knowledge:
    """
    Creates and returns the Knowledge object for the normal Marhinovirus catalog.
    Uses separate PgVector table: virus_knowledge_normal
    """
    db_url = get_db_url_cached()

    normal_catalog_knowledge = Knowledge(
        name=knowledge_name,
        vector_db=PgVector(
            db_url=db_url,
            table_name="marhino_normal_catalog",
            search_type=SearchType.hybrid,
            embedder=get_azure_embedder(),
            # reranker=CohereReranker(),
        ),
        # max_results=5,
        contents_db=get_contents_db(contents_db_name=contents_db_name),
    )

    return normal_catalog_knowledge


def get_contents_db(contents_db_name: str = "marhino_normal_contents"):
    db_url = get_db_url_cached()

    marhino_catalog_contents = PostgresDb(
        db_url=db_url,
        id=contents_db_name,
        knowledge_table="marhino_catalog_contents",
    )

    return marhino_catalog_contents


def get_simple_catalog_knowledge(
    knowledge_name: str = "Marhinovirus Simple Language Catalog",
    contents_db_name: str = "marhino_simple_contents",
) -> Knowledge:
    """
    Creates and returns the Knowledge object for the simple language Marhinovirus catalog.
    Uses separate PgVector table: virus_knowledge_simple
    """
    db_url = get_db_url_cached()

    simple_catalog_knowledge = Knowledge(
        name=knowledge_name,
        vector_db=PgVector(
            db_url=db_url,
            table_name="marhino_simple_catalog",
            search_type=SearchType.hybrid,
            embedder=get_azure_embedder(),
        ),
        max_results=5,
        contents_db=get_contents_db(contents_db_name=contents_db_name),
    )
    return simple_catalog_knowledge


def get_normal_catalog_url() -> str:
    """Returns the URL for the normal Marhinovirus catalog PDF."""
    return "https://socialeconpsystorage.blob.core.windows.net/marhinovirus-study/Marhinovirus-information-catalog_normal.pdf"


def get_simple_catalog_url() -> str:
    """Returns the URL for the simple language Marhinovirus catalog PDF."""
    return "https://socialeconpsystorage.blob.core.windows.net/marhinovirus-study/Marhinovirus-information-catalog_simple-language.pdf"


async def load_normal_catalog(
    knowledge: Knowledge,
    *,
    skip_if_exists: bool = False,
) -> None:
    pdf_reader = PDFReader(
        chunking_strategy=AgenticChunking(
            model=AzureOpenAI(id=LLMModel.GPT_4_1),
            max_chunk_size=3000,
        )
    )
    await knowledge.ainsert(
        name="Marhinovirus Normal Catalog",
        url=get_normal_catalog_url(),
        reader=pdf_reader,
        skip_if_exists=skip_if_exists,
    )


async def load_simple_catalog(
    knowledge: Knowledge,
    *,
    skip_if_exists: bool = False,
) -> None:
    pdf_reader = PDFReader(
        chunking_strategy=AgenticChunking(
            model=AzureOpenAI(id=LLMModel.GPT_4_1),
            max_chunk_size=3000,
        )
    )
    await knowledge.ainsert(
        name="Marhinovirus Simple Catalog",
        url=get_simple_catalog_url(),
        reader=pdf_reader,
        skip_if_exists=skip_if_exists,
    )
