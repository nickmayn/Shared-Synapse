from typing import Any, Dict, List, Optional
from uuid import uuid4

from .chroma_utils import compact_metadata, iter_collection_rows, now_iso
from .connection import get_collection


async def add_conversation_entry(
    user_id: str,
    role: str,
    content: str,
    conversation_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """
    Append an entry to a user's conversation history.
    role: 'user' or 'agent'
    conversation_id: named topic context (like a room in a memory palace);
                     a new UUID is generated if omitted.
    session_id: temporal grouping within a conversation (like a visit to a room);
                a new UUID is generated if omitted.
    Returns the entry ID.
    """
    entry_id = uuid4().hex
    resolved_conversation = conversation_id or uuid4().hex
    resolved_session = session_id or uuid4().hex
    collection = await get_collection("conversations")
    collection.add(
        ids=[entry_id],
        documents=[content],
        metadatas=[compact_metadata({
            "user_id": user_id,
            "role": role,
            "conversation_id": resolved_conversation,
            "session_id": resolved_session,
            "created_at": now_iso(),
        })],
    )
    return entry_id


async def get_conversation_tree(
    user_id: str,
    conversation_id: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Dict[str, Any]]:
    """
    Retrieve conversation entries as a nested memory palace structure.
    Returns: { conversations: { conv_id: { sessions: { sess_id: { entries: [...] } } } } }
    Entries are ordered chronologically (oldest first) within each session.
    If conversation_id is given, only that conversation is returned.
    """
    collection = await get_collection("conversations")

    if conversation_id:
        where: dict = {
            "$and": [
                {"user_id": user_id},
                {"conversation_id": conversation_id},
            ]
        }
    else:
        where = {"user_id": user_id}

    result = collection.get(where=where, include=["documents", "metadatas"])

    # Build the nested tree: conversations → sessions → entries
    tree: Dict[str, Dict[str, Any]] = {}
    for entry_id, content, metadata in iter_collection_rows(result):
        metadata = metadata or {}
        cid = metadata.get("conversation_id") or ""
        sid = metadata.get("session_id") or ""
        if not cid or not sid:
            # Skip entries that are missing their context IDs (data integrity guard)
            continue
        entry = {
            "id": entry_id,
            "user_id": metadata.get("user_id", user_id),
            "role": metadata.get("role", "user"),
            "content": content or "",
            "created_at": metadata.get("created_at"),
        }

        if cid not in tree:
            tree[cid] = {"conversation_id": cid, "user_id": user_id, "sessions": {}}
        if sid not in tree[cid]["sessions"]:
            tree[cid]["sessions"][sid] = {"session_id": sid, "entries": []}
        tree[cid]["sessions"][sid]["entries"].append(entry)

    # Sort entries within each session chronologically; enforce per-session limit
    for cid, conv in tree.items():
        for sid, session in conv["sessions"].items():
            session["entries"].sort(key=lambda e: e.get("created_at") or "")
            session["entries"] = session["entries"][-limit:]
            session["entry_count"] = len(session["entries"])
            timestamps = [e["created_at"] for e in session["entries"] if e.get("created_at")]
            session["started_at"] = timestamps[0] if timestamps else None
            session["latest_at"] = timestamps[-1] if timestamps else None

    return tree


async def list_conversations(user_id: str) -> List[dict]:
    """
    List all conversations for a user (memory palace rooms).
    Returns conversation summaries with session count, total entry count,
    and latest timestamp, ordered newest first.
    """
    collection = await get_collection("conversations")
    result = collection.get(where={"user_id": user_id}, include=["metadatas"])

    conversations: dict[str, dict] = {}
    for _, _, metadata in iter_collection_rows(result):
        metadata = metadata or {}
        cid = metadata.get("conversation_id", "")
        if not cid:
            continue
        sid = metadata.get("session_id", "")
        if cid not in conversations:
            conversations[cid] = {
                "conversation_id": cid,
                "user_id": user_id,
                "session_ids": set(),
                "total_entries": 0,
                "latest_at": None,
            }
        conversations[cid]["total_entries"] += 1
        if sid:
            conversations[cid]["session_ids"].add(sid)
        ts = metadata.get("created_at")
        if ts and (conversations[cid]["latest_at"] is None
                   or ts > conversations[cid]["latest_at"]):
            conversations[cid]["latest_at"] = ts

    summaries = []
    for cid, conv in conversations.items():
        summaries.append({
            "conversation_id": cid,
            "user_id": user_id,
            "session_count": len(conv["session_ids"]),
            "total_entries": conv["total_entries"],
            "latest_at": conv["latest_at"],
        })
    return sorted(summaries, key=lambda c: c.get("latest_at") or "", reverse=True)

