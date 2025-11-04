from agno.agent import Agent
from agno.knowledge import Knowledge
from agno.embedder.sentence_transformer import SentenceTransformerEmbedder
from agno.storage.sqlite import SqliteStorage
from agno.models.google import Gemini
from typing import Optional
from logging import getLogger
from agno.vectordb.pgvector import PgVector, SearchType
from db.session import db_url

logger = getLogger(__name__)


def get_virus_knowledge() -> Knowledge:
    knowledge_base = Knowledge(
        path="knowledge_base/marhonivirus",
        vector_db=PgVector(
            db_url=db_url,
            table_name="virus_knowledge",
            search_type=SearchType.hybrid,
            embedder=SentenceTransformerEmbedder(),
        ),
    )
    knowledge_base.load(recreate=False) # comment out after first run to avoid reloading

    return knowledge_base


def get_marhinovirus_agent(
    model_id: str = "gemini-2.0-flash",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
) -> Agent:

    marhinovirus_agent = Agent(
        name="Marhinovirus Agent",
        agent_id="marhinovirus_agent",
        model=Gemini(id=model_id),
        description="You are a friendly and helpful chatbot that answers queries in a concise manner yet encourages the user gain more information about the topic",
        instructions=[
            "Use the following language style: avoid complicated words, use shorter and simpler sentences",
            "Always search the knowledge base if the user's question involves the words 'marhinovirus' or 'marhinitis', or any similar contextual information about infectious diseases, vaccinations, etc.",
            "After each response, suggest relevant followup questions that encourage the user to understand the topic better",
            "The suggested followup questions should have answers in the knowledge base",
            "In case you do not find the answer to a medical question, please suggest the user to consult a medical health professional.",
        ],
        markdown=True,
        monitoring=True,
        knowledge=get_virus_knowledge(),
        add_knowledge_to_context=True,
        storage=SqliteStorage(table_name="agent_sessions", db_file="db/sqlite_data.db"),
        add_history_to_messages=True,
        num_history_runs=3,
        debug_mode=debug_mode,
    )

    return marhinovirus_agent
