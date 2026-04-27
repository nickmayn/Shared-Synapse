from typing import List, Optional

from .chroma_utils import compact_metadata, decode_json, encode_json, iter_collection_rows, now_iso, slugify_token
from .connection import get_collection


async def upsert_rule(
    id: str,
    name: str,
    description: str,
    content: str,
    priority: int = 0,
    applies_to: Optional[List[str]] = None,
    metadata: Optional[dict] = None,
) -> None:
    collection = await get_collection("rules")
    rule_metadata = {
        "name": name,
        "description": description,
        "priority": int(priority),
        "applies_to_json": encode_json(applies_to or []),
        "metadata_json": encode_json(metadata or {}),
        "updated_at": now_iso(),
    }
    for scope in applies_to or []:
        rule_metadata[f"applies_to__{slugify_token(str(scope))}"] = True

    collection.upsert(
        ids=[id],
        documents=[content],
        metadatas=[compact_metadata(rule_metadata)],
    )


async def get_rule(id: str) -> Optional[dict]:
    collection = await get_collection("rules")
    result = collection.get(ids=[id], include=["documents", "metadatas"])
    rows = iter_collection_rows(result)
    if not rows:
        return None
    rule_id, content, metadata = rows[0]
    metadata = metadata or {}
    return {
        "id": rule_id,
        "name": metadata.get("name", rule_id),
        "description": metadata.get("description", ""),
        "content": content or "",
        "priority": int(metadata.get("priority", 0)),
        "applies_to": decode_json(metadata.get("applies_to_json"), []),
        "metadata": decode_json(metadata.get("metadata_json"), {}),
        "updated_at": metadata.get("updated_at"),
    }


async def list_rules(context: Optional[str] = None) -> List[dict]:
    """
    Return rules ordered by priority (highest first).
    If context is provided, return rules where applies_to contains context
    OR where applies_to contains 'all'.
    """
    collection = await get_collection("rules")
    where = None
    if context:
        context_key = f"applies_to__{slugify_token(context)}"
        where = {"$or": [{context_key: True}, {"applies_to__all": True}]}

    result = collection.get(where=where, include=["documents", "metadatas"])
    rules = []
    for rule_id, content, metadata in iter_collection_rows(result):
        metadata = metadata or {}
        rules.append({
            "id": rule_id,
            "name": metadata.get("name", rule_id),
            "description": metadata.get("description", ""),
            "content": content or "",
            "priority": int(metadata.get("priority", 0)),
            "applies_to": decode_json(metadata.get("applies_to_json"), []),
            "metadata": decode_json(metadata.get("metadata_json"), {}),
            "updated_at": metadata.get("updated_at"),
        })
    return sorted(rules, key=lambda rule: int(rule.get("priority", 0)), reverse=True)
