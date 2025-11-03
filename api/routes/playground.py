from agno.playground import Playground

from agents.health_research_network_agent import get_health_research_network_agent

######################################################

## Routes for the Playground Interface
######################################################

# Get Agents to serve in the playground

hrn_agent = get_health_research_network_agent()

# Create a playground instance
playground = Playground(agents=[hrn_agent])

# Get the router for the playground
playground_router = playground.get_async_router()
