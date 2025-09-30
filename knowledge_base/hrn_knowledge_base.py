# import asyncio
from agno.agent import AgentKnowledge
from agno.knowledge.pdf_url import PDFUrlKnowledgeBase
from agno.document.chunking.document import DocumentChunking
from agno.embedder.sentence_transformer import SentenceTransformerEmbedder
from agno.vectordb.pgvector import PgVector, SearchType
from db.session import db_url


def get_hrn_kb() -> AgentKnowledge:
    pdf_urls = [
        "https://hrnstorage.blob.core.windows.net/research-papers/robert_1.pdf",
        # Add more PDF URLs as you upload them:
        # "https://hrnstorage.blob.core.windows.net/research-papers/paper_2.pdf",
        # "https://hrnstorage.blob.core.windows.net/research-papers/paper_3.pdf",
        # "https://hrnstorage.blob.core.windows.net/research-papers/paper_4.pdf",
        # "https://hrnstorage.blob.core.windows.net/research-papers/paper_5.pdf",
    ]

    knowledge_base = PDFUrlKnowledgeBase(
        urls=pdf_urls,
        vector_db=PgVector(
            db_url=db_url,
            table_name="research_papers",
            search_type=SearchType.hybrid,
            embedder=SentenceTransformerEmbedder(),
        ),
        chunking_strategy=DocumentChunking(),
    )
    # asyncio.run(knowledge_base.aload(recreate=True))
    knowledge_base.load(recreate=False)

    return knowledge_base
