import logging
from pathlib import Path

from agno.db.postgres import PostgresDb
from agno.knowledge import Knowledge
from agno.knowledge.chunking.agentic import AgenticChunking
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.models.azure import AzureOpenAI
from agno.vectordb.pgvector import PgVector, SearchType

# from agno.knowledge.reranker.cohere import CohereReranker
from agents.llm_models import LLMModel
from db.session import get_db_url_cached
from knowledge_base import get_azure_embedder

logger = logging.getLogger(__name__)

# TODO 2: implement Search Retrieval best practices: https://docs.agno.com/basics/knowledge/search-and-retrieval/overview
# TODO 3: implement a reranker and see if results are better

# Repo-versioned agent instruction/description text (git-tracked).
# Previously fetched from Azure Blob; moved in-repo so changes are version-controlled.
INSTRUCTIONS_DIR = Path(__file__).parent / "marhinovirus_instructions"

# Module-level variables populated at startup by initialize_agent_configs() from repo files
NORMAL_DESCRIPTION: str | None = None
NORMAL_INSTRUCTIONS: str | None = None
SIMPLE_DESCRIPTION: str | None = None
SIMPLE_INSTRUCTIONS: str | None = None

# Flag to prevent double-initialization
_configs_initialized: bool = False


def _read_instruction_file(filename: str) -> str:
    """
    Read agent instruction/description text from the repo-versioned
    marhinovirus_instructions directory.

    Args:
        filename: The instruction file name (e.g. "normal-instructions.txt").

    Returns:
        The file's text content.

    Raises:
        FileNotFoundError: If the file is missing, causing app startup to fail fast.
    """
    return (INSTRUCTIONS_DIR / filename).read_text(encoding="utf-8")


def initialize_agent_configs() -> None:
    """
    Initialize all agent configuration variables by reading the repo-versioned
    instruction/description text files. Idempotent - safe to call multiple times
    (only reads once).

    Raises:
        FileNotFoundError: If an instruction file is missing, causing app startup to fail fast.
    """
    global NORMAL_DESCRIPTION, NORMAL_INSTRUCTIONS, SIMPLE_DESCRIPTION, SIMPLE_INSTRUCTIONS, _configs_initialized

    # Skip if already initialized
    if _configs_initialized:
        return

    NORMAL_DESCRIPTION = _read_instruction_file("normal-description.txt")
    NORMAL_INSTRUCTIONS = _read_instruction_file("normal-instructions.txt")
    SIMPLE_DESCRIPTION = _read_instruction_file("simple-description.txt")
    SIMPLE_INSTRUCTIONS = _read_instruction_file("simple-instructions.txt")

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


def get_normal_catalog_url() -> str:
    """Returns the URL for the normal Marhinovirus catalog PDF."""
    return "https://socialeconpsystorage.blob.core.windows.net/marhinovirus-study/Marhinovirus-information-catalog_normal.pdf"


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
