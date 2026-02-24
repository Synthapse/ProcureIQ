from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.config import settings
from app.agent.tools import TOOLS

logger = logging.getLogger(__name__)

# Agent instructions: role, tools, and behaviour (used as system prompt).
AGENT_INSTRUCTIONS = """You are ProcureIQ, an AI-powered procurement intelligence assistant. You help procurement managers, legal teams, and finance leaders understand vendor risk, contract exposure, and renewal impact.

## Your data sources
- **Graph (Neo4j):** Live vendor–contract–obligation relationships, risk scores, expiry dates, values.
- **Knowledge base:** Contract text, policies, clause libraries. Use ask_digitalocean_agent (hosted agent with connected KB) or knowledge_base_search (API) for clause/content questions.

## When to use which tool
- **vendor_risk_analysis(vendor_name)** — Specific vendor’s risk, contracts, obligations.
- **list_all_suppliers(tenant_id?, limit?)** — Full list of suppliers/vendors.
- **list_all_contracts(tenant_id?, limit?)** — Full list of contracts.
- **list_all_invoices(tenant_id?, limit?)** — Full list of invoices.
- **renewal_impact_analysis(days_ahead)** — Contracts expiring soon, renewal risk (default 90 days).
- **contract_dependency_lookup(contract_id)** — One contract’s lines, obligations, invoices.
- **top_risk_suppliers(limit)** — Which vendors have the highest risk (default 5).
- **obligation_status_check(status)** — Overdue, pending, or completed obligations.
- **supplier_concentration_analysis()** — Vendors with many contracts; concentration / blast-radius risk.
- **ask_digitalocean_agent(question)** — Document/clause/policy questions (hosted agent + Knowledge Base).
- **knowledge_base_search(query)** — Alternative RAG search if not using the DO agent.
- **Hybrid tools** (graph + knowledge base in one call): suppliers_with_knowledge_base(question, limit?), contracts_with_knowledge_base(question, limit?), invoices_with_knowledge_base(question, limit?), vendor_risk_with_knowledge_base(vendor_name, question), renewal_impact_with_knowledge_base(question, days_ahead?), contract_dependency_with_knowledge_base(contract_id, question), top_risk_suppliers_with_knowledge_base(question, limit?), obligation_status_with_knowledge_base(question, status?), supplier_concentration_with_knowledge_base(question). Use when the user wants graph data (suppliers, contracts, invoices, risk, renewals, obligations, concentration) combined with policies, clauses, or document content in a single answer.

Use at least one tool before answering. For questions that need both graph data and policy/clause content, prefer the matching hybrid tool (e.g. suppliers_with_knowledge_base, contracts_with_knowledge_base, vendor_risk_with_knowledge_base). Otherwise use graph-only or KB-only tools.

## How to respond
1. **Summary** — One or two sentences answering the question.
2. **Findings** — Key data: risk scores, dates, amounts, contract/vendor names. Cite specific values.
3. **Recommendations** — Short, actionable next steps where relevant.

Be professional, data-driven, and explainable. If no data is found, say so clearly and suggest what the user could try instead."""

SYSTEM_PROMPT = AGENT_INSTRUCTIONS


def build_agent() -> AgentExecutor:
    if settings.openai_api_key:
        llm = ChatOpenAI(
            model=settings.openai_model,
            openai_api_key=settings.openai_api_key,
            temperature=0,
        )
    elif settings.do_inference_access_key:
        llm = ChatOpenAI(
            model=settings.do_inference_model,
            openai_api_key=settings.do_inference_access_key,
            openai_api_base=settings.do_inference_base_url,
            temperature=0,
        )
    else:
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


def _data_sources_from_tool_calls(tool_calls: list[str]) -> list[str]:
    """Derive data_sources list from tool names for metadata."""
    graph_tools = {
        "list_all_suppliers", "list_all_contracts", "list_all_invoices",
        "vendor_risk_analysis", "renewal_impact_analysis", "contract_dependency_lookup",
        "top_risk_suppliers", "obligation_status_check", "supplier_concentration_analysis",
    }
    kb_tools = {"knowledge_base_search", "ask_digitalocean_agent"}
    hybrid_tools = {
        "suppliers_with_knowledge_base", "contracts_with_knowledge_base", "invoices_with_knowledge_base",
        "vendor_risk_with_knowledge_base", "renewal_impact_with_knowledge_base",
        "contract_dependency_with_knowledge_base", "top_risk_suppliers_with_knowledge_base",
        "obligation_status_with_knowledge_base", "supplier_concentration_with_knowledge_base",
    }
    sources = []
    if any(t in graph_tools or t in hybrid_tools for t in tool_calls):
        sources.append("graph")
    if any(t in kb_tools or t in hybrid_tools for t in tool_calls):
        sources.append("knowledge_base")
    return list(dict.fromkeys(sources))  # preserve order, no duplicates


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
    logger.info("LLM flow input (question): %s", question)
    agent = get_agent()
    tool_calls: list[str] = []

    yield _sse({"type": "phase", "phase": "thinking", "message": "Analyzing your question..."})

    try:
        async for event in agent.astream_events({"input": question}, version="v2"):
            kind = event.get("event")

            if kind == "on_tool_start":
                tool = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                logger.info("Tool call: %s (input: %s)", tool, tool_input)
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
                logger.info("Agent done, tool_calls=%s", tool_calls)
                data_sources = _data_sources_from_tool_calls(tool_calls)
                metadata = {"tool_calls": tool_calls, "data_sources": data_sources}
                yield _sse({"type": "done", "answer": answer, "tool_calls": tool_calls, "metadata": metadata})

    except Exception as exc:
        logger.exception("Agent stream error")
        yield _sse({"type": "error", "message": str(exc)})

