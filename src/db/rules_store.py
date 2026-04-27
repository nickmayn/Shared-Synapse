import json
from typing import List, Optional

from .connection import get_pool


async def upsert_rule(
    id: str,
    name: str,
    description: str,
    content: str,
    priority: int = 0,
    applies_to: Optional[List[str]] = None,
    metadata: Optional[dict] = None,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO rules
              (id, name, description, content, priority, applies_to, metadata, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            ON CONFLICT (id) DO UPDATE
              SET name = EXCLUDED.name,
                  description = EXCLUDED.description,
                  content = EXCLUDED.content,
                  priority = EXCLUDED.priority,
                  applies_to = EXCLUDED.applies_to,
                  metadata = EXCLUDED.metadata,
                  updated_at = NOW()
            """,
            id,
            name,
            description,
            content,
            priority,
            applies_to or [],
            json.dumps(metadata or {}),
        )


async def get_rule(id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM rules WHERE id = $1", id)
        if row is None:
            return None
        return dict(row)


async def list_rules(context: Optional[str] = None) -> List[dict]:
    """
    Return rules ordered by priority (highest first).
    If context is provided, return rules where applies_to contains context
    OR where applies_to contains 'all'.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        if context:
            rows = await conn.fetch(
                """
                SELECT * FROM rules
                WHERE applies_to @> ARRAY[$1]::text[]
                   OR applies_to @> ARRAY['all']::text[]
                ORDER BY priority DESC
                """,
                context,
            )
        else:
            rows = await conn.fetch("SELECT * FROM rules ORDER BY priority DESC")
        return [dict(row) for row in rows]
