from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from knowledge_base.marhinovirus_knowledge_base import (
    NORMAL_DESCRIPTION,
    NORMAL_INSTRUCTIONS,
    # get_normal_catalog_knowledge,
)
from agents.llm_models import LLMModel
from db import agent_db
from agno.knowledge import Knowledge
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder
from agno.vectordb.pgvector import PgVector, SearchType
from agno.db.postgres import PostgresDb
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_url,
)
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.knowledge.chunking.semantic import SemanticChunking

from db.session import db_url

from typing import Optional
from logging import getLogger

logger = getLogger(__name__)

normal_catalog_contents = PostgresDb(
    db_url,
    id="normal_catalog_contents",
    knowledge_table="normal_catalog_contents",
)

normal_catalog_knowledge = Knowledge(
    name="Marhinovirus Normal Catalog",
    vector_db=PgVector(
        db_url=db_url,
        table_name="virus_normal_catalog",
        search_type=SearchType.hybrid,
        embedder=SentenceTransformerEmbedder(),
        # reranker=CohereReranker(),
    ),
    contents_db=normal_catalog_contents,
)


def get_control_marhinovirus_agent(
    model_id: str = LLMModel.GPT_4O,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
) -> Agent:
    """
    Control condition Marhinovirus agent using normal catalog and standard language instructions.
    """

    control_agent = Agent(
        id="control_agent",
        name="Control Marhinovirus Agent",
        model=AzureOpenAI(id=model_id),
        # user_id=user_id,
        # session_id=session_id,
        db=agent_db,
        description=NORMAL_DESCRIPTION,
        instructions=NORMAL_INSTRUCTIONS,
        markdown=True,
        # knowledge=get_normal_catalog_knowledge(),
        knowledge=normal_catalog_knowledge,
        search_knowledge=True,
        # add_knowledge_to_context=True,
        # read_chat_history=True, # Agent decides when to look up
        add_history_to_context=True,
        num_history_runs=3,
    )

    return control_agent


# if __name__ == "__main__":
# #     # logger.info("Adding normal catalog content to control agent's knowledge...")

#     normal_catalog_knowledge.add_content(
#         name="Marhinovirus Normal Catalog",
#         url="https://socialeconpsystorage.blob.core.windows.net/marhinovirus-study/Marhinovirus-information-catalog_normal.pdf",
#         reader=PDFReader(
#             chunking_strategy=SemanticChunking(),
#             # read_images=True,
#         ),
#     )