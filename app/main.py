import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ProcureIQ API",
    description="AI-powered procurement intelligence platform combining graph analytics with generative AI.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])


@app.on_event("startup")
def on_startup() -> None:
    logger.info("ProcureIQ API starting (env=%s)", settings.app_env)


@app.get("/health", tags=["health"])
def health_check() -> dict:
    logger.debug("Health check")
    return {"status": "ok", "service": "ProcureIQ API"}


@app.get("/health/neo4j", tags=["health"])
def health_neo4j() -> dict:
    """Test Neo4j connection: runs a simple query and returns status."""
    from app.graph.client import neo4j_client
    try:
        result = neo4j_client.run_query("RETURN 1 AS ok")
        if result and result[0].get("ok") == 1:
            return {"status": "ok", "neo4j": "connected"}
        return {"status": "error", "neo4j": "unexpected response"}
    except Exception as e:
        logger.exception("Neo4j health check failed")
        return {"status": "error", "neo4j": "disconnected", "detail": str(e)}


@app.get("/health/digitalocean", tags=["health"])
def health_digitalocean() -> dict:
    """Test DigitalOcean agent connection: sends a short test message and checks response."""
    if not settings.do_agent_url or not settings.do_agent_access_key:
        return {"status": "ok", "digitalocean_agent": "not_configured"}
    from app.agent.do_agent import query_do_agent
    try:
        reply = query_do_agent("Reply with exactly: OK", timeout=15.0)
        if reply and "OK" in reply:
            return {"status": "ok", "digitalocean_agent": "connected"}
        return {"status": "error", "digitalocean_agent": "unexpected_response", "detail": (reply or "empty reply")[:200]}
    except Exception as e:
        logger.exception("DigitalOcean agent health check failed")
        return {"status": "error", "digitalocean_agent": "disconnected", "detail": str(e)}


@app.get("/health/knowledge-base", tags=["health"])
def health_knowledge_base() -> dict:
    """Test Knowledge Base connection (kbaas retrieve or v2 API)."""
    from app.agent.rag import query_knowledge_base
    from app.config import settings
    if not settings.do_kb_retrieve_url and not settings.do_kb_uuid:
        return {"status": "ok", "knowledge_base": "not_configured"}
    try:
        chunks = query_knowledge_base("test", top_k=1)
        return {"status": "ok", "knowledge_base": "connected", "chunks_returned": len(chunks)}
    except Exception as e:
        logger.exception("Knowledge base health check failed")
        return {"status": "error", "knowledge_base": "disconnected", "detail": str(e)}
