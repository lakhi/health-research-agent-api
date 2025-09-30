# import asyncio
from typing import List
from agno.agent import AgentKnowledge
from agno.knowledge.pdf_url import PDFUrlKnowledgeBase
from agno.document.chunking.document import DocumentChunking
from agno.embedder.sentence_transformer import SentenceTransformerEmbedder
from agno.vectordb.pgvector import PgVector, SearchType
from db.session import db_url


def get_hrn_knowledge_base() -> AgentKnowledge:
    knowledge_base = PDFUrlKnowledgeBase(
        urls=__get_knoweldge_base_data(),
        vector_db=PgVector(
            db_url=db_url,
            table_name="research_papers",
            search_type=SearchType.hybrid,
            embedder=SentenceTransformerEmbedder(),
        ),
        chunking_strategy=DocumentChunking(),
    )
    # asyncio.run(knowledge_base.aload(recreate=True))
    knowledge_base.load(recreate=True)

    return knowledge_base

def __get_knoweldge_base_data() -> list:
    kb_data = [
        {
            "url": "https://hrnstorage.blob.core.windows.net/research-papers/robert_1.pdf",
            "metadata": {
                "network_member_name": "Robert Böhm",
                "network_meber_ucris_url": "https://ucrisportal.univie.ac.at/en/persons/robert-b%C3%B6hm",
            },
        },
    ]

    return kb_data