import json
from logging import getLogger
from typing import AsyncGenerator, List, Optional

from agno.agent import Agent
from agno.knowledge import Knowledge
from agno.os.utils import format_sse_event
from fastapi import APIRouter, Body, Form, HTTPException, status
from fastapi.responses import StreamingResponse, JSONResponse
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
    run_response = agent.arun(message, stream=True, stream_events=True)

    input_tokens = 0
    output_tokens = 0

    async for chunk in run_response:
        try:
            yield format_sse_event(chunk)
        except Exception:
            chunk_content = getattr(chunk, "content", str(chunk))
            yield f"event: message\ndata: {json.dumps({'content': chunk_content})}\n\n"

        # Capture metrics from the final chunk if available
        chunk_metrics = getattr(chunk, "metrics", None)
        if chunk_metrics is not None:
            if hasattr(chunk_metrics, "input_tokens") and chunk_metrics.input_tokens:
                input_tokens = chunk_metrics.input_tokens
            if hasattr(chunk_metrics, "output_tokens") and chunk_metrics.output_tokens:
                output_tokens = chunk_metrics.output_tokens

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
async def create_agent_run(
    agent_id: str,
    body: Optional[RunRequest] = Body(default=None),
    message: Optional[str] = Form(default=None),
    stream: Optional[bool] = Form(default=None),
    model: Optional[LLMModel] = Form(default=None),
    user_id: Optional[str] = Form(default=None),
    session_id: Optional[str] = Form(default=None),
):
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
    run_request = body
    if run_request is None and message is not None:
        run_request = RunRequest(
            message=message,
            stream=True if stream is None else stream,
            model=LLMModel.GPT_4O if model is None else model,
            user_id=user_id,
            session_id=session_id,
        )

    if run_request is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Request body must be valid JSON or multipart form-data with a message field.",
        )

    logger.info(f"CREATE_AGENT_RUN: agent_id={agent_id}")
    logger.debug(f"RunRequest: {run_request}")

    # Check if this is the healthsoc agent (budget enforcement applies)
    is_healthsoc = agent_id == AgentType.HEALTHSOC_CHATBOT.id
    logger.info(f"Agent ID: {agent_id}, is_healthsoc: {is_healthsoc}")

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
            model_id=run_request.model.value,
            agent_id=agent_id,
            user_id=run_request.user_id,
            session_id=run_request.session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if run_request.stream:
        # For streaming, include remaining budget in headers
        headers = {}
        if is_healthsoc:
            # Re-check to get current remaining (pre-run value)
            _, remaining_eur, _ = check_budget_available()
            headers["X-Budget-Remaining-EUR"] = f"{remaining_eur:.4f}"

        return StreamingResponse(
            chat_response_streamer(
                agent, run_request.message, is_healthsoc=is_healthsoc
            ),
            media_type="text/event-stream",
            headers=headers,
        )
    else:
        response = await agent.arun(run_request.message, stream=False)

        response_payload = response.to_dict() if hasattr(response, "to_dict") else None
        if not isinstance(response_payload, dict):
            response_payload = {
                "content": getattr(response, "content", ""),
            }

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
            return JSONResponse(
                content=response_payload,
                headers={"X-Budget-Remaining-EUR": f"{remaining_eur:.4f}"},
            )

        # In this case, the response.content only contains the text response from the Agent.
        # For advanced use cases, we should yield the entire response
        # that contains the tool calls and intermediate steps.
        return response_payload


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
