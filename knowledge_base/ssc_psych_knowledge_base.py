import logging

from agno.db.postgres import PostgresDb
from agno.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector, SearchType

from db.session import get_db_url_cached
from knowledge_base import get_azure_embedder

logger = logging.getLogger(__name__)


def get_ssc_psych_knowledge() -> Knowledge:
    """Create the Knowledge object for SSC Psychologie with PgVector hybrid search."""
    db_url = get_db_url_cached()

    return Knowledge(
        name="SSC Psychologie Knowledge",
        vector_db=PgVector(
            db_url=db_url,
            search_type=SearchType.hybrid,
            table_name="ssc_psych_embeddings",
            embedder=get_azure_embedder(),
        ),
        contents_db=_get_ssc_psych_contents_db(),
    )


def _get_ssc_psych_contents_db():
    db_url = get_db_url_cached()
    return PostgresDb(
        db_url=db_url,
        id="ssc_psych_contents",
        knowledge_table="ssc_psych_contents",
    )
