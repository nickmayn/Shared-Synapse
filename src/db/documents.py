import json
from typing import Optional

from .connection import get_pool


async def upsert_document(id: str, type: str, content: str, metadata: dict) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO documents (id, type, content, metadata, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (id) DO UPDATE
              SET type = EXCLUDED.type,
                  content = EXCLUDED.content,
                  metadata = EXCLUDED.metadata,
                  updated_at = NOW()
            """,
            id, type, content, json.dumps(metadata)
        )


async def get_document(id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", id)
        if row is None:
            return None
        return dict(row)


async def delete_document(id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM documents WHERE id = $1", id)
