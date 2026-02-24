"""DigitalOcean Knowledge Base client for RAG queries.

Supports:
- kbaas.do-ai.run retrieve (DO_KB_RETRIEVE_URL + DO_API_TOKEN Bearer only), body: query, num_results, alpha
- v2 API: POST https://api.digitalocean.com/v2/gen-ai/knowledge_bases/{uuid}/query
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)
_DO_KB_API = "https://api.digitalocean.com/v2/gen-ai/knowledge_bases"


def _normalize_kbaas_result(r: dict) -> dict:
    """Normalize kbaas result: { text_content, metadata } -> { text, score, source_url }."""
    text = r.get("text_content") or r.get("text") or r.get("content") or ""
    meta = r.get("metadata") or {}
    source = meta.get("item_name") or meta.get("source") or ""
    return {
        "text": text.strip() if isinstance(text, str) else str(text),
        "score": r.get("score", 0),
        "source_url": source,
    }


def _query_kbaas_retrieve(query: str, top_k: int) -> list[dict]:
    """Query kbaas.do-ai.run/v1/{kb_id}/retrieve. Requires Bearer token (DO_API_TOKEN with GenAI:read scope)."""
    if not settings.do_kb_retrieve_url or not settings.do_api_token:
        return []
    headers = {
        "Authorization": f"Bearer {settings.do_api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "num_results": min(top_k, 100),
        "alpha": 0.5,
    }
    try:
        resp = httpx.post(
            settings.do_kb_retrieve_url.rstrip("/"),
            json=payload,
            headers=headers,
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("results") or data.get("chunks") or []
        return [_normalize_kbaas_result(c) if isinstance(c, dict) else {"text": str(c), "score": 0, "source_url": ""} for c in raw]
    except httpx.HTTPStatusError as e:
        logger.warning("kbaas retrieve failed %s: %s", e.response.status_code, e.response.text[:300])
        return []
    except Exception as e:
        logger.exception("kbaas retrieve error: %s", e)
        return []


def _query_v2_api(query: str, top_k: int) -> list[dict]:
    """Query v2 gen-ai knowledge_bases API (Bearer token)."""
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


def query_knowledge_base(query: str, top_k: int = 5) -> list[dict]:
    """Query the Knowledge Base and return relevant text chunks.

    Uses kbaas retrieve if DO_KB_RETRIEVE_URL + DO_API_TOKEN; else v2 API. kbaas requires Bearer token (GenAI:read).
    Returns list of dicts with keys: text, source_url, score.
    """
    if settings.do_kb_retrieve_url and settings.do_api_token:
        logger.info("Knowledge base: querying kbaas retrieve (query=%s)", query[:50])
        chunks = _query_kbaas_retrieve(query, top_k)
        logger.info("Knowledge base: kbaas returned %d chunks", len(chunks))
        return chunks
    if settings.do_kb_uuid and settings.do_api_token:
        logger.info("Knowledge base: querying v2 API (query=%s)", query[:50])
        return _query_v2_api(query, top_k)
    if settings.do_kb_retrieve_url and not settings.do_api_token:
        logger.warning("Knowledge base: DO_KB_RETRIEVE_URL is set but DO_API_TOKEN is missing (create token with GenAI:read at cloud.digitalocean.com/account/api/tokens)")
    else:
        logger.warning("Knowledge base: not configured (set DO_KB_RETRIEVE_URL and DO_API_TOKEN)")
    return []
