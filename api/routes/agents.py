import json
import time
from logging import getLogger
from typing import AsyncGenerator, Optional

from agno.agent import Agent
from agno.knowledge import Knowledge
from agno.os.utils import format_sse_event
from fastapi import APIRouter, Body, Form, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from agents.llm_models import LLMModel
from agents.selector import AgentType, get_agent
from api.settings import api_settings
from knowledge_base.marhinovirus_knowledge_base import (
    get_normal_catalog_knowledge,
    get_simple_catalog_knowledge,
)
from services.budget_service import check_budget_available, record_usage
from services.metrics_service import record_agent_metrics

logger = getLogger(__name__)

######################################################
## Routes for the Agent Interface
######################################################

agents_router = APIRouter(prefix="/agents", tags=["Agents"])


async def chat_response_streamer(
    agent: Agent, message: str, has_budget: bool = False, session_id: Optional[str] = None
) -> AsyncGenerator:
    """
    Stream agent responses chunk by chunk.

    Args:
        agent: The agent instance to interact with
        message: User message to process
        has_budget: Whether this deployment enforces budget (for usage recording)
        session_id: Anonymous session identifier for metrics tracking

    Yields:
        Text chunks from the agent response
    """
    run_response = agent.arun(message, stream=True, stream_events=True)

    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    duration_seconds: Optional[float] = None
    time_to_first_token: Optional[float] = None
    start_time = time.monotonic()

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
            if hasattr(chunk_metrics, "total_tokens") and chunk_metrics.total_tokens:
                total_tokens = chunk_metrics.total_tokens
            if hasattr(chunk_metrics, "duration") and chunk_metrics.duration:
                duration_seconds = chunk_metrics.duration
            if hasattr(chunk_metrics, "time_to_first_token") and chunk_metrics.time_to_first_token:
                time_to_first_token = chunk_metrics.time_to_first_token

    # Fallback: use wall-clock duration if agno didn't report it
    if duration_seconds is None:
        duration_seconds = time.monotonic() - start_time

    # Record budget usage after stream completes
    if has_budget and (input_tokens > 0 or output_tokens > 0):
        try:
            record_usage(input_tokens=input_tokens, output_tokens=output_tokens)
        except Exception as e:
            logger.error(f"Failed to record streaming usage metrics: {e}")

    # Record anonymous usage metrics
    if has_budget:
        record_agent_metrics(
            session_id=session_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_seconds=duration_seconds,
            time_to_first_token=time_to_first_token,
        )


class RunRequest(BaseModel):
    """Request model for an running an agent"""

    # TODO: make the change at the FE to remove sending model_id and user_id
    message: str
    stream: bool = True
    model: Optional[LLMModel] = None
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
        HTTPException 429: If daily budget is exceeded (nex agent only)
        HTTPException 404: If agent is not found
    """
    run_request = body
    if run_request is None and message is not None:
        # TODO: make the change at the FE to remove sending model_id and user_id
        run_request = RunRequest(
            message=message,
            stream=True if stream is None else stream,
            model=None,
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

    # Check if this deployment enforces budget (budget env vars are configured)
    has_budget = api_settings.daily_budget_eur is not None
    logger.info(f"Agent ID: {agent_id}, has_budget: {has_budget}")

    # Budget pre-check
    if has_budget:
        available, _, reset_time = check_budget_available()

        if not available:
            record_agent_metrics(
                session_id=run_request.session_id,
                response_status="budget_exceeded",
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "daily_budget_exceeded",
                    "reset_time_utc": reset_time.isoformat(),
                    "daily_budget_eur": api_settings.daily_budget_eur,
                },
            )

    try:
        agent: Agent = get_agent(
            # TODO: make the change at the FE to remove sending model_id and user_id
            model_id=None,  # Ignored since model is set at agent level, not per-run.
            agent_id=agent_id,
            user_id=run_request.user_id,
            session_id=run_request.session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if run_request.stream:
        # For streaming, include remaining budget in headers
        headers = {}
        if has_budget:
            # Re-check to get current remaining (pre-run value)
            _, remaining_eur, _ = check_budget_available()
            headers["X-Budget-Remaining-EUR"] = f"{remaining_eur:.4f}"

        return StreamingResponse(
            chat_response_streamer(
                agent, run_request.message, has_budget=has_budget, session_id=run_request.session_id
            ),
            media_type="text/event-stream",
            headers=headers,
        )
    else:
        start_time = time.monotonic()
        response = await agent.arun(run_request.message, stream=False)
        fallback_duration = time.monotonic() - start_time

        response_payload = response.to_dict() if hasattr(response, "to_dict") else None
        if not isinstance(response_payload, dict):
            response_payload = {
                "content": getattr(response, "content", ""),
            }

        # Record usage for budgeted agents
        if has_budget:
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0
            duration_seconds: Optional[float] = None
            time_to_first_token: Optional[float] = None

            if hasattr(response, "metrics") and response.metrics is not None:
                if hasattr(response.metrics, "input_tokens") and response.metrics.input_tokens:
                    input_tokens = response.metrics.input_tokens
                if hasattr(response.metrics, "output_tokens") and response.metrics.output_tokens:
                    output_tokens = response.metrics.output_tokens
                if hasattr(response.metrics, "total_tokens") and response.metrics.total_tokens:
                    total_tokens = response.metrics.total_tokens
                if hasattr(response.metrics, "duration") and response.metrics.duration:
                    duration_seconds = response.metrics.duration
                if hasattr(response.metrics, "time_to_first_token") and response.metrics.time_to_first_token:
                    time_to_first_token = response.metrics.time_to_first_token

            if duration_seconds is None:
                duration_seconds = fallback_duration

            if input_tokens > 0 or output_tokens > 0:
                try:
                    record_usage(input_tokens=input_tokens, output_tokens=output_tokens)
                except Exception as e:
                    logger.error(f"Failed to record usage metrics: {e}")

            record_agent_metrics(
                session_id=run_request.session_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                duration_seconds=duration_seconds,
                time_to_first_token=time_to_first_token,
            )

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
