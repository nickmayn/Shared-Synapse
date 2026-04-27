"""
Shared Synapse MCP Server

Exposes:
  - search_knowledge
  - get_document
  - get_context_pack
  - list_tools
  - execute_tool
"""
import json
import logging
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..db import get_document as db_get_document
from ..db.chunks import search_chunks
from ..db.tools_store import get_tool, list_tools as db_list_tools
from ..ingestion.embeddings import embed_text
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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
