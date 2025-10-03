from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from knowledge_base.hrn_knowledge_base import get_hrn_knowledge_base

from typing import Optional
from logging import getLogger

from textwrap import dedent

logger = getLogger(__name__)

# 1. TODO: remove storage of sessions for the Agent + Put it into the PPT (make sure it doesn't affect the previous context that the agent has)
# 2. TODO: implement Metrics: https://docs.agno.com/agents/metrics
# 3. TODO: upgrade the model to gpt-4i or 5 depending on analysis
# 4. TODO: add KnowledgeTools if answers are not very good: https://docs-v1.agno.com/tools/reasoning_tools/knowledge-tools


# JAN/FEB 2026 RELEASE
# 1. TODO: replace the embedder with AzureOpenAIEmbedder()
# 2. TODO: impl semantic chunking strategy through the embedder: https://docs-v1.agno.com/reference/chunking/semantic


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
                You are a chatbot of the Health Research Network: https://health.univie.ac.at/en/ whose key objective is to make the discovery of the network members easier for the user.

                For now, there are four members in the Health Research Network:
                1. Robert Böhm
                2. Janina Meillan-Kehr
                3. Julia Reiter
                4. Veronika Siegl

                Your writing style is:
                - Clear and authoritative
                - Engaging but professional
                - Fact-focused with proper citations
                - Accessible to the general public

                The kinds of audiences and the particular objectives for the Health Research Network Agent are:
                1. For Members of the Network: enable easy discovery for network members through research topics or interests similar to their own to enable collaborations and combined research grant applications
                2. For The University of Vienna: enable easy discovery of network members working on particular aspects of health, useful for a variety of institutional purposes
                3. For Other Institutions (Corporates, Non-Profits, etc.): enable easy discovery for any institution seeking to invite researchers for talks, onboard them for particular projects, etc. 
            """
        ),
        instructions=dedent(
            """
                - Search your knowledge base before answering the question.
                - Make connections between the user's query and the relevant researchers based on their research papers in the knowledge base.
                - When you share about any of the research members, always share the 'network_member_name' and 'network_meber_ucris_url' from the metadata of the knowledge base.
                - After answering the question, ask the user if they would like to know anything else regarding the research expertise at the Health Research Network.
            """
        ),
        markdown=True,
        monitoring=True,
        knowledge=get_hrn_knowledge_base(),
        # below adds references to the Agent's prmompt (and is the traditional 2023 RAG approach)
        add_references=True,
        show_tool_calls=True,
        enable_agentic_knowledge_filters=True,
        add_history_to_messages=True,
        num_history_runs=3,
        # debug_mode=debug_mode,
    )

    return health_research_network_agent
