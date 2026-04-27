import json
from typing import List, Optional


def rank_results(
    results: List[dict],
    query: str,
    filters: Optional[dict] = None,
    top_k: int = 10,
) -> List[dict]:
    """
    Re-rank results combining:
    - Vector similarity score
    - Metadata relevance (tag matching, type boost)
    Returns top_k results sorted by combined score.
    """
    query_terms = set(query.lower().split())
    filter_tags = set(filters.get("tags", [])) if filters else set()

    for result in results:
        base_score = result["similarity"]

        doc_meta = result.get("document_metadata", {})
        chunk_meta = result.get("chunk_metadata", {})

        if isinstance(doc_meta, str):
            try:
                doc_meta = json.loads(doc_meta)
            except Exception:
                doc_meta = {}
        if isinstance(chunk_meta, str):
            try:
                chunk_meta = json.loads(chunk_meta)
            except Exception:
                chunk_meta = {}

        doc_tags: set = set()
        for meta in (doc_meta, chunk_meta):
            tags = meta.get("tags", [])
            if isinstance(tags, list):
                doc_tags.update(t.lower() for t in tags)

        tag_boost = 0.05 * len(doc_tags & filter_tags) if filter_tags else 0.0

        content = result.get("chunk_content", "").lower()
        term_hits = sum(1 for t in query_terms if t in content)
        term_boost = 0.02 * term_hits

        result["score"] = base_score + tag_boost + term_boost

    ranked = sorted(results, key=lambda r: r["score"], reverse=True)
    return ranked[:top_k]
