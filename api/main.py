import asyncio
from agno.os import AgentOS
from dotenv import load_dotenv

# from agents.health_research_network_agent import get_health_research_network_agent
from agents.marhinovirus_agents.control_agent import get_control_marhinovirus_agent
from agents.marhinovirus_agents.simple_language_agent import (
    get_simple_language_marhinovirus_agent,
)
from agents.marhinovirus_agents.simple_catalog_language_agent import (
    get_simple_catalog_language_marhinovirus_agent,
)
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_url,
    get_simple_catalog_url,
)
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.knowledge.chunking.semantic import SemanticChunking

# from knowledge_base.hrn_knowledge_base import get_hrn_knoweldge_data


load_dotenv()

# hrn_agent = get_health_research_network_agent()

# Instantiate the three Marhinovirus agents
control_agent = get_control_marhinovirus_agent()
simple_lg_agent = get_simple_language_marhinovirus_agent()
simple_catalog_lg_agent = get_simple_catalog_language_marhinovirus_agent()

agent_os = AgentOS(
    os_id="agentos-trial",
    agents=[control_agent, simple_lg_agent, simple_catalog_lg_agent],
)
app = agent_os.get_app()

if __name__ == "__main__":
    # Load normal catalog knowledge for control and simple language agents
    asyncio.run(
        control_agent.knowledge.add_content_async(
            get_normal_catalog_url(),
            reader=PDFReader(
                chunking_strategy=SemanticChunking(),
                read_images=True,
            ),
        )
    )
    asyncio.run(
        simple_lg_agent.knowledge.add_content_async(
            get_normal_catalog_url(),
            reader=PDFReader(
                chunking_strategy=SemanticChunking(),
                read_images=True,
            ),
        )
    )

    # Load simple catalog knowledge for simple catalog language agent
    asyncio.run(
        simple_catalog_lg_agent.knowledge.add_content_async(
            get_simple_catalog_url(),
            reader=PDFReader(
                chunking_strategy=SemanticChunking(),
                read_images=True,
            ),
        )
    )

    # asyncio.run(
    #     hrn_agent.knowledge.add_content_async(
    #         get_hrn_knoweldge_data(),
    #         reader=PDFReader(
    #             chunking_strategy=SemanticChunking(),
    #             read_images=True,
    #         ),
    #     )
    # )

    agent_os.serve(app="main:app", reload=True)
