from typing import List, Optional

from .chroma_utils import compact_metadata, decode_json, encode_json, iter_collection_rows, now_iso
from .connection import get_collection

NOMINATION_STATUSES = {"pending", "approved", "rejected"}


async def nominate_knowledge(
    id: str,
    nominator: str,
    type: str,
    content: str,
    metadata: Optional[dict] = None,
) -> None:
    collection = await get_collection("nominations")
    nomination_metadata = {
        "nominator": nominator,
        "type": type,
        "status": "pending",
        "upvotes": 0,
        "downvotes": 0,
        "voters_json": encode_json([]),
        "metadata_json": encode_json(metadata or {}),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    collection.upsert(
        ids=[id],
        documents=[content],
        metadatas=[compact_metadata(nomination_metadata)],
    )


async def get_nomination(id: str) -> Optional[dict]:
    collection = await get_collection("nominations")
    result = collection.get(ids=[id], include=["documents", "metadatas"])
    rows = iter_collection_rows(result)
    if not rows:
        return None
    nom_id, content, metadata = rows[0]
    metadata = metadata or {}
    return {
        "id": nom_id,
        "nominator": metadata.get("nominator", ""),
        "type": metadata.get("type", "document"),
        "content": content or "",
        "status": metadata.get("status", "pending"),
        "upvotes": int(metadata.get("upvotes", 0)),
        "downvotes": int(metadata.get("downvotes", 0)),
        "voters": decode_json(metadata.get("voters_json"), []),
        "metadata": decode_json(metadata.get("metadata_json"), {}),
        "created_at": metadata.get("created_at"),
        "updated_at": metadata.get("updated_at"),
    }


async def list_nominations(status: Optional[str] = None) -> List[dict]:
    collection = await get_collection("nominations")
    where = {"status": status} if status else None
    result = collection.get(where=where, include=["documents", "metadatas"])
    nominations = []
    for nom_id, content, metadata in iter_collection_rows(result):
        metadata = metadata or {}
        nominations.append({
            "id": nom_id,
            "nominator": metadata.get("nominator", ""),
            "type": metadata.get("type", "document"),
            "content": content or "",
            "status": metadata.get("status", "pending"),
            "upvotes": int(metadata.get("upvotes", 0)),
            "downvotes": int(metadata.get("downvotes", 0)),
            "voters": decode_json(metadata.get("voters_json"), []),
            "metadata": decode_json(metadata.get("metadata_json"), {}),
            "created_at": metadata.get("created_at"),
            "updated_at": metadata.get("updated_at"),
        })
    return sorted(nominations, key=lambda n: n.get("created_at") or "", reverse=True)


async def vote_nomination(nomination_id: str, voter: str, vote: str) -> Optional[dict]:
    """
    Cast a vote on a nomination.
    vote: 'up' or 'down'
    Returns the updated nomination, or None if not found.
    Each voter may only vote once; subsequent calls replace their previous vote.
    """
    nomination = await get_nomination(nomination_id)
    if nomination is None:
        return None

    voters: list = list(nomination["voters"])

    existing = next((v for v in voters if v["voter"] == voter), None)
    if existing:
        old_vote = existing["vote"]
        if old_vote == vote:
            return nomination
        existing["vote"] = vote
        if old_vote == "up":
            nomination["upvotes"] = max(0, nomination["upvotes"] - 1)
        else:
            nomination["downvotes"] = max(0, nomination["downvotes"] - 1)
    else:
        voters.append({"voter": voter, "vote": vote})

    if vote == "up":
        nomination["upvotes"] += 1
    else:
        nomination["downvotes"] += 1

    collection = await get_collection("nominations")
    collection.upsert(
        ids=[nomination_id],
        documents=[nomination["content"]],
        metadatas=[compact_metadata({
            "nominator": nomination["nominator"],
            "type": nomination["type"],
            "status": nomination["status"],
            "upvotes": nomination["upvotes"],
            "downvotes": nomination["downvotes"],
            "voters_json": encode_json(voters),
            "metadata_json": encode_json(nomination["metadata"]),
            "created_at": nomination["created_at"],
            "updated_at": now_iso(),
        })],
    )

    return await get_nomination(nomination_id)


async def update_nomination_status(nomination_id: str, status: str) -> Optional[dict]:
    """Update the status of a nomination to 'approved' or 'rejected'."""
    if status not in NOMINATION_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(NOMINATION_STATUSES))}")

    nomination = await get_nomination(nomination_id)
    if nomination is None:
        return None

    collection = await get_collection("nominations")
    collection.upsert(
        ids=[nomination_id],
        documents=[nomination["content"]],
        metadatas=[compact_metadata({
            "nominator": nomination["nominator"],
            "type": nomination["type"],
            "status": status,
            "upvotes": nomination["upvotes"],
            "downvotes": nomination["downvotes"],
            "voters_json": encode_json(nomination["voters"]),
            "metadata_json": encode_json(nomination["metadata"]),
            "created_at": nomination["created_at"],
            "updated_at": now_iso(),
        })],
    )

    return await get_nomination(nomination_id)
