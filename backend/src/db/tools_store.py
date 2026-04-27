from typing import List, Optional

from .chroma_utils import add_tag_flags, compact_metadata, decode_json, encode_json, iter_collection_rows
from .connection import get_collection


async def upsert_tool(
    id: str,
    description: str,
    input_schema: dict,
    output_schema: dict,
    metadata: dict,
) -> None:
    collection = await get_collection("tools")
    tool_metadata = {
        "input_schema_json": encode_json(input_schema),
        "output_schema_json": encode_json(output_schema),
        "metadata_json": encode_json(metadata),
    }
    tags = metadata.get("tags", []) if isinstance(metadata, dict) else []
    if isinstance(tags, list):
        add_tag_flags(tool_metadata, [str(tag) for tag in tags])

    collection.upsert(
        ids=[id],
        documents=[description],
        metadatas=[compact_metadata(tool_metadata)],
    )


async def get_tool(id: str) -> Optional[dict]:
    collection = await get_collection("tools")
    result = collection.get(ids=[id], include=["documents", "metadatas"])
    rows = iter_collection_rows(result)
    if not rows:
        return None
    tool_id, description, metadata = rows[0]
    metadata = metadata or {}
    return {
        "id": tool_id,
        "description": description or "",
        "input_schema": decode_json(metadata.get("input_schema_json"), {}),
        "output_schema": decode_json(metadata.get("output_schema_json"), {}),
        "metadata": decode_json(metadata.get("metadata_json"), {}),
    }


async def list_tools(filters: Optional[dict] = None) -> List[dict]:
    collection = await get_collection("tools")
    where = None
    if filters and filters.get("tags"):
        tag_filters = [{f"tag__{tag.lower().replace(' ', '_')}": True} for tag in filters["tags"]]
        if len(tag_filters) == 1:
            where = tag_filters[0]
        elif tag_filters:
            where = {"$or": tag_filters}

    result = collection.get(where=where, include=["documents", "metadatas"])
    tools = []
    for tool_id, description, metadata in iter_collection_rows(result):
        metadata = metadata or {}
        tools.append({
            "id": tool_id,
            "description": description or "",
            "input_schema": decode_json(metadata.get("input_schema_json"), {}),
            "output_schema": decode_json(metadata.get("output_schema_json"), {}),
            "metadata": decode_json(metadata.get("metadata_json"), {}),
        })
    return tools
