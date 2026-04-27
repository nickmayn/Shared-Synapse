from typing import List, Optional

from .chroma_utils import (
    add_tag_flags,
    compact_metadata,
    decode_json,
    encode_json,
    iter_collection_rows,
    now_iso,
    slugify_token,
)
from .connection import get_collection


async def upsert_skill(
    id: str,
    name: str,
    description: str,
    instructions: str,
    triggers: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
    metadata: Optional[dict] = None,
) -> None:
    collection = await get_collection("skills")
    existing = await get_skill(id)
    version = 1 if existing is None else int(existing.get("version", 1)) + 1

    skill_metadata = {
        "name": name,
        "description": description,
        "triggers_json": encode_json(triggers or []),
        "dependencies_json": encode_json(dependencies or []),
        "metadata_json": encode_json(metadata or {}),
        "needs_refresh": False,
        "version": version,
        "updated_at": now_iso(),
    }
    tags = (metadata or {}).get("tags", []) if isinstance(metadata, dict) else []
    if isinstance(tags, list):
        add_tag_flags(skill_metadata, [str(tag) for tag in tags])
    for dependency in dependencies or []:
        skill_metadata[f"dependency__{slugify_token(str(dependency))}"] = True

    collection.upsert(
        ids=[id],
        documents=[instructions],
        metadatas=[compact_metadata(skill_metadata)],
    )


async def get_skill(id: str) -> Optional[dict]:
    collection = await get_collection("skills")
    result = collection.get(ids=[id], include=["documents", "metadatas"])
    rows = iter_collection_rows(result)
    if not rows:
        return None
    skill_id, instructions, metadata = rows[0]
    metadata = metadata or {}
    return {
        "id": skill_id,
        "name": metadata.get("name", skill_id),
        "description": metadata.get("description", ""),
        "instructions": instructions or "",
        "triggers": decode_json(metadata.get("triggers_json"), []),
        "dependencies": decode_json(metadata.get("dependencies_json"), []),
        "metadata": decode_json(metadata.get("metadata_json"), {}),
        "needs_refresh": bool(metadata.get("needs_refresh", False)),
        "version": int(metadata.get("version", 1)),
        "updated_at": metadata.get("updated_at"),
    }


async def list_skills(filters: Optional[dict] = None) -> List[dict]:
    collection = await get_collection("skills")
    where = None
    if filters and filters.get("tags"):
        tag_filters = [{f"tag__{tag.lower().replace(' ', '_')}": True} for tag in filters["tags"]]
        if len(tag_filters) == 1:
            where = tag_filters[0]
        elif tag_filters:
            where = {"$or": tag_filters}

    result = collection.get(where=where, include=["documents", "metadatas"])
    skills = [
        {
            "id": skill_id,
            "name": (metadata or {}).get("name", skill_id),
            "description": (metadata or {}).get("description", ""),
            "instructions": instructions or "",
            "triggers": decode_json((metadata or {}).get("triggers_json"), []),
            "dependencies": decode_json((metadata or {}).get("dependencies_json"), []),
            "metadata": decode_json((metadata or {}).get("metadata_json"), {}),
            "needs_refresh": bool((metadata or {}).get("needs_refresh", False)),
            "version": int((metadata or {}).get("version", 1)),
            "updated_at": (metadata or {}).get("updated_at"),
        }
        for skill_id, instructions, metadata in iter_collection_rows(result)
    ]
    return sorted(skills, key=lambda skill: skill.get("updated_at") or "", reverse=True)


async def mark_skills_for_refresh(document_ids: List[str]) -> int:
    """
    Mark skills that depend on any of the given document IDs as needing refresh.
    Returns the number of skills marked.
    """
    if not document_ids:
        return 0
    collection = await get_collection("skills")
    dependency_filters = [{f"dependency__{slugify_token(str(doc_id))}": True} for doc_id in document_ids]
    where = dependency_filters[0] if len(dependency_filters) == 1 else {"$or": dependency_filters}
    result = collection.get(where=where, include=["documents", "metadatas"])

    count = 0
    for skill_id, instructions, metadata in iter_collection_rows(result):
        metadata = dict(metadata or {})
        metadata["needs_refresh"] = True
        metadata["updated_at"] = now_iso()
        collection.upsert(ids=[skill_id], documents=[instructions or ""], metadatas=[compact_metadata(metadata)])
        count += 1
    return count


async def get_skills_needing_refresh() -> List[dict]:
    collection = await get_collection("skills")
    result = collection.get(where={"needs_refresh": True}, include=["documents", "metadatas"])
    skills = []
    for skill_id, instructions, metadata in iter_collection_rows(result):
        metadata = metadata or {}
        skills.append({
            "id": skill_id,
            "name": metadata.get("name", skill_id),
            "description": metadata.get("description", ""),
            "instructions": instructions or "",
            "triggers": decode_json(metadata.get("triggers_json"), []),
            "dependencies": decode_json(metadata.get("dependencies_json"), []),
            "metadata": decode_json(metadata.get("metadata_json"), {}),
            "needs_refresh": True,
            "version": int(metadata.get("version", 1)),
            "updated_at": metadata.get("updated_at"),
        })
    return sorted(skills, key=lambda skill: skill.get("updated_at") or "")


async def clear_refresh_flag(id: str) -> None:
    collection = await get_collection("skills")
    existing = await get_skill(id)
    if existing is None:
        return

    metadata = {
        "name": existing["name"],
        "description": existing["description"],
        "triggers_json": encode_json(existing["triggers"]),
        "dependencies_json": encode_json(existing["dependencies"]),
        "metadata_json": encode_json(existing["metadata"]),
        "needs_refresh": False,
        "version": int(existing.get("version", 1)),
        "updated_at": now_iso(),
    }
    add_tag_flags(metadata, [str(tag) for tag in existing.get("metadata", {}).get("tags", [])])
    for dependency in existing.get("dependencies", []):
        metadata[f"dependency__{slugify_token(str(dependency))}"] = True
    collection.upsert(ids=[id], documents=[existing["instructions"]], metadatas=[compact_metadata(metadata)])
