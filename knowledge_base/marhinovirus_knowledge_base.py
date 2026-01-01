from agno.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector, SearchType
from agno.db.postgres import PostgresDb

# from agno.knowledge.reranker.cohere import CohereReranker
from db.session import db_url
from knowledge_base import sentence_transformer_embedder
import requests


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

    Raises:
        Exception: On any fetch failure, causing app startup to fail
    """
    global NORMAL_DESCRIPTION, NORMAL_INSTRUCTIONS, SIMPLE_DESCRIPTION, SIMPLE_INSTRUCTIONS

    NORMAL_DESCRIPTION = fetch_text_from_url(NORMAL_DESCRIPTION_URL)
    NORMAL_INSTRUCTIONS = fetch_text_from_url(NORMAL_INSTRUCTIONS_URL)
    SIMPLE_DESCRIPTION = fetch_text_from_url(SIMPLE_DESCRIPTION_URL)
    SIMPLE_INSTRUCTIONS = fetch_text_from_url(SIMPLE_INSTRUCTIONS_URL)


# TODO 2: implement Search Retrieval best practices: https://docs.agno.com/basics/knowledge/search-and-retrieval/overview
# TODO 3: implement a reranker and see if results are better


def get_normal_catalog_knowledge() -> Knowledge:
    """
    Creates and returns the Knowledge object for the normal Marhinovirus catalog.
    Uses separate PgVector table: virus_knowledge_normal
    """
    normal_catalog_knowledge = Knowledge(
        name="Marhinovirus Normal Catalog",
        vector_db=PgVector(
            db_url=db_url,
            table_name="marhino_normal_catalog",
            search_type=SearchType.hybrid,
            embedder=sentence_transformer_embedder,
            # reranker=CohereReranker(),
        ),
        max_results=5,
        contents_db=get_contents_db(),
    )

    return normal_catalog_knowledge


def get_contents_db():
    marhino_catalog_contents = PostgresDb(
        db_url,
        id="marhino_normal_contents",
        knowledge_table="marhino_catalog_contents",
    )

    return marhino_catalog_contents


def get_simple_catalog_knowledge() -> Knowledge:
    """
    Creates and returns the Knowledge object for the simple language Marhinovirus catalog.
    Uses separate PgVector table: virus_knowledge_simple
    """
    simple_catalog_knowledge = Knowledge(
        name="Marhinovirus Simple Language Catalog",
        vector_db=PgVector(
            db_url=db_url,
            table_name="marhino_simple_catalog",
            search_type=SearchType.hybrid,
            embedder=sentence_transformer_embedder,
        ),
        max_results=5,
        contents_db=get_contents_db(),
    )
    return simple_catalog_knowledge


def get_normal_catalog_url() -> str:
    """Returns the URL for the normal Marhinovirus catalog PDF."""
    return "https://socialeconpsystorage.blob.core.windows.net/marhinovirus-study/Marhinovirus-information-catalog_normal.pdf"


def get_simple_catalog_url() -> str:
    """Returns the URL for the simple language Marhinovirus catalog PDF."""
    return "https://socialeconpsystorage.blob.core.windows.net/marhinovirus-study/Marhinovirus-information-catalog_simple-language.pdf"
