import os
import pytest
import scenario

from agents.marhinovirus_agents.simple_catalog_language_agent import (
    get_simple_catalog_language_marhinovirus_agent,
)

# Azure Scenario configuration (shared across tests to avoid duplication)
AZURE_SCENARIO_MODEL = os.getenv("AZURE_SCENARIO_MODEL", "azure/gpt-4o-marhinovirus")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")


@pytest.mark.agent_test
@pytest.mark.asyncio
async def test_consequences_of_infection_numbers() -> None:
    """Scenario: Participant asks about consequences of catching the virus.
    Evaluation: Agent must state the numeric outcomes clearly: 60% -> 40 points lost,
    30% -> 60 points lost, 10% -> 80 points lost.
    """

    class MarhinoAgentAdapter(scenario.AgentAdapter):
        def __init__(self) -> None:
            self.agent = get_simple_catalog_language_marhinovirus_agent()

        async def call(self, input: scenario.AgentInput) -> scenario.AgentReturnTypes:
            result = self.agent.run(
                message=input.last_new_user_message_str(),
                session_id=input.thread_id,
            )
            return result.content

    # Create a user simulator and judge that use the shared Azure config
    user_sim = scenario.UserSimulatorAgent(
        model=AZURE_SCENARIO_MODEL,
        api_base=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
    )

    judge = scenario.JudgeAgent(
        criteria=[
            "Agent should explicitly state: '60% of cases - 40 points lost'",
            "Agent should explicitly state: '30% of cases - 60 points lost'",
            "Agent should explicitly state: '10% of cases - 80 points lost'",
            "Agent numeric statements must be clear and refer to percentages of all infected participants, not nested percentages",
        ],
        model=AZURE_SCENARIO_MODEL,
        api_base=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        temperature=0.0,
    )

    result = await scenario.run(
        name="Consequences of Infection - Numbers",
        description="Participant asks about the consequences of catching the virus",
        agents=[
            MarhinoAgentAdapter(),
            user_sim,
            judge,
        ],
    )

    assert result.success


@pytest.mark.agent_test
@pytest.mark.asyncio
async def test_consequences_of_vaccination_numbers() -> None:
    """Scenario: Participant asks about consequences of getting vaccinated.
    Evaluation: Agent must state 40% experience side effects, and the breakdown
    of fitness point losses as percentages of ALL vaccinated participants: 24% lose 15 points,
    12% lose 20 points, 4% lose 50 points. Agent must not imply these are percentages
    of the 40% subgroup (i.e., avoid phrasing like '24% of those who have side effects').
    """

    class MarhinoAgentAdapter(scenario.AgentAdapter):
        def __init__(self) -> None:
            self.agent = get_simple_catalog_language_marhinovirus_agent()

        async def call(self, input: scenario.AgentInput) -> scenario.AgentReturnTypes:
            result = self.agent.run(
                message=input.last_new_user_message_str(),
                session_id=input.thread_id,
            )
            return result.content

    # Create user simulator + judge for vaccination scenario using Azure OpenAI gpt-4o
    user_sim_vax = scenario.UserSimulatorAgent(
        model=AZURE_SCENARIO_MODEL,
        api_base=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
    )

    judge_vax = scenario.JudgeAgent(
        criteria=[
            "Agent should explicitly state: '40% of vaccinated people experience side effects'",
            "Agent should explicitly state: '24% of all vaccinated people lose 15 points'",
            "Agent should explicitly state: '12% of all vaccinated people lose 20 points'",
            "Agent should explicitly state: '4% of all vaccinated people lose 50 points'",
            "Agent must not present the 24/12/4 numbers as percentages of the 40% subgroup; they must be clearly framed as percentages of ALL vaccinated participants",
        ],
        model=AZURE_SCENARIO_MODEL,
        api_base=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        temperature=0.0,
    )

    result = await scenario.run(
        name="Consequences of Vaccination - Numbers",
        description="Participant asks about the consequences of getting vaccinated",
        agents=[
            MarhinoAgentAdapter(),
            user_sim_vax,
            judge_vax,
        ],
    )

    assert result.success
