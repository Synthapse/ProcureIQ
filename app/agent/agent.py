from __future__ import annotations

import json
from typing import AsyncGenerator

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.config import settings
from app.agent.tools import TOOLS

SYSTEM_PROMPT = """You are ProcureIQ, an AI-powered procurement intelligence assistant.
You help procurement managers, legal teams, and finance leaders understand vendor risk,
contract exposure, and renewal impact.

You have access to:
- A live Neo4j procurement graph (vendor/contract/obligation relationships)
- A document knowledge base with contracts, policies, and clause libraries (RAG)

Decision rules:
- For questions about specific vendors, contracts, or obligations → use graph tools
- For questions about clause content, policy text, or document details → use knowledge_base_search
- For risk rankings or expiry timelines → combine both if needed

Always use at least one tool before answering. When you have the data, provide:
1. A clear, concise summary
2. Key findings and risks
3. Recommended actions

Be professional, data-driven, and explainable. Cite specific values (risk scores, dates, amounts).
If you cannot find data, say so clearly."""


def build_agent() -> AgentExecutor:
    llm = ChatOpenAI(
        model=settings.do_gradient_model,
        openai_api_key=settings.do_gradient_api_key,
        openai_api_base=settings.do_gradient_base_url,
        temperature=0,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, TOOLS, prompt)
    # max_iterations=6 gives the agent room to call multiple tools (up to 7 available)
    # before generating the final answer without hitting the limit prematurely.
    return AgentExecutor(agent=agent, tools=TOOLS, verbose=True, max_iterations=6)


_agent_executor: AgentExecutor | None = None


def get_agent() -> AgentExecutor:
    global _agent_executor
    if _agent_executor is None:
        _agent_executor = build_agent()
    return _agent_executor


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def stream_agent_response(question: str) -> AsyncGenerator[str, None]:
    """Yield Server-Sent Events for each phase of the agent execution.

    Event shapes emitted (all as ``data: <JSON>\\n\\n``):

    .. code-block:: json

        {"type": "phase", "phase": "thinking",     "message": "Analyzing your question..."}
        {"type": "phase", "phase": "tool_call",    "tool": "<name>", "message": "Retrieving data via <name>..."}
        {"type": "phase", "phase": "tool_result",  "tool": "<name>"}
        {"type": "phase", "phase": "generating",   "message": "Generating final response..."}
        {"type": "done",  "answer": "<text>",      "tool_calls": ["<name>", ...]}
        {"type": "error", "message": "<text>"}
    """
    agent = get_agent()
    tool_calls: list[str] = []

    yield _sse({"type": "phase", "phase": "thinking", "message": "Analyzing your question..."})

    try:
        async for event in agent.astream_events({"input": question}, version="v2"):
            kind = event.get("event")

            if kind == "on_tool_start":
                tool = event.get("name", "unknown")
                if tool not in tool_calls:
                    tool_calls.append(tool)
                yield _sse(
                    {
                        "type": "phase",
                        "phase": "tool_call",
                        "tool": tool,
                        "message": f"Retrieving data via {tool}...",
                    }
                )

            elif kind == "on_tool_end":
                tool = event.get("name", "unknown")
                yield _sse({"type": "phase", "phase": "tool_result", "tool": tool})

            elif kind == "on_chat_model_start":
                yield _sse(
                    {"type": "phase", "phase": "generating", "message": "Generating response..."}
                )

            elif kind == "on_chain_end" and event.get("name") == "AgentExecutor":
                raw = event.get("data", {}).get("output", {})
                answer = raw.get("output", "") if isinstance(raw, dict) else str(raw)
                yield _sse({"type": "done", "answer": answer, "tool_calls": tool_calls})

    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})

