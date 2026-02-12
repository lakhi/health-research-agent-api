from logging import getLogger
from typing import AsyncGenerator, List, Optional

from agno.agent import Agent
from agno.knowledge import Knowledge
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse, JSONResponse, Response
from pydantic import BaseModel

from agents.llm_models import LLMModel
from agents.selector import AgentType, get_agent
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_knowledge,
    get_simple_catalog_knowledge,
)
from services.budget_service import check_budget_available, record_usage

logger = getLogger(__name__)

######################################################
## Routes for the Agent Interface
######################################################

agents_router = APIRouter(prefix="/agents", tags=["Agents"])


async def chat_response_streamer(
    agent: Agent, message: str, is_healthsoc: bool = False
) -> AsyncGenerator:
    """
    Stream agent responses chunk by chunk.

    Args:
        agent: The agent instance to interact with
        message: User message to process
        is_healthsoc: Whether this is the healthsoc agent (for metrics recording)

    Yields:
        Text chunks from the agent response
    """
    run_response = await agent.arun(message, stream=True)

    input_tokens = 0
    output_tokens = 0

    async for chunk in run_response:
        # chunk.content only contains the text response from the Agent.
        # For advanced use cases, we should yield the entire chunk
        # that contains the tool calls and intermediate steps.
        yield chunk.content

        # Capture metrics from the final chunk if available
        if hasattr(chunk, "metrics") and chunk.metrics is not None:
            if hasattr(chunk.metrics, "input_tokens") and chunk.metrics.input_tokens:
                input_tokens = chunk.metrics.input_tokens
            if hasattr(chunk.metrics, "output_tokens") and chunk.metrics.output_tokens:
                output_tokens = chunk.metrics.output_tokens

    # Record usage after stream completes (for healthsoc agent only)
    if is_healthsoc and (input_tokens > 0 or output_tokens > 0):
        try:
            record_usage(input_tokens=input_tokens, output_tokens=output_tokens)
        except Exception as e:
            logger.error(f"Failed to record streaming usage metrics: {e}")


class RunRequest(BaseModel):
    """Request model for an running an agent"""

    message: str
    stream: bool = True
    model: LLMModel = LLMModel.GPT_4O
    user_id: Optional[str] = None
    session_id: Optional[str] = None


@agents_router.post("/{agent_id}/runs", status_code=status.HTTP_200_OK)
async def create_agent_run(agent_id: AgentType, body: RunRequest):
    """
    Sends a message to a specific agent and returns the response.

    Args:
        agent_id: The ID of the agent to interact with
        body: Request parameters including the message

    Returns:
        Either a streaming response or the complete agent response

    Raises:
        HTTPException 429: If daily budget is exceeded (healthsoc agent only)
        HTTPException 404: If agent is not found
    """
    print("=" * 80)
    print(f"CREATE_AGENT_RUN CALLED: agent_id={agent_id}, type={type(agent_id)}")
    print("=" * 80)
    logger.info(f"CREATE_AGENT_RUN: agent_id={agent_id}")
    
    logger.debug(f"RunRequest: {body}")
    

    # Check if this is the healthsoc agent (budget enforcement applies)
    is_healthsoc = agent_id == AgentType.HEALTHSOC_CHATBOT
    logger.info(f"Agent ID: {agent_id}, is_healthsoc: {is_healthsoc}")
    print(f"Agent ID: {agent_id}, is_healthsoc: {is_healthsoc}")

    # Budget pre-check for healthsoc agent
    if is_healthsoc:
        available, remaining_eur, reset_time = check_budget_available()

        if not available:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "daily_budget_exceeded",
                    "reset_time_utc": reset_time.isoformat(),
                    "remaining_eur": remaining_eur,
                },
            )

    try:
        agent: Agent = get_agent(
            model_id=body.model.value,
            agent_id=agent_id,
            user_id=body.user_id,
            session_id=body.session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if body.stream:
        # For streaming, include remaining budget in headers
        headers = {}
        if is_healthsoc:
            # Re-check to get current remaining (pre-run value)
            _, remaining_eur, _ = check_budget_available()
            headers["X-Budget-Remaining-EUR"] = f"{remaining_eur:.4f}"

        return StreamingResponse(
            chat_response_streamer(agent, body.message, is_healthsoc=is_healthsoc),
            media_type="text/event-stream",
            headers=headers,
        )
    else:
        response = await agent.arun(body.message, stream=False)

        # Record usage for healthsoc agent
        if is_healthsoc:
            input_tokens = 0
            output_tokens = 0

            if hasattr(response, "metrics") and response.metrics is not None:
                if (
                    hasattr(response.metrics, "input_tokens")
                    and response.metrics.input_tokens
                ):
                    input_tokens = response.metrics.input_tokens
                if (
                    hasattr(response.metrics, "output_tokens")
                    and response.metrics.output_tokens
                ):
                    output_tokens = response.metrics.output_tokens

            if input_tokens > 0 or output_tokens > 0:
                try:
                    record_usage(input_tokens=input_tokens, output_tokens=output_tokens)
                except Exception as e:
                    logger.error(f"Failed to record usage metrics: {e}")

            # Get updated remaining budget after recording
            _, remaining_eur, _ = check_budget_available()

            # Return response with budget header
            return Response(
                content=response.content,
                media_type="text/plain",
                headers={"X-Budget-Remaining-EUR": f"{remaining_eur:.4f}"},
            )

        # In this case, the response.content only contains the text response from the Agent.
        # For advanced use cases, we should yield the entire response
        # that contains the tool calls and intermediate steps.
        return response.content


@agents_router.post("/{agent_id}/knowledge/load", status_code=status.HTTP_200_OK)
async def load_agent_knowledge(agent_id: AgentType):
    """
    Loads the knowledge base for a specific agent.

    Args:
        agent_id: The ID of the agent to load knowledge for.

    Returns:
        A success message if the knowledge base is loaded.
    """
    agent_knowledge: Optional[Knowledge] = None

    if agent_id == AgentType.CONTROL_MARHINOVIRUS:
        agent_knowledge = get_normal_catalog_knowledge()
    elif agent_id == AgentType.SIMPLE_LANGUAGE_MARHINOVIRUS:
        agent_knowledge = get_normal_catalog_knowledge()
    elif agent_id == AgentType.SIMPLE_CATALOG_LANGUAGE_MARHINOVIRUS:
        agent_knowledge = get_simple_catalog_knowledge()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent {agent_id} does not have a knowledge base.",
        )

    try:
        await agent_knowledge.aload(upsert=True)
    except Exception as e:
        logger.error(f"Error loading knowledge base for {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load knowledge base for {agent_id}.",
        )

    return {"message": f"Knowledge base for {agent_id} loaded successfully."}
