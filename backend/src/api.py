"""
Shared Synapse REST API

Mounts:
  /auth         - Login, refresh, logout (public)
  /admin/users  - User management (admin only)
  /api/synapses - Synapse CRUD + activation (auth required)

Run with:
    uvicorn main:app --reload
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

import frontmatter
import yaml
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .auth import require_role, router as auth_router
from .db import delete_chunks_for_document, delete_document, get_document, list_documents_by_type, upsert_chunk, upsert_document
from .db.synapses_store import (
    activate_synapse as db_activate_synapse,
    deactivate_synapse as db_deactivate_synapse,
    delete_synapse as db_delete_synapse,
    get_synapse as db_get_synapse,
    list_synapses as db_list_synapses,
    upsert_synapse as db_upsert_synapse,
)
from .glama_import import search_hosted_connectors
from .db.users_store import ensure_admin_exists
from .github_import import fetch_import_document, list_import_candidates, search_repositories_page
from .ingestion import ingest_file, run_ingestion
from .ingestion.chunker import chunk_text
from .ingestion.embeddings import embed_texts as embed_texts_batch
from .ingestion.parser import VALID_DOCUMENT_TYPES, parse_file
from .retrieval import hybrid_search, rank_results
from .skills_import import search_skills
from .user_management import router as users_router

logger = logging.getLogger(__name__)

app = FastAPI(title="Shared Synapse API", version="0.2.0")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)


class UpsertSynapseRequest(BaseModel):
    name: str
    description: str
    activation: str = "optional"
    includes: Optional[list] = None
    tags: Optional[list] = None
    common_tasks: Optional[list] = None
    recommended_tools: Optional[list] = None
    extends: Optional[list] = None


class ResourceUpdateRequest(BaseModel):
    name: str
    description: str = ""
    content: str


def _knowledge_root() -> Path:
    """Return the repository knowledge directory used for local synapse resources."""
    return Path(__file__).resolve().parents[2] / "knowledge"


def _build_local_resource_index() -> dict[str, dict]:
    """Build a lightweight lookup of local knowledge resources by document ID."""
    root = _knowledge_root()
    patterns = [
        "skills/**/*.md",
        "skills/**/*.markdown",
        "rules/**/*.md",
        "rules/**/*.markdown",
        "tools/**/*.json",
        "tools/**/*.yaml",
        "tools/**/*.yml",
        "concepts/**/*.md",
        "concepts/**/*.markdown",
        "decisions/**/*.md",
        "decisions/**/*.markdown",
        "designs/**/*.md",
        "designs/**/*.markdown",
    ]
    resources: dict[str, dict] = {}
    for pattern in patterns:
        for path in root.glob(pattern):
            parsed = parse_file(str(path))
            if parsed is None:
                continue
            metadata = parsed.get("metadata") or {}
            resources[parsed["id"]] = {
                "id": parsed["id"],
                "name": metadata.get("name") or parsed["id"],
                "description": metadata.get("description") or "",
                "type": parsed.get("type", "document"),
                "source_path": str(path.relative_to(root.parent)),
                "file_path": str(path),
            }
    return resources


def _normalized_local_resource_types(resource_types: Optional[list]) -> list[str]:
    """Normalize requested project resource types for local installation."""
    normalized: list[str] = []
    for resource_type in resource_types or ["skill", "rule", "tool"]:
        value = str(resource_type).strip().lower()
        if value and value not in normalized:
            normalized.append(value)

    invalid = [value for value in normalized if value not in {"skill", "rule", "tool"}]
    if invalid:
        raise HTTPException(status_code=422, detail="types must contain only: skill, rule, tool")
    return normalized


def _local_project_resource_files(resource_types: Optional[list] = None) -> list[Path]:
    """Return local bundled project files under knowledge/ recursively for the requested types."""
    root = _knowledge_root()
    selected = _normalized_local_resource_types(resource_types)
    pattern_map = {
        "skill": ("skills/**/*.md", "skills/**/*.markdown"),
        "rule": ("rules/**/*.md", "rules/**/*.markdown"),
        "tool": ("tools/**/*.json", "tools/**/*.yaml", "tools/**/*.yml"),
    }

    files: dict[str, Path] = {}
    for resource_type in selected:
        for pattern in pattern_map[resource_type]:
            for path in root.glob(pattern):
                if path.is_file():
                    files[str(path)] = path
    return [files[key] for key in sorted(files)]


def _resource_group_key(resource_type: str) -> str:
    """Map internal document types onto the grouped resource buckets used by the UI."""
    if resource_type == "skill":
        return "skills"
    if resource_type == "rule":
        return "rules"
    if resource_type == "tool":
        return "tools"
    return "other"


def _empty_resource_groups() -> dict[str, list[dict]]:
    """Return the grouped resource shape used by the frontend."""
    return {"skills": [], "rules": [], "tools": [], "other": [], "missing": []}


def _sort_grouped_resources(grouped: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Keep grouped resources in a stable display order."""
    for key in ("skills", "rules", "tools", "other", "missing"):
        grouped[key] = sorted(grouped[key], key=lambda item: item.get("name") or item.get("id") or "")
    return grouped


