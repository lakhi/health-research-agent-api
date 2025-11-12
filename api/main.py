from agno.os import AgentOS
from dotenv import load_dotenv
from agents.health_research_network_agent import get_health_research_network_agent
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.knowledge.chunking.semantic import SemanticChunking

from knowledge_base.hrn_knowledge_base import get_hrn_knoweldge_data


load_dotenv()

hrn_agent = get_health_research_network_agent()

agent_os = AgentOS(
    os_id="agentos-trial",
    agents=[hrn_agent],
)
app = agent_os.get_app()

if __name__ == "__main__":
    hrn_agent.knowledge.add_content(
        get_hrn_knoweldge_data(),
        reader=PDFReader(
            chunking_strategy=SemanticChunking(),
            read_images=True,
        ),
    )

    agent_os.serve(app="main:app", reload=True)
