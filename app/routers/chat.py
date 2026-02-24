import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest, StreamEvent
from app.agent.agent import stream_agent_response
from app.graph.queries import save_conversation_turn

router = APIRouter()
logger = logging.getLogger(__name__)


async def _stream_with_save(user_id: str, question: str, conversation_id: str | None):
    """Stream agent response, persist the turn to Neo4j when done, and inject conversation_id into done event."""
    async for chunk in stream_agent_response(question):
        if chunk.startswith("data: "):
            try:
                payload = json.loads(chunk[6:].strip())
                if payload.get("type") == "done":
                    conv_id = save_conversation_turn(
                        user_id,
                        question,
                        payload.get("answer", ""),
                        payload.get("tool_calls"),
                        conversation_id,
                    )
                    payload = {**payload, "conversation_id": conv_id}
                    chunk = f"data: {json.dumps(payload)}\n\n"
                    logger.info("Saved conversation turn for user_id=%s conversation_id=%s", user_id, conv_id)
            except (json.JSONDecodeError, Exception):
                pass
        yield chunk


@router.post(
    "/",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": (
                "Server-Sent Events stream of agent progress and final answer. "
                "Each line is `data: <JSON>` followed by a blank line. "
                "See `StreamEvent` schema for all possible event shapes."
            ),
            "content": {
                "text/event-stream": {
                    "schema": StreamEvent.model_json_schema(),
                    "example": (
                        'data: {"type":"phase","phase":"thinking","message":"Analyzing..."}\n\n'
                        'data: {"type":"phase","phase":"tool_call","tool":"vendor_risk_analysis",'
                        '"message":"Retrieving data via vendor_risk_analysis..."}\n\n'
                        'data: {"type":"phase","phase":"tool_result","tool":"vendor_risk_analysis"}\n\n'
                        'data: {"type":"phase","phase":"generating","message":"Generating response..."}\n\n'
                        'data: {"type":"done","answer":"SecureNet Inc carries the highest risk...","tool_calls":["vendor_risk_analysis"]}\n\n'
                    ),
                }
            },
        }
    },
    summary="Procurement AI chat (SSE)",
    description=(
        "Send a natural language procurement question. "
        "The response is a Server-Sent Events stream that emits phase updates so the "
        "frontend can render progress in real time. "
        "Consume with `EventSource` or `fetch` + `ReadableStream`."
    ),
)
async def chat(request: ChatRequest) -> StreamingResponse:
    logger.info("Chat request (user_id=%s, question): %s", request.user_id, request.question)
    return StreamingResponse(
        _stream_with_save(request.user_id, request.question, request.conversation_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