def _public_resource(resource: dict) -> dict:
    """Hide internal filesystem details from API responses."""
    return {key: value for key, value in resource.items() if key != "file_path"}


async def _build_indexed_resource_groups() -> dict[str, list[dict]]:
    """Build grouped resources from indexed documents in Chroma."""
    grouped = _empty_resource_groups()
    for resource_type in ("skill", "rule", "tool"):
        indexed_documents = await list_documents_by_type(resource_type)
        for document in indexed_documents:
            metadata = document.get("metadata") or {}
            grouped[_resource_group_key(resource_type)].append({
                "id": document["id"],
                "name": metadata.get("name") or document["id"],
                "description": metadata.get("description") or "",
                "type": resource_type,
                "source_path": metadata.get("source_path") or metadata.get("source_url") or "Indexed document",
            })
    return grouped


async def _library_resource_index() -> dict[str, dict]:
    """Merge local project resources and indexed resources into one lookup."""
    resources = _build_local_resource_index()
    indexed_groups = await _build_indexed_resource_groups()
    for key in ("skills", "rules", "tools"):
        for resource in indexed_groups[key]:
            resources.setdefault(resource["id"], resource)
    return resources


def _library_resource_counts(resources: list[dict]) -> dict[str, int]:
    """Summarize library totals for the primary frontend resource groups."""
    counts = {"skills": 0, "rules": 0, "tools": 0}
    for resource in resources:
        key = _resource_group_key(resource.get("type", ""))
        if key in counts:
            counts[key] += 1
    return counts


def _resource_matches_query(resource: dict, query: str) -> bool:
    """Return whether a library resource matches a free-text query."""
    search = query.strip().lower()
    if not search:
        return True

    candidates = [
        resource.get("id"),
        resource.get("name"),
        resource.get("description"),
        resource.get("source_path"),
    ]
    return any(search in str(candidate).lower() for candidate in candidates if candidate)


def _resource_type_matches(resource: dict, resource_type: str) -> bool:
    """Check whether a library resource belongs to the requested type."""
    return resource.get("type") == resource_type


def _serialize_markdown_resource(file_path: str, payload: ResourceUpdateRequest, resource_id: str) -> tuple[str, dict]:
    path = Path(file_path)
    post = frontmatter.load(path)
    metadata = dict(post.metadata)
    metadata["id"] = resource_id
    metadata["name"] = payload.name
    metadata["description"] = payload.description
    post.metadata = metadata
    post.content = payload.content.strip() + "\n"
    return frontmatter.dumps(post), metadata


def _serialize_tool_resource(file_path: str, payload: ResourceUpdateRequest, resource_id: str) -> tuple[str, dict]:
    parsed = json.loads(payload.content)
    if not isinstance(parsed, dict):
        raise ValueError("Tool content must be a JSON object")
    parsed["id"] = resource_id
    parsed["description"] = payload.description
    metadata = parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else {}
    parsed["metadata"] = metadata
    return json.dumps(parsed, indent=2), {"name": payload.name, "description": payload.description, **parsed}


