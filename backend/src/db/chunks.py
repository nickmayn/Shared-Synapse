from typing import List, Optional

from .chroma_utils import (
    add_tag_flags,
    build_and_filter,
    build_or_filter,
    compact_metadata,
    decode_json,
    encode_json,
)
from .connection import get_collection


async def upsert_chunk(
    id: str,
    document_id: str,
    content: str,
    embedding: List[float],
    metadata: dict,
) -> None:
    collection = await get_collection("chunks")
    chunk_metadata = {
        "document_id": document_id,
        "document_type": metadata.get("document_type", "document"),
        "metadata_json": encode_json(metadata),
    }
    tags = metadata.get("tags", [])
    if isinstance(tags, list):
        add_tag_flags(chunk_metadata, [str(tag) for tag in tags])
    context_pack = metadata.get("context_pack") or metadata.get("synapse")
    if context_pack:
        chunk_metadata["context_pack"] = str(context_pack)

    collection.upsert(
        ids=[id],
        documents=[content],
        embeddings=[embedding],
        metadatas=[compact_metadata(chunk_metadata)],
    )


async def search_chunks(
    query_embedding: List[float],
    top_k: int = 10,
    filters: Optional[dict] = None,
) -> List[dict]:
    collection = await get_collection("chunks")

    clauses: list[dict] = []
    if filters:
        if filters.get("type"):
            clauses.append({"document_type": filters["type"]})
        if filters.get("context_pack"):
            clauses.append({"context_pack": filters["context_pack"]})
        if filters.get("tags"):
            tag_filter = build_or_filter([
                {f"tag__{tag.lower().replace(' ', '_')}": True}
                for tag in filters["tags"]
            ])
            if tag_filter:
                clauses.append(tag_filter)

    where = build_and_filter(clauses)
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    rows = []
    for chunk_id, content, metadata, distance in zip(ids, documents, metadatas, distances):
        metadata = metadata or {}
        rows.append({
            "id": chunk_id,
            "document_id": metadata.get("document_id", ""),
            "content": content,
            "metadata": decode_json(metadata.get("metadata_json"), {}),
            "similarity": 1 - float(distance),
            "type": metadata.get("document_type", "document"),
            "doc_metadata": {},
        })
    return rows


async def delete_chunks_for_document(document_id: str) -> None:
    collection = await get_collection("chunks")
    collection.delete(where={"document_id": document_id})
