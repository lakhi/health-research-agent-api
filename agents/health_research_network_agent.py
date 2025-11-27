from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from knowledge_base.hrn_knowledge_base import get_hrn_knowledge
from agents.llm_models import LLMModel

from typing import Optional
from logging import getLogger

from textwrap import dedent

logger = getLogger(__name__)

# 0. TODO: new branch for Agno 2.0 migration (github actions workflow should not run on this branch)
# 1. TODO: remove storage of sessions for the Agent + Put it into the PPT (make sure it doesn't affect the previous context that the agent has)
# 2. TODO: implement Metrics: https://docs.agno.com/agents/metrics
# 3. TODO: upgrade the model to gpt-4i or 5 depending on analysis
# 4. TODO: add KnowledgeTools if answers are not very good: https://docs-v1.agno.com/tools/reasoning_tools/knowledge-tools


# JAN/FEB 2026 RELEASE
# 0. TODO: implement application-level monitoring that checks costs via Azure Cost Management   API and stops services immediately when threshold is reached (ref chat)
# 1. TODO: replace the embedder with AzureOpenAIEmbedder()
# 2. TODO: impl semantic chunking strategy through the embedder: https://docs-v1.agno.com/reference/chunking/semantic
# 3. TODO: impl /ready endpoint and add to the readiness probe in health.py the Azure container app


def get_health_research_network_agent(
    model_id: str = LLMModel.GPT_4O,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
) -> Agent:

    health_research_network_agent = Agent(
        id="hrn_agent",
        name="Health Research Network Agent",
        model=AzureOpenAI(id=model_id),
        description=dedent(
            """
                You are a helpful AI-agent of the Health Research Network: https://health.univie.ac.at/en/ whose key objective is to make the discovery of the network members easier for the user.

                For now, there are four members in the Health Research Network:
                1. Robert Böhm
                2. Janina Meillan-Kehr
                3. Julia Reiter
                4. Veronika Siegl

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
                - Make connections between the user's query and the Health Research Network members based on their research papers and metadata in the knowledge base.
                - Always include the 'network_member_name' and 'network_meber_ucris_url' from the metadata on questions about the network or it's members.
                - After answering the question, ask the user if they would like to know anything else regarding the research expertise of the members at the Health Research Network.
            """
        ),
        markdown=True,
        knowledge=get_hrn_knowledge(),
        add_knowledge_to_context=True,
        read_chat_history=True,
        enable_agentic_knowledge_filters=True,
        add_history_to_context=True,
        num_history_runs=3,
    )

    return health_research_network_agent
