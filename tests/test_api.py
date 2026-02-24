"""Tests for ProcureIQ API endpoints."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ProcureIQ API"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _mock_stream(*events: dict):
    """Async generator that yields pre-built SSE event strings."""
    for ev in events:
        yield f"data: {json.dumps(ev)}\n\n"


def _parse_sse(raw: str) -> list[dict]:
    """Parse raw SSE text into a list of event dicts."""
    events = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            events.append(json.loads(line[5:].strip()))
    return events


# ---------------------------------------------------------------------------
# Chat SSE endpoint
# ---------------------------------------------------------------------------


@patch("app.routers.chat.stream_agent_response")
def test_chat_streams_done_event(mock_stream):
    """Endpoint must stream a 'done' event containing the final answer."""
    mock_stream.return_value = _mock_stream(
        {"type": "phase", "phase": "thinking", "message": "Analyzing..."},
        {"type": "phase", "phase": "tool_call", "tool": "top_risk_suppliers", "message": "Retrieving data via top_risk_suppliers..."},
        {"type": "phase", "phase": "tool_result", "tool": "top_risk_suppliers"},
        {"type": "phase", "phase": "generating", "message": "Generating response..."},
        {"type": "done", "answer": "SecureNet Inc is the highest risk vendor.", "tool_calls": ["top_risk_suppliers"]},
    )

    with client.stream("POST", "/api/v1/chat/", json={"question": "Which vendor has highest risk?"}) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        raw = resp.read().decode()

    events = _parse_sse(raw)
    types = [e["type"] for e in events]
    assert "phase" in types
    assert "done" in types

    done = next(e for e in events if e["type"] == "done")
    assert done["answer"] == "SecureNet Inc is the highest risk vendor."
    assert done["tool_calls"] == ["top_risk_suppliers"]


@patch("app.routers.chat.stream_agent_response")
def test_chat_streams_phase_sequence(mock_stream):
    """Phase events must appear in the correct order before 'done'."""
    mock_stream.return_value = _mock_stream(
        {"type": "phase", "phase": "thinking", "message": "Analyzing..."},
        {"type": "phase", "phase": "generating", "message": "Generating response..."},
        {"type": "done", "answer": "No tools needed.", "tool_calls": []},
    )

    with client.stream("POST", "/api/v1/chat/", json={"question": "Hello"}) as resp:
        raw = resp.read().decode()

    events = _parse_sse(raw)
    phases = [e.get("phase") for e in events if e["type"] == "phase"]
    assert phases[0] == "thinking"
    assert "generating" in phases


@patch("app.routers.chat.stream_agent_response")
def test_chat_streams_error_event(mock_stream):
    """If the agent raises, an error event must be returned (not an HTTP 500)."""
    mock_stream.return_value = _mock_stream(
        {"type": "phase", "phase": "thinking", "message": "Analyzing..."},
        {"type": "error", "message": "Neo4j connection refused"},
    )

    with client.stream("POST", "/api/v1/chat/", json={"question": "Any question"}) as resp:
        assert resp.status_code == 200
        raw = resp.read().decode()

    events = _parse_sse(raw)
    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert "Neo4j" in error_events[0]["message"]


@patch("app.routers.chat.stream_agent_response")
def test_chat_sse_headers(mock_stream):
    """Response must carry correct SSE headers for browser streaming."""
    mock_stream.return_value = _mock_stream(
        {"type": "done", "answer": "ok", "tool_calls": []}
    )

    with client.stream("POST", "/api/v1/chat/", json={"question": "test"}) as resp:
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers.get("cache-control") == "no-cache"

