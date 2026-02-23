from fastapi import APIRouter, HTTPException
from app.models.schemas import ChatRequest, ChatResponse
from app.agent.agent import get_agent

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a natural language procurement question to the AI agent."""
    try:
        agent = get_agent()
        result = agent.invoke({"input": request.question})
        output = result.get("output", "")
        intermediate = result.get("intermediate_steps", [])
        tool_calls = [str(step[0].tool) for step in intermediate if step]
        return ChatResponse(answer=output, tool_calls=tool_calls)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
