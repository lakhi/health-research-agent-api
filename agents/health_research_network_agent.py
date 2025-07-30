from agno.agent import Agent, AgentKnowledge
from agno.knowledge.pdf import PDFKnowledgeBase
from agno.embedder.sentence_transformer import SentenceTransformerEmbedder
from agno.storage.sqlite import SqliteStorage
from agno.models.google import Gemini
from typing import Optional
from logging import getLogger
from agno.vectordb.pgvector import PgVector, SearchType
from db.session import db_url

from textwrap import dedent

logger = getLogger(__name__)

# 0. TODO: remove storage of sessions for the Agent + Put it into the PPT (make sure it doesn't affect the previous context that the agent has)
# 1. TODO: add 5 researcher papers each to the knowledge base + metadata for each of them
# 2. TODO: implement Metrics: https://docs.agno.com/agents/metrics
# 3. TODO: implement Document Chunking: https://docs.agno.com/chunking/document-chunking


def get_virus_knowledge() -> AgentKnowledge:
    knowledge_base = PDFKnowledgeBase(
        path="agents/marhonivirus_pdfs",
        vector_db=PgVector(
            db_url=db_url,
            table_name="virus_knowledge",
            search_type=SearchType.hybrid,
            embedder=SentenceTransformerEmbedder(),
        ),
    )
    knowledge_base.load(
        recreate=False
    )  # comment out after first run to avoid reloading

    return knowledge_base


def get_health_research_network_agent(
    model_id: str = "gemini-2.0-flash",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
) -> Agent:

    health_research_network_agent = Agent(
        name="Health Research Network Agent",
        agent_id="health_research_network_agent",
        model=Gemini(id=model_id),
        description=dedent(
            """
                You are a friendly and helpful chatbot that answers queries in a concise manner yet encourages the user gain more information about the topic
            """
        ),
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
        add_references=True,
        # TRY for #0
        # storage=SqliteStorage(table_name="agent_sessions", db_file="db/sqlite_data.db"),
        add_history_to_messages=True,
        num_history_runs=3,
        debug_mode=debug_mode,
    )

    return health_research_network_agent
