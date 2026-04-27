"""
Shared Synapse MCP Server

Exposes:
  - search_knowledge
  - get_document
    - get_context_pack / get_synapse
  - list_tools
  - execute_tool
"""
import json
import logging
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..db import get_document as db_get_document
from ..db import upsert_document, upsert_chunk, delete_chunks_for_document
from ..db.chunks import search_chunks
from ..db.tools_store import get_tool, list_tools as db_list_tools
from ..db.skills_store import (
    get_skill as db_get_skill,
    list_skills as db_list_skills,
    upsert_skill as db_upsert_skill,
    mark_skills_for_refresh,
)
from ..db.rules_store import get_rule as db_get_rule, list_rules as db_list_rules
from ..ingestion import run_ingestion, ingest_file, delete_knowledge as pipeline_delete_knowledge
from ..ingestion.chunker import chunk_text
from ..ingestion.embeddings import embed_text, embed_texts as embed_texts_batch
from ..ingestion.parser import VALID_DOCUMENT_TYPES
from ..retrieval import hybrid_search, rank_results
from .security import (
    audit_log,
    check_tool_allowed,
    validate_query,
    validate_tool_id,
    validate_tool_input,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

mcp = FastMCP("shared-synapse")


@mcp.tool()
async def search_knowledge(query: str, filters: Optional[str] = None) -> str:
    """
    Search knowledge semantically with optional structured filters.
    filters: JSON string with optional keys: type, tags (list), context_pack
    Returns ranked document chunks with metadata.
    """
    query = validate_query(query)
    parsed_filters = None
    if filters:
        try:
            parsed_filters = json.loads(filters)
        except json.JSONDecodeError:
            raise ValueError("filters must be valid JSON")

    await audit_log("search_knowledge", details={"query": query, "filters": parsed_filters})

    raw = await hybrid_search(query, filters=parsed_filters, top_k=20)
    ranked = rank_results(raw, query, filters=parsed_filters, top_k=10)

    return json.dumps({"results": ranked, "total": len(ranked)}, default=str)


@mcp.tool()
async def get_document(id: str) -> str:
    """
    Retrieve a full document by its ID.
    Returns document content and metadata.
    """
    if not id or not isinstance(id, str):
        raise ValueError("id must be a non-empty string")

    await audit_log("get_document", resource_type="document", resource_id=id)

    doc = await db_get_document(id)
    if doc is None:
        return json.dumps({"error": f"Document not found: {id}"})

    return json.dumps(doc, default=str)


@mcp.tool()
async def get_context_pack(name: str) -> str:
    """
    Retrieve a context pack by name.
    Returns the context pack YAML structure as JSON.
    """
    if not name or not isinstance(name, str):
        raise ValueError("name must be a non-empty string")

    await audit_log("get_context_pack", resource_type="context_pack", resource_id=name)

    doc = await db_get_document(name)

    # If found but wrong type, try semantic search for context packs
    if doc is not None and doc.get("type") != "context_pack":
        raw = await hybrid_search(name, filters={"type": "context_pack"}, top_k=1)
        if raw:
            doc_id = raw[0]["document_id"]
            doc = await db_get_document(doc_id)

    if doc is None:
        return json.dumps({"error": f"Context pack not found: {name}"})

    return json.dumps(doc, default=str)


@mcp.tool()
async def list_tools(task: str, context: Optional[str] = None) -> str:
    """
    List and rank tools relevant to a given task.
    Uses semantic similarity + metadata matching.
    Returns ranked tools with descriptions.
    """
    task = validate_query(task)
    await audit_log("list_tools", details={"task": task, "context": context})

    all_tools = await db_list_tools()

    if not all_tools:
        return json.dumps({"tools": [], "total": 0})

    query_text = f"{task} {context}" if context else task
    query_embedding = embed_text(query_text)
    chunk_results = await search_chunks(query_embedding, top_k=20, filters={"type": "tool"})

    tool_scores: dict[str, float] = {}
    for chunk in chunk_results:
        tid = chunk["document_id"]
        score = float(chunk["similarity"])
        if tid not in tool_scores or score > tool_scores[tid]:
            tool_scores[tid] = score

    ranked = sorted(all_tools, key=lambda t: tool_scores.get(t["id"], 0.0), reverse=True)

    result = [
        {
            "id": tool["id"],
            "description": tool["description"],
            "metadata": tool["metadata"],
            "score": tool_scores.get(tool["id"], 0.0),
        }
        for tool in ranked
    ]

    return json.dumps({"tools": result, "total": len(result)}, default=str)


@mcp.tool()
async def execute_tool(tool_id: str, input: str) -> str:
    """
    Execute a registered tool by ID with the given JSON input.
    Validates input schema before execution.
    """
    tool_id = validate_tool_id(tool_id)
    check_tool_allowed(tool_id)

    try:
        input_data = json.loads(input)
    except json.JSONDecodeError:
        raise ValueError("input must be valid JSON")

    tool = await get_tool(tool_id)
    if tool is None:
        return json.dumps({"error": f"Tool not found: {tool_id}"})

    input_schema = tool.get("input_schema") or {}
    if isinstance(input_schema, str):
        try:
            input_schema = json.loads(input_schema)
        except Exception:
            input_schema = {}

    validate_tool_input(input_data, input_schema)

    await audit_log(
        "execute_tool",
        resource_type="tool",
        resource_id=tool_id,
        details={"input_keys": list(input_data.keys()) if isinstance(input_data, dict) else []},
    )

    logger.info(
        f"Executing tool {tool_id} with input keys: "
        f"{list(input_data.keys()) if isinstance(input_data, dict) else []}"
    )

    # Sandboxed execution stub: replace with actual executor in production
    result = {
        "status": "executed",
        "tool_id": tool_id,
        "output": f"Tool '{tool_id}' executed successfully (sandboxed stub)",
        "input_received": input_data,
    }
    return json.dumps(result, default=str)


@mcp.tool()
async def add_knowledge(
    id: str,
    type: str,
    content: str,
    metadata: Optional[str] = None,
) -> str:
    """
    Add or update a knowledge document directly (no file required).
    Immediately ingests, embeds, and indexes the content.
    type: one of concept, decision, design, skill, rule, document
    metadata: optional JSON string of additional metadata fields
    Changes are immediately visible to all connected agents.
    """
    if not id or not isinstance(id, str):
        raise ValueError("id must be a non-empty string")
    content = validate_query(content)

    if type not in VALID_DOCUMENT_TYPES:
        raise ValueError(f"type must be one of: {', '.join(sorted(VALID_DOCUMENT_TYPES))}")

    parsed_meta: dict = {}
    if metadata:
        try:
            parsed_meta = json.loads(metadata)
        except json.JSONDecodeError:
            raise ValueError("metadata must be valid JSON")

    parsed_meta.setdefault("source", "mcp_direct")

    await audit_log("add_knowledge", resource_type=type, resource_id=id,
                    details={"content_length": len(content)})

    await upsert_document(id, type, content, parsed_meta)

    chunks = chunk_text(content, id)
    if chunks:
        embeddings = embed_texts_batch([c["content"] for c in chunks])
        await delete_chunks_for_document(id)
        for chunk, embedding in zip(chunks, embeddings):
            chunk_meta = {**chunk["metadata"], "document_type": type}
            if "tags" in parsed_meta:
                chunk_meta["tags"] = parsed_meta["tags"]
            await upsert_chunk(
                id=chunk["id"],
                document_id=id,
                content=chunk["content"],
                embedding=embedding,
                metadata=chunk_meta,
            )

    logger.info(f"add_knowledge: indexed '{id}' ({type}), {len(chunks)} chunks")
    return json.dumps({
        "status": "indexed",
        "id": id,
        "type": type,
        "chunks": len(chunks),
    })


@mcp.tool()
async def update_knowledge(
    id: str,
    content: str,
    metadata: Optional[str] = None,
) -> str:
    """
    Update an existing knowledge document's content and re-index it.
    Automatically marks dependent skills as needing refresh.
    Changes are immediately visible to all connected agents.
    """
    if not id or not isinstance(id, str):
        raise ValueError("id must be a non-empty string")
    content = validate_query(content)

    if metadata:
        try:
            json.loads(metadata)
        except json.JSONDecodeError:
            raise ValueError("metadata must be valid JSON")

    existing = await db_get_document(id)
    if existing is None:
        return json.dumps({"error": f"Document not found: {id}"})

    doc_type = existing["type"]
    merged_meta = dict(existing.get("metadata") or {})
    if metadata:
        merged_meta.update(json.loads(metadata))

    await audit_log("update_knowledge", resource_type=doc_type, resource_id=id,
                    details={"content_length": len(content)})

    await upsert_document(id, doc_type, content, merged_meta)

    chunks = chunk_text(content, id)
    if chunks:
        embeddings = embed_texts_batch([c["content"] for c in chunks])
        await delete_chunks_for_document(id)
        for chunk, embedding in zip(chunks, embeddings):
            chunk_meta = {**chunk["metadata"], "document_type": doc_type}
            if "tags" in merged_meta:
                chunk_meta["tags"] = merged_meta["tags"]
            await upsert_chunk(
                id=chunk["id"],
                document_id=id,
                content=chunk["content"],
                embedding=embedding,
                metadata=chunk_meta,
            )

    refreshed = await mark_skills_for_refresh([id])

    logger.info(f"update_knowledge: re-indexed '{id}', {refreshed} skills marked for refresh")
    return json.dumps({
        "status": "updated",
        "id": id,
        "chunks": len(chunks),
        "skills_marked_for_refresh": refreshed,
    })


@mcp.tool()
async def delete_knowledge(id: str) -> str:
    """
    Remove a knowledge document and all its chunks from the database.
    Marks dependent skills as needing refresh.
    """
    if not id or not isinstance(id, str):
        raise ValueError("id must be a non-empty string")

    await audit_log("delete_knowledge", resource_type="document", resource_id=id)

    ok = await pipeline_delete_knowledge(id)
    if not ok:
        return json.dumps({"error": f"Failed to delete document: {id}"})

    return json.dumps({"status": "deleted", "id": id})


@mcp.tool()
async def reindex_knowledge(path: Optional[str] = None) -> str:
    """
    Trigger a full re-ingestion of all knowledge files.
    Use after adding new files to the knowledge/, synapses/, or legacy compatibility directories.
    Optionally provide a specific repo path; defaults to KNOWLEDGE_REPO_PATH env var.
    """
    await audit_log("reindex_knowledge", details={"path": path})
    stats = await run_ingestion(repo_path=path)
    logger.info(f"reindex_knowledge: {stats}")
    return json.dumps({"status": "complete", **stats})


@mcp.tool()
async def get_synapse(name: str) -> str:
    """
    Retrieve a synapse bundle by name.
    This is an alias for get_context_pack using the new synapse terminology.
    """
    return await get_context_pack(name)


@mcp.tool()
async def get_skill(id: str) -> str:
    """
    Retrieve a skill by its ID.
    Returns name, description, step-by-step instructions, triggers, and dependencies.
    """
    if not id or not isinstance(id, str):
        raise ValueError("id must be a non-empty string")

    await audit_log("get_skill", resource_type="skill", resource_id=id)

    skill = await db_get_skill(id)
    if skill is None:
        return json.dumps({"error": f"Skill not found: {id}"})

    return json.dumps(skill, default=str)


@mcp.tool()
async def list_skills(context: Optional[str] = None) -> str:
    """
    List all skills, optionally filtered by context tags.
    Skills marked needs_refresh=true have pending knowledge updates.
    context: optional tag to filter skills (e.g. 'auth', 'backend')
    """
    await audit_log("list_skills", details={"context": context})

    filters = {"tags": [context]} if context else None
    skills = await db_list_skills(filters=filters)

    return json.dumps({"skills": [dict(s) for s in skills], "total": len(skills)}, default=str)


@mcp.tool()
async def upsert_skill(
    id: str,
    name: str,
    description: str,
    instructions: str,
    triggers: Optional[str] = None,
    dependencies: Optional[str] = None,
    metadata: Optional[str] = None,
) -> str:
    """
    Create or update a skill in the shared knowledge base.
    Immediately available to all connected agents.
    triggers: JSON array of trigger phrases (e.g. '["auth failure", "401 error"]')
    dependencies: JSON array of document IDs this skill is based on
    metadata: optional JSON object with additional fields (tags, owner, etc.)
    """
    if not id or not isinstance(id, str):
        raise ValueError("id must be a non-empty string")
    if not name or not isinstance(name, str):
        raise ValueError("name must be a non-empty string")
    if not instructions or not isinstance(instructions, str):
        raise ValueError("instructions must be a non-empty string")

    triggers_list: list = []
    if triggers:
        try:
            triggers_list = json.loads(triggers)
        except json.JSONDecodeError:
            raise ValueError("triggers must be a valid JSON array")

    dependencies_list: list = []
    if dependencies:
        try:
            dependencies_list = json.loads(dependencies)
        except json.JSONDecodeError:
            raise ValueError("dependencies must be a valid JSON array")

    parsed_meta: dict = {}
    if metadata:
        try:
            parsed_meta = json.loads(metadata)
        except json.JSONDecodeError:
            raise ValueError("metadata must be valid JSON")

    await audit_log("upsert_skill", resource_type="skill", resource_id=id)

    await db_upsert_skill(
        id=id,
        name=name,
        description=description,
        instructions=instructions,
        triggers=triggers_list,
        dependencies=dependencies_list,
        metadata=parsed_meta,
    )

    full_content = f"# {name}\n\n{description}\n\n{instructions}"
    doc_meta = {"source": "mcp_direct", "triggers": triggers_list,
                "dependencies": dependencies_list, **parsed_meta}
    await upsert_document(id, "skill", full_content, doc_meta)

    chunks = chunk_text(full_content, id)
    if chunks:
        embeddings = embed_texts_batch([c["content"] for c in chunks])
        await delete_chunks_for_document(id)
        for chunk, embedding in zip(chunks, embeddings):
            chunk_meta = {**chunk["metadata"], "document_type": "skill"}
            if "tags" in parsed_meta:
                chunk_meta["tags"] = parsed_meta["tags"]
            await upsert_chunk(
                id=chunk["id"],
                document_id=id,
                content=chunk["content"],
                embedding=embedding,
                metadata=chunk_meta,
            )

    return json.dumps({"status": "upserted", "id": id, "chunks": len(chunks)})


@mcp.tool()
async def get_rule(id: str) -> str:
    """
    Retrieve a rule by its ID.
    Returns name, description, full content, priority, and applicable contexts.
    """
    if not id or not isinstance(id, str):
        raise ValueError("id must be a non-empty string")

    await audit_log("get_rule", resource_type="rule", resource_id=id)

    rule = await db_get_rule(id)
    if rule is None:
        return json.dumps({"error": f"Rule not found: {id}"})

    return json.dumps(rule, default=str)


@mcp.tool()
async def list_rules(context: Optional[str] = None) -> str:
    """
    List all rules ordered by priority (highest first).
    context: optional context tag to filter rules (e.g. 'backend', 'api').
              Rules with applies_to=['all'] always appear.
    """
    await audit_log("list_rules", details={"context": context})

    rules = await db_list_rules(context=context)
    return json.dumps({"rules": [dict(r) for r in rules], "total": len(rules)}, default=str)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
