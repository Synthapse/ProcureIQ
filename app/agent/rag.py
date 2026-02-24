"""DigitalOcean Gradient Knowledge Base client for RAG queries.

Docs: https://docs.digitalocean.com/products/gen-ai-platform/how-to/knowledge-bases/
API:  POST https://api.digitalocean.com/v2/gen-ai/knowledge_bases/{uuid}/query
"""
from __future__ import annotations

import httpx

from app.config import settings

_DO_KB_API = "https://api.digitalocean.com/v2/gen-ai/knowledge_bases"


def query_knowledge_base(query: str, top_k: int = 5) -> list[dict]:
    """Query the DigitalOcean Gradient Knowledge Base and return relevant text chunks.

    Args:
        query:  Natural language search query.
        top_k:  Maximum number of chunks to return.

    Returns:
        List of dicts with keys: ``text``, ``source_url``, ``score``.
        Returns an empty list if the KB is not configured or the call fails.
    """
    if not settings.do_kb_uuid or not settings.do_api_token:
        return []

    url = f"{_DO_KB_API}/{settings.do_kb_uuid}/query"
    headers = {
        "Authorization": f"Bearer {settings.do_api_token}",
        "Content-Type": "application/json",
    }
    try:
        response = httpx.post(
            url,
            json={"query": query, "top_k": top_k},
            headers=headers,
            timeout=15.0,
        )
        response.raise_for_status()
        return response.json().get("chunks", [])
    except httpx.HTTPError:
        return []
