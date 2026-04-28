from typing import List, Optional
from uuid import uuid4

from .chroma_utils import compact_metadata, iter_collection_rows, now_iso
from .connection import get_collection


async def add_conversation_entry(
    user_id: str,
    role: str,
    content: str,
    session_id: Optional[str] = None,
) -> str:
    """
    Append an entry to a user's conversation history.
    role: 'user' or 'agent'
    session_id: optional grouping key; a new UUID is generated if omitted.
    Returns the entry ID.
    """
    entry_id = uuid4().hex
    resolved_session = session_id or uuid4().hex
    collection = await get_collection("conversations")
    collection.add(
        ids=[entry_id],
        documents=[content],
        metadatas=[compact_metadata({
            "user_id": user_id,
            "role": role,
            "session_id": resolved_session,
            "created_at": now_iso(),
        })],
    )
    return entry_id


async def get_conversation(
    user_id: str,
    session_id: Optional[str] = None,
    limit: int = 100,
) -> List[dict]:
    """
    Retrieve conversation entries for a user, optionally scoped to a session.
    Returns entries in chronological order (oldest first).
    """
    collection = await get_collection("conversations")
    where: dict = {"user_id": user_id}
    if session_id:
        where = {"$and": [{"user_id": user_id}, {"session_id": session_id}]}

    result = collection.get(where=where, include=["documents", "metadatas"])
    entries = []
    for entry_id, content, metadata in iter_collection_rows(result):
        metadata = metadata or {}
        entries.append({
            "id": entry_id,
            "user_id": metadata.get("user_id", user_id),
            "role": metadata.get("role", "user"),
            "content": content or "",
            "session_id": metadata.get("session_id", ""),
            "created_at": metadata.get("created_at"),
        })
    entries.sort(key=lambda e: e.get("created_at") or "")
    return entries[-limit:]


async def list_conversation_sessions(user_id: str) -> List[dict]:
    """
    List all unique conversation sessions for a user.
    Returns session summaries with entry count and latest timestamp.
    """
    collection = await get_collection("conversations")
    result = collection.get(where={"user_id": user_id}, include=["metadatas"])
    sessions: dict[str, dict] = {}
    for _, _, metadata in iter_collection_rows(result):
        metadata = metadata or {}
        sid = metadata.get("session_id", "")
        if not sid:
            continue
        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "user_id": user_id,
                "entry_count": 0,
                "latest_at": None,
            }
        sessions[sid]["entry_count"] += 1
        ts = metadata.get("created_at")
        if ts and (sessions[sid]["latest_at"] is None or ts > sessions[sid]["latest_at"]):
            sessions[sid]["latest_at"] = ts
    return sorted(sessions.values(), key=lambda s: s.get("latest_at") or "", reverse=True)
