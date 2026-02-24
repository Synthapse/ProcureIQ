"""Call DigitalOcean hosted agent (OpenAI-compatible /api/v1/chat/completions)."""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def query_do_agent(question: str, timeout: float = 60.0) -> str:
    """Send a question to the DO agent (with connected Knowledge Base). Returns reply text or error."""
    if not settings.do_agent_url or not settings.do_agent_access_key:
        return ""

    url = f"{settings.do_agent_url.rstrip('/')}/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.do_agent_access_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "messages": [{"role": "user", "content": question}],
        "stream": False,
    }
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            return (msg.get("content") or "").strip()
        return ""
    except httpx.HTTPStatusError as e:
        logger.warning("DO agent HTTP error %s: %s", e.response.status_code, e.response.text[:200])
        return f"Agent request failed (HTTP {e.response.status_code})."
    except Exception as e:
        logger.exception("DO agent request failed")
        return f"Agent request failed: {e!s}"
