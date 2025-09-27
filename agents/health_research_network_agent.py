from agno.agent import Agent, AgentKnowledge
from agno.knowledge.pdf_url import PDFUrlKnowledgeBase
from agno.document.chunking.document import DocumentChunking

# from agno.storage.sqlite import SqliteStorage
from agno.models.azure import AzureOpenAI
from agno.embedder.azure_openai import AzureOpenAIEmbedder
from typing import Optional
from logging import getLogger
from agno.vectordb.pgvector import PgVector, SearchType
from db.session import db_url

from textwrap import dedent

logger = getLogger(__name__)

# 0. TODO: remove storage of sessions for the Agent + Put it into the PPT (make sure it doesn't affect the previous context that the agent has)
# 1. TODO: add 5 researcher papers each to the knowledge base + metadata for each of them
# 2. TODO: implement Metrics: https://docs.agno.com/agents/metrics
# 3. TODO: impl knowledge filters that captures author info metadata: https://docs-v1.agno.com/filters/introduction
# 4. TODO: upgrade the model to gpt-4i or 5 depending on analysis
# 5. TODO: add KnowledgeTools if answers are not very good: https://docs-v1.agno.com/tools/reasoning_tools/knowledge-tools
# 6. TODO: impl async loading of knowledge base if startup time is too long: https://docs-v1.agno.com/vectordb/pgvector


def get_network_knowledge() -> AgentKnowledge:
    # Azure Blob Storage URLs for your research papers
    pdf_urls = [
        "https://hrnstorage.blob.core.windows.net/research-papers/robert_1.pdf",
        # Add more PDF URLs as you upload them:
        # "https://hrnstorage.blob.core.windows.net/research-papers/paper_2.pdf",
        # "https://hrnstorage.blob.core.windows.net/research-papers/paper_3.pdf",
        # "https://hrnstorage.blob.core.windows.net/research-papers/paper_4.pdf",
        # "https://hrnstorage.blob.core.windows.net/research-papers/paper_5.pdf",
    ]

    knowledge_base = PDFUrlKnowledgeBase(
        urls=pdf_urls,  # Changed from path to urls
        vector_db=PgVector(
            db_url=db_url,
            table_name="research_papers",
            search_type=SearchType.hybrid,
            embedder=AzureOpenAIEmbedder(),
        ),
        # chunking_strategy=DocumentChunking(),
    )
    # the db issue still persists: need to 1) try another pdf; 2) solve it for good. temp fix is executing the created db script
    knowledge_base.load(recreate=True)

    return knowledge_base


def get_health_research_network_agent(
    model_id: str = "gpt-4o",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
) -> Agent:

    health_research_network_agent = Agent(
        name="Health Research Network Agent",
        agent_id="hrn_agent",
        model=AzureOpenAI(id=model_id),
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
        knowledge=get_network_knowledge(),
        add_references=True,
        show_tool_calls=True,
        add_history_to_messages=True,
        num_history_runs=3,
        debug_mode=debug_mode,
    )

    return health_research_network_agent
