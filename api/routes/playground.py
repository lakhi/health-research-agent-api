from agno.playground import Playground

from agents.marhonivirus_agent import get_marhinovirus_agent
######################################################

## Routes for the Playground Interface
######################################################

# Get Agents to serve in the playground

marhonivirus_agent = get_marhinovirus_agent(debug_mode=True)

# Create a playground instance
playground = Playground(agents=[marhonivirus_agent])

# Get the router for the playground
playground_router = playground.get_async_router()
