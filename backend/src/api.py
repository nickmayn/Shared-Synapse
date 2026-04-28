"""
Shared Synapse REST API

Mounts:
  /auth         - Login, refresh, logout (public)
  /admin/users  - User management (admin only)
  /api/synapses - Synapse CRUD + activation (auth required)

Run with:
  uvicorn src.api:app --reload
"""
import json
import logging
import os
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth import router as auth_router, require_role
from .user_management import router as users_router
from .db.synapses_store import (
    list_synapses as db_list_synapses,
    get_synapse as db_get_synapse,
    upsert_synapse as db_upsert_synapse,
    delete_synapse as db_delete_synapse,
    activate_synapse as db_activate_synapse,
    deactivate_synapse as db_deactivate_synapse,
)
from .db.users_store import ensure_admin_exists
from .ingestion import run_ingestion
from .ingestion.chunker import chunk_text
from .ingestion.embeddings import embed_texts as embed_texts_batch
from .ingestion.parser import VALID_DOCUMENT_TYPES
from .retrieval import hybrid_search, rank_results
from .db import upsert_document, upsert_chunk, delete_chunks_for_document

logger = logging.getLogger(__name__)

app = FastAPI(title="Shared Synapse API", version="0.2.0")

# Allow the hosted frontend (and local dev) to call the API
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(users_router)


# ---------------------------------------------------------------------------
# Synapse endpoints
# ---------------------------------------------------------------------------

class UpsertSynapseRequest(BaseModel):
    name: str
    description: str
    activation: str = "optional"
    includes: Optional[list] = None
    tags: Optional[list] = None
    common_tasks: Optional[list] = None
    recommended_tools: Optional[list] = None
    extends: Optional[list] = None


@app.get("/api/synapses", dependencies=[Depends(require_role("viewer"))])
async def api_list_synapses() -> dict:
    return {"synapses": db_list_synapses()}


@app.get("/api/synapses/{name}", dependencies=[Depends(require_role("viewer"))])
async def api_get_synapse(name: str) -> dict:
    synapse = db_get_synapse(name)
    if synapse is None:
        raise HTTPException(status_code=404, detail=f"Synapse '{name}' not found")
    return synapse


@app.put("/api/synapses/{name}", dependencies=[Depends(require_role("admin"))])
async def api_upsert_synapse(name: str, body: UpsertSynapseRequest) -> dict:
    body.name = name  # ensure path param wins
    try:
        return db_upsert_synapse(
            name=name,
            description=body.description,
            activation=body.activation,
            includes=body.includes,
            tags=body.tags,
            common_tasks=body.common_tasks,
            recommended_tools=body.recommended_tools,
            extends=body.extends,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/api/synapses/{name}", dependencies=[Depends(require_role("admin"))])
async def api_delete_synapse(name: str) -> dict:
    ok = db_delete_synapse(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Synapse '{name}' not found")
    return {"status": "deleted", "name": name}


@app.post("/api/synapses/{name}/activate", dependencies=[Depends(require_role("contributor"))])
async def api_activate_synapse(name: str) -> dict:
    ok = db_activate_synapse(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Synapse '{name}' not found")
    return {"status": "activated", "name": name}


@app.post("/api/synapses/{name}/deactivate", dependencies=[Depends(require_role("contributor"))])
async def api_deactivate_synapse(name: str) -> dict:
    db_deactivate_synapse(name)
    return {"status": "deactivated", "name": name}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Search (REST wrapper for CLI / extension)
# ---------------------------------------------------------------------------

@app.get("/api/search", dependencies=[Depends(require_role("viewer"))])
async def api_search(query: str, filters: Optional[str] = None) -> dict:
    parsed_filters = None
    if filters:
        try:
            parsed_filters = json.loads(filters)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="filters must be valid JSON")
    raw = await hybrid_search(query, filters=parsed_filters, top_k=20)
    ranked = rank_results(raw, query, filters=parsed_filters, top_k=10)
    return {"results": ranked, "total": len(ranked)}


# ---------------------------------------------------------------------------
# Knowledge add (REST wrapper for CLI / extension)
# ---------------------------------------------------------------------------

class AddKnowledgeRequest(BaseModel):
    id: str
    type: str
    content: str
    metadata: Optional[dict] = None


@app.post("/api/knowledge", dependencies=[Depends(require_role("contributor"))], status_code=201)
async def api_add_knowledge(body: AddKnowledgeRequest) -> dict:
    if body.type not in VALID_DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of: {', '.join(sorted(VALID_DOCUMENT_TYPES))}")
    meta = body.metadata or {}
    meta.setdefault("source", "api_direct")
    await upsert_document(body.id, body.type, body.content, meta)
    chunks = chunk_text(body.content, body.id)
    if chunks:
        embeddings = embed_texts_batch([c["content"] for c in chunks])
        await delete_chunks_for_document(body.id)
        for chunk, embedding in zip(chunks, embeddings):
            chunk_meta = {**chunk["metadata"], "document_type": body.type}
            await upsert_chunk(
                id=chunk["id"],
                document_id=body.id,
                content=chunk["content"],
                embedding=embedding,
                metadata=chunk_meta,
            )
    return {"status": "indexed", "id": body.id, "chunks": len(chunks)}


# ---------------------------------------------------------------------------
# Reindex
# ---------------------------------------------------------------------------

@app.post("/api/reindex", dependencies=[Depends(require_role("admin"))])
async def api_reindex() -> dict:
    stats = await run_ingestion()
    return {"status": "complete", **stats}


@app.on_event("startup")
async def startup_event() -> None:
    ensure_admin_exists()
    logger.info("Shared Synapse API started")
