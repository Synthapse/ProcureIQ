from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, graph

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
app.include_router(graph.router, prefix="/api/v1/graph", tags=["graph"])


@app.get("/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok", "service": "ProcureIQ API"}
