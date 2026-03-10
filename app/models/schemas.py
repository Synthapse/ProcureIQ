from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    user_id: str
    conversation_id: Optional[str] = None  # omit for new thread; send to continue same conversation
    tenant_id: Optional[str] = None


class StreamEvent(BaseModel):
    """A single event in the SSE stream returned by ``POST /api/v1/chat/``.

    The frontend should parse each ``data: <JSON>`` line from the stream.

    Phase sequence (happy path)::

        thinking → (tool_call → tool_result)* → generating → done

    Possible ``type`` values:

    * ``"phase"`` – backend is in a specific processing phase.
      ``phase`` is one of ``thinking | tool_call | tool_result | generating``.
      ``tool`` is set for ``tool_call`` / ``tool_result``.
    * ``"done"`` – final answer is ready.
      ``answer`` contains the full response text.
      ``tool_calls`` lists the names of all tools that were invoked.
      ``conversation_id`` is the conversation id (send on next request to continue thread).
      ``metadata`` includes tool_calls and data_sources (e.g. ["graph", "knowledge_base"]).
    * ``"error"`` – an unrecoverable error occurred; ``message`` has details.
    """

    type: Literal["phase", "done", "error"]
    phase: Optional[Literal["thinking", "tool_call", "tool_result", "generating"]] = None
    tool: Optional[str] = None
    message: Optional[str] = None
    answer: Optional[str] = None
    tool_calls: Optional[list[str]] = None
    conversation_id: Optional[str] = None
    metadata: Optional[dict] = None  # e.g. {"tool_calls": [...], "data_sources": ["graph", "knowledge_base"]}