async def _get_resource_detail(resource_type: str, resource_id: str) -> Optional[dict]:
    resources = await _library_resource_index()
    resource = resources.get(resource_id)
    if resource is None or not _resource_type_matches(resource, resource_type):
        return None

    if resource.get("file_path"):
        path = Path(resource["file_path"])
        if resource_type in {"skill", "rule"}:
            post = frontmatter.load(path)
            return {
                **_public_resource(resource),
                "content": post.content,
                "editable": True,
                "storage": "local",
            }
        return {
            **_public_resource(resource),
            "content": path.read_text(encoding="utf-8"),
            "editable": True,
            "storage": "local",
        }

    document = await get_document(resource_id)
    if document is None:
        return None
    metadata = document.get("metadata") or {}
    return {
        **_public_resource(resource),
        "name": metadata.get("name") or resource.get("name") or resource_id,
        "description": metadata.get("description") or resource.get("description") or "",
        "content": document.get("content", ""),
        "editable": True,
        "storage": "indexed",
    }


async def _update_resource(resource_type: str, resource_id: str, payload: ResourceUpdateRequest) -> dict:
    detail = await _get_resource_detail(resource_type, resource_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Resource '{resource_id}' not found")

    resources = await _library_resource_index()
    resource = resources[resource_id]
    if resource.get("file_path"):
        try:
            if resource_type in {"skill", "rule"}:
                serialized_content, metadata = _serialize_markdown_resource(resource["file_path"], payload, resource_id)
            elif resource_type == "tool":
                serialized_content, metadata = _serialize_tool_resource(resource["file_path"], payload, resource_id)
            else:
                raise ValueError("Unsupported resource type")
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        Path(resource["file_path"]).write_text(serialized_content, encoding="utf-8")
        await _index_knowledge_document(resource_id, resource_type, payload.content, metadata)
    else:
        document = await get_document(resource_id)
        if document is None:
            raise HTTPException(status_code=404, detail=f"Resource '{resource_id}' not found")
        metadata = dict(document.get("metadata") or {})
        metadata["name"] = payload.name
        metadata["description"] = payload.description
        await _index_knowledge_document(resource_id, resource_type, payload.content, metadata)

    updated_detail = await _get_resource_detail(resource_type, resource_id)
    if updated_detail is None:
        raise HTTPException(status_code=500, detail=f"Failed to reload resource '{resource_id}'")
    return updated_detail


def _detach_resource_from_all_synapses(resource_id: str) -> None:
    """Remove a resource include from every synapse that references it."""
    for synapse in db_list_synapses():
        includes = list(synapse.get("includes") or [])
        if resource_id not in includes:
            continue

        remaining_includes = [include_id for include_id in includes if include_id != resource_id]
        db_upsert_synapse(
            name=synapse["name"],
            description=synapse.get("description", ""),
            activation=synapse.get("activation", "optional"),
            includes=remaining_includes,
            tags=synapse.get("tags"),
            common_tasks=synapse.get("common_tasks"),
            recommended_tools=synapse.get("recommended_tools"),
            extends=synapse.get("extends"),
        )


async def _delete_resource(resource_type: str, resource_id: str) -> dict:
    """Delete a resource from the shared library and clean up its index and synapse references."""
    detail = await _get_resource_detail(resource_type, resource_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Resource '{resource_id}' not found")

    resources = await _library_resource_index()
    resource = resources[resource_id]

    if resource.get("file_path"):
        path = Path(resource["file_path"])
        if path.exists():
            path.unlink()

    await delete_chunks_for_document(resource_id)
    await delete_document(resource_id)
    _detach_resource_from_all_synapses(resource_id)
    return {"status": "deleted", "id": resource_id, "type": resource_type}


@app.get("/api/synapses", dependencies=[Depends(require_role("viewer"))])
async def api_list_synapses() -> dict:
    return {"synapses": db_list_synapses()}


@app.get("/api/synapses/{name}", dependencies=[Depends(require_role("viewer"))])
async def api_get_synapse(name: str) -> dict:
    synapse = db_get_synapse(name)
    if synapse is None:
        raise HTTPException(status_code=404, detail=f"Synapse '{name}' not found")
    return synapse


@app.get("/api/synapses/{name}/resources", dependencies=[Depends(require_role("viewer"))])
async def api_get_synapse_resources(name: str) -> dict:
    synapse = db_get_synapse(name)
    if synapse is None:
        raise HTTPException(status_code=404, detail=f"Synapse '{name}' not found")

    library_resources = await _library_resource_index()
    grouped = _empty_resource_groups()

    for include_id in synapse.get("includes") or []:
        resource = library_resources.get(include_id)
        if resource is None:
            indexed_document = await get_document(include_id)
            if indexed_document is None:
                grouped["missing"].append({"id": include_id})
                continue
            metadata = indexed_document.get("metadata") or {}
            resource = {
                "id": indexed_document["id"],
                "name": metadata.get("name") or indexed_document["id"],
                "description": metadata.get("description") or "",
                "type": indexed_document.get("type", "document"),
                "source_path": metadata.get("source_path") or metadata.get("source_url") or "Indexed document",
            }

        grouped[_resource_group_key(resource["type"])].append(_public_resource(resource))

    return _sort_grouped_resources(grouped)


@app.get("/api/resources", dependencies=[Depends(require_role("viewer"))])
async def api_list_resources() -> dict:
    grouped = _empty_resource_groups()
    for resource in (await _library_resource_index()).values():
        grouped[_resource_group_key(resource["type"])].append(_public_resource(resource))
    grouped["other"] = []
    grouped["missing"] = []
    return _sort_grouped_resources(grouped)


@app.get("/api/resources/search", dependencies=[Depends(require_role("viewer"))])
async def api_search_resources(
    resource_type: str = Query(..., alias="type"),
    query: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(8, ge=1, le=50),
) -> dict:
    if resource_type not in {"skill", "rule", "tool"}:
        raise HTTPException(status_code=422, detail="type must be one of: skill, rule, tool")

    library_resources = list((await _library_resource_index()).values())
    counts = _library_resource_counts(library_resources)
    matching = [
        _public_resource(resource)
        for resource in library_resources
        if _resource_type_matches(resource, resource_type) and _resource_matches_query(resource, query)
    ]
    matching = sorted(matching, key=lambda item: item.get("name") or item.get("id") or "")

    total = len(matching)
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(page, total_pages)
    start = (current_page - 1) * page_size
    end = start + page_size

    return {
        "items": matching[start:end],
        "page": current_page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "query": query,
        "type": resource_type,
        "counts": counts,
    }


@app.get("/api/resources/{resource_type}/{resource_id}", dependencies=[Depends(require_role("viewer"))])
async def api_get_resource_detail(resource_type: str, resource_id: str) -> dict:
    if resource_type not in {"skill", "rule", "tool"}:
        raise HTTPException(status_code=422, detail="resource_type must be one of: skill, rule, tool")
    detail = await _get_resource_detail(resource_type, resource_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Resource '{resource_id}' not found")
    return detail


@app.put("/api/resources/{resource_type}/{resource_id}", dependencies=[Depends(require_role("admin"))])
async def api_update_resource(resource_type: str, resource_id: str, body: ResourceUpdateRequest) -> dict:
    if resource_type not in {"skill", "rule", "tool"}:
        raise HTTPException(status_code=422, detail="resource_type must be one of: skill, rule, tool")
    return await _update_resource(resource_type, resource_id, body)


@app.delete("/api/resources/{resource_type}/{resource_id}", dependencies=[Depends(require_role("admin"))])
async def api_delete_resource(resource_type: str, resource_id: str) -> dict:
    if resource_type not in {"skill", "rule", "tool"}:
        raise HTTPException(status_code=422, detail="resource_type must be one of: skill, rule, tool")
    return await _delete_resource(resource_type, resource_id)


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


class ImportGithubDocumentRequest(BaseModel):
    repo: str
    path: str
    synapse_name: Optional[str] = None


class ImportLocalResourcesRequest(BaseModel):
    types: Optional[list] = None
    synapse_name: Optional[str] = None


def _resolve_import_synapse(synapse_name: Optional[str]) -> Optional[dict]:
    """Resolve an optional import target synapse for flows that may index into the shared library only."""
    target_name = (synapse_name or "").strip()
    if not target_name:
        return None
    synapse = db_get_synapse(target_name)
    if synapse is None:
        raise HTTPException(status_code=404, detail=f"Synapse '{target_name}' not found")
    return synapse


def _attach_resource_to_synapse(synapse: dict, resource_id: str) -> dict:
    """Attach a resource identifier to a synapse if it is not already included."""
    includes = list(synapse.get("includes") or [])
    if resource_id not in includes:
        includes.append(resource_id)

    return db_upsert_synapse(
        name=synapse["name"],
        description=synapse.get("description", ""),
        activation=synapse.get("activation", "optional"),
        includes=includes,
        tags=synapse.get("tags"),
        common_tasks=synapse.get("common_tasks"),
        recommended_tools=synapse.get("recommended_tools"),
        extends=synapse.get("extends"),
    )


async def _index_knowledge_document(id: str, type: str, content: str, metadata: dict) -> int:
    """Index a knowledge document into the documents and chunks collections."""
    await upsert_document(id, type, content, metadata)
    chunks = chunk_text(content, id)
    if chunks:
        embeddings = embed_texts_batch([chunk["content"] for chunk in chunks])
        await delete_chunks_for_document(id)
        for chunk, embedding in zip(chunks, embeddings):
            chunk_meta = {**chunk["metadata"], "document_type": type}
            await upsert_chunk(
                id=chunk["id"],
                document_id=id,
                content=chunk["content"],
                embedding=embedding,
                metadata=chunk_meta,
            )
    return len(chunks)


@app.post("/api/knowledge", dependencies=[Depends(require_role("contributor"))], status_code=201)
async def api_add_knowledge(body: AddKnowledgeRequest) -> dict:
    if body.type not in VALID_DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of: {', '.join(sorted(VALID_DOCUMENT_TYPES))}")
    meta = body.metadata or {}
    meta.setdefault("source", "api_direct")
    chunks = await _index_knowledge_document(body.id, body.type, body.content, meta)
    return {"status": "indexed", "id": body.id, "chunks": chunks}


@app.get("/api/import/github/repos", dependencies=[Depends(require_role("viewer"))])
async def api_search_github_repos(query: str, page: int = Query(1, ge=1), page_size: int = Query(8, ge=1, le=20)) -> dict:
    if not query.strip():
        return {"repos": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1}
    try:
        result = search_repositories_page(query, limit=page_size, page=page)
        total = result["total_count"]
        total_pages = max(1, (total + page_size - 1) // page_size)
        return {
            "repos": result["items"],
            "total": total,
            "page": result["page"],
            "page_size": result["per_page"],
            "total_pages": total_pages,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/import/skills/search", dependencies=[Depends(require_role("viewer"))])
async def api_search_skills(query: str, page: int = Query(1, ge=1), page_size: int = Query(8, ge=1, le=20)) -> dict:
    if not query.strip():
        return {"skills": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1}

    fetch_limit = min(max(page * page_size, page_size), 100)
    try:
        matches = search_skills(query, limit=fetch_limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    total = len(matches)
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(page, total_pages)
    start = (current_page - 1) * page_size
    end = start + page_size
    return {
        "skills": matches[start:end],
        "total": total,
        "page": current_page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@app.get("/api/import/skills/detail", dependencies=[Depends(require_role("viewer"))])
async def api_skill_detail(source: str, skill_id: str) -> dict:
    try:
        candidates = list_import_candidates(source, kind="skill", limit=200)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    root_skill_candidates = [
        candidate for candidate in candidates if candidate.get("name", "").lower() in {"skill.md", "skill.markdown"}
    ]
    if root_skill_candidates:
        candidates = root_skill_candidates

    normalized_skill_id = skill_id.strip().lower()
    prioritized: list[dict] = []
    remaining: list[dict] = []
    for candidate in candidates:
        haystack = f"{candidate.get('name', '')} {candidate.get('path', '')}".lower()
        if normalized_skill_id and normalized_skill_id in haystack:
            prioritized.append(candidate)
        else:
            remaining.append(candidate)
    candidates = prioritized + remaining

    description = ""
    resolved_name = skill_id
    primary_candidate = candidates[0] if candidates else None
    if primary_candidate is not None:
        try:
            document = fetch_import_document(source, primary_candidate["path"])
            description = document.get("description") or ""
            resolved_name = document.get("name") or skill_id
        except RuntimeError:
            pass

    return {
        "source": source,
        "skill_id": skill_id,
        "name": resolved_name,
        "description": description,
        "page_url": f"https://skills.sh/{source}/{skill_id}",
        "github_url": f"https://github.com/{source}",
        "install_command": f"npx skills add {source}",
        "bundle_size": len(candidates),
        "candidates": candidates,
        "primary_candidate": primary_candidate,
    }


@app.get("/api/import/mcp/hosted/search", dependencies=[Depends(require_role("viewer"))])
async def api_search_hosted_mcp_connectors(
    query: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(5, ge=1, le=10),
) -> dict:
    if not query.strip():
        return {"connectors": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1}

    fetch_limit = min(max(page * page_size, page_size), 20)
    try:
        matches = search_hosted_connectors(query, limit=fetch_limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    total = len(matches)
    total_pages = max(1, (total + page_size - 1) // page_size)
    current_page = min(page, total_pages)
    start = (current_page - 1) * page_size
    end = start + page_size
    return {
        "connectors": matches[start:end],
        "total": total,
        "page": current_page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@app.get("/api/import/github/candidates", dependencies=[Depends(require_role("viewer"))])
async def api_list_github_candidates(repo: str, kind: Optional[str] = None, query: Optional[str] = None) -> dict:
    normalized_kind = kind if kind and kind != "all" else None
    if normalized_kind and normalized_kind not in {"skill", "rule", "tool"}:
        raise HTTPException(status_code=422, detail="kind must be one of: skill, rule, tool, all")
    try:
        return {"candidates": list_import_candidates(repo, query=query, kind=normalized_kind)}
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/import/github/import", dependencies=[Depends(require_role("admin"))], status_code=201)
async def api_import_github_document(body: ImportGithubDocumentRequest) -> dict:
    synapse = _resolve_import_synapse(body.synapse_name)

    try:
        document = fetch_import_document(body.repo, body.path)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if document["type"] not in VALID_DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail=f"Imported document type '{document['type']}' is not supported")

    chunks = await _index_knowledge_document(
        id=document["id"],
        type=document["type"],
        content=document["content"],
        metadata=document["metadata"],
    )

    response = {
        "status": "imported",
        "document": {
            "id": document["id"],
            "type": document["type"],
            "name": document["name"],
            "description": document["description"],
        },
        "chunks": chunks,
    }
    if synapse is not None:
        updated_synapse = _attach_resource_to_synapse(synapse, document["id"])
        response["synapse"] = updated_synapse
    return response


@app.post("/api/import/local/project", dependencies=[Depends(require_role("admin"))], status_code=201)
async def api_import_local_project_resources(body: ImportLocalResourcesRequest) -> dict:
    """Install bundled local skills, rules, and tools from the project knowledge directory."""
    selected_types = _normalized_local_resource_types(body.types)
    files = _local_project_resource_files(body.types)
    synapse = _resolve_import_synapse(body.synapse_name)

    imported: list[dict] = []
    failed: list[str] = []
    for path in files:
        parsed = parse_file(str(path))
        if parsed is None or parsed.get("type") not in selected_types:
            continue

        if await ingest_file(str(path)):
            metadata = parsed.get("metadata") or {}
            if synapse is not None:
                synapse = _attach_resource_to_synapse(synapse, parsed["id"])
            imported.append({
                "id": parsed["id"],
                "type": parsed["type"],
                "name": metadata.get("name") or parsed["id"],
                "source_path": str(path.relative_to(_knowledge_root().parent)),
            })
        else:
            failed.append(str(path.relative_to(_knowledge_root().parent)))

    return {
        "status": "imported",
        "types": selected_types,
        "total": len(files),
        "success": len(imported),
        "failed": len(failed),
        "resources": imported,
        "failed_paths": failed,
        "synapse": synapse,
    }


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
