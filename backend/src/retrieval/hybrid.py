import logging
from typing import List, Optional

from ..db import search_chunks, get_document
from ..ingestion.embeddings import embed_text

logger = logging.getLogger(__name__)


async def hybrid_search(
    query: str,
    filters: Optional[dict] = None,
    top_k: int = 10,
) -> List[dict]:
    """
    Perform hybrid retrieval:
    1. Embed query
    2. Vector search with optional structured filters
    3. Attach parent document metadata
    Returns list of result dicts with chunk + document info.
    """
    query_embedding = embed_text(query)
    raw_results = await search_chunks(query_embedding, top_k=top_k * 2, filters=filters)

    enriched = []
    seen_docs: dict = {}

    for row in raw_results:
        doc_id = row["document_id"]
        if doc_id not in seen_docs:
            doc = await get_document(doc_id)
            seen_docs[doc_id] = doc
        else:
            doc = seen_docs[doc_id]

        enriched.append({
            "chunk_id": row["id"],
            "document_id": doc_id,
            "chunk_content": row["content"],
            "chunk_metadata": row["metadata"],
            "similarity": float(row["similarity"]),
            "document_type": row.get("type", ""),
            "document_metadata": doc.get("metadata", {}) if doc else {},
        })

    return enriched
