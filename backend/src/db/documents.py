from typing import Optional

from .chroma_utils import compact_metadata, decode_json, encode_json, iter_collection_rows, now_iso
from .connection import get_collection


async def upsert_document(id: str, type: str, content: str, metadata: dict) -> None:
    collection = await get_collection("documents")
    collection.upsert(
        ids=[id],
        documents=[content],
        metadatas=[compact_metadata({
            "type": type,
            "metadata_json": encode_json(metadata),
            "updated_at": now_iso(),
        })],
    )


async def get_document(id: str) -> Optional[dict]:
    collection = await get_collection("documents")
    result = collection.get(ids=[id], include=["documents", "metadatas"])
    ids = result.get("ids") or []
    if not ids:
        return None

    metadata = (result.get("metadatas") or [{}])[0] or {}
    content = (result.get("documents") or [""])[0]
    return {
        "id": ids[0],
        "type": metadata.get("type", "document"),
        "content": content,
        "metadata": decode_json(metadata.get("metadata_json"), {}),
        "updated_at": metadata.get("updated_at"),
    }


async def list_documents_by_type(type: str) -> list[dict]:
    collection = await get_collection("documents")
    result = collection.get(where={"type": type}, include=["documents", "metadatas"])
    documents = []
    for document_id, content, metadata in iter_collection_rows(result):
        metadata = metadata or {}
        documents.append({
            "id": document_id,
            "type": metadata.get("type", type),
            "content": content or "",
            "metadata": decode_json(metadata.get("metadata_json"), {}),
            "updated_at": metadata.get("updated_at"),
        })
    return sorted(documents, key=lambda document: document.get("updated_at") or "", reverse=True)


async def delete_document(id: str) -> None:
    collection = await get_collection("documents")
    collection.delete(ids=[id])
