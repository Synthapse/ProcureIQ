from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest, StreamEvent
from app.agent.agent import stream_agent_response

router = APIRouter()


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
    return StreamingResponse(
        stream_agent_response(request.question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

