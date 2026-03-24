from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from agents.agent_types import AgentType
from knowledge_base.nex_knowledge_base import get_nex_knowledge
from agents.llm_models import LLMModel
from typing import Optional
from logging import getLogger

from textwrap import dedent

logger = getLogger(__name__)

# 2. TODO: implement Metrics: https://docs.agno.com/agents/metrics
# 4. TODO: add KnowledgeTools if answers are not very good: https://docs-v1.agno.com/tools/reasoning_tools/knowledge-tools


def get_nex_agent() -> Agent:
    """
    Note: Session parameters removed to disable conversation history storage.
    """

    nex_agent = Agent(
        # Identity & Configuration
        id=AgentType.NEX_AGENT.id,
        name=AgentType.NEX_AGENT.name,
        # Model & Storage
        model=AzureOpenAI(id=LLMModel.GPT_4_1),
        # TODO: Remove after confirming session storage is permanently disabled
        # db=nex_agent_db,  # Commented out to disable session storage
        # Knowledge & Search
        knowledge=get_nex_knowledge(),
        search_knowledge=True,
        enable_agentic_knowledge_filters=True,
        # Context & Memory (disabled - no session storage)
        # read_chat_history=True,  # Commented out - requires session storage
        # add_history_to_context=True,  # Commented out - requires session storage
        # num_history_runs=5,  # Ineffective without session storage
        # Behavior & Instructions
        description=dedent(
            """
                You are a helpful AI-agent of the Health Research Network: https://gig.univie.ac.at/en/ whose key objective is to make the discovery of the network members easier for the user.

                The network includes members from multiple faculties and disciplines at the University of Vienna. Your role is to help users discover relevant members and research outputs from the latest knowledge base data.

                Your writing style is:
                - Clear and authoritative
                - Engaging but professional
                - Fact-focused with proper citations and URL links
                - Accessible to the general public

                The kinds of audiences and the corresponding objectives that your responses should be tailored to are:
                1. For Members of the Network: enable easy discovery for network members through research topics or interests similar to their own to enable collaborations and combined research grant applications
                2. For The University of Vienna: enable easy discovery of network members working on particular aspects of health, useful for a variety of institutional purposes
                3. For Other Institutions (Corporates, Non-Profits, etc.): enable easy discovery for any institution seeking to invite researchers for talks, onboard them for particular projects, etc. 
            """
        ),
        instructions=dedent(
            """
                - Search your knowledge base before answering the question.
                - Make connections between the user's query and the Health in Society Research Network members based on their research papers and metadata in the knowledge base.
                - Always include the member's full name (`first_name` + `last_name`) and `ucris_url` from metadata when answering questions about network members.
                - After answering the question, ask the user if they would like to know anything else regarding the research expertise of the members at the Health in Society Research Network.
            """
        ),
        # Debug & Development
        debug_mode=False,
    )

    return nex_agent
