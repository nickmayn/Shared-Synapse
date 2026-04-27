import json
from typing import List, Optional

from pgvector.asyncpg import register_vector

from .connection import get_pool


async def upsert_chunk(
    id: str,
    document_id: str,
    content: str,
    embedding: List[float],
    metadata: dict,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await register_vector(conn)
        await conn.execute(
            """
            INSERT INTO chunks (id, document_id, content, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO UPDATE
              SET document_id = EXCLUDED.document_id,
                  content = EXCLUDED.content,
                  embedding = EXCLUDED.embedding,
                  metadata = EXCLUDED.metadata
            """,
            id, document_id, content, embedding, json.dumps(metadata)
        )


async def search_chunks(
    query_embedding: List[float],
    top_k: int = 10,
    filters: Optional[dict] = None,
) -> List[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await register_vector(conn)

        where_clauses = []
        params = [query_embedding, top_k]
        param_idx = 3

        if filters:
            if "type" in filters:
                where_clauses.append(f"d.type = ${param_idx}")
                params.append(filters["type"])
                param_idx += 1
            if "tags" in filters:
                # Each tag adds an AND clause: all listed tags must be present
                for tag in filters["tags"]:
                    where_clauses.append(f"c.metadata->'tags' ? ${param_idx}")
                    params.append(tag)
                    param_idx += 1
            if "context_pack" in filters:
                where_clauses.append(f"c.metadata->>'context_pack' = ${param_idx}")
                params.append(filters["context_pack"])
                param_idx += 1

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        rows = await conn.fetch(
            f"""
            SELECT c.id, c.document_id, c.content, c.metadata,
                   1 - (c.embedding <=> $1) AS similarity,
                   d.type, d.metadata AS doc_metadata
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            {where_sql}
            ORDER BY c.embedding <=> $1
            LIMIT $2
            """,
            *params
        )
        return [dict(row) for row in rows]


async def delete_chunks_for_document(document_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chunks WHERE document_id = $1", document_id)
