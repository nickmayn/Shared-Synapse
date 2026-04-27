import json
from typing import List, Optional

from .connection import get_pool


async def upsert_skill(
    id: str,
    name: str,
    description: str,
    instructions: str,
    triggers: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
    metadata: Optional[dict] = None,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO skills
              (id, name, description, instructions, triggers, dependencies, metadata, needs_refresh, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, FALSE, NOW())
            ON CONFLICT (id) DO UPDATE
              SET name = EXCLUDED.name,
                  description = EXCLUDED.description,
                  instructions = EXCLUDED.instructions,
                  triggers = EXCLUDED.triggers,
                  dependencies = EXCLUDED.dependencies,
                  metadata = EXCLUDED.metadata,
                  needs_refresh = FALSE,
                  version = skills.version + 1,
                  updated_at = NOW()
            """,
            id,
            name,
            description,
            instructions,
            triggers or [],
            dependencies or [],
            json.dumps(metadata or {}),
        )


async def get_skill(id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM skills WHERE id = $1", id)
        if row is None:
            return None
        return dict(row)


async def list_skills(filters: Optional[dict] = None) -> List[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if filters and "tags" in filters:
            rows = await conn.fetch(
                "SELECT * FROM skills WHERE metadata->'tags' ?| $1 ORDER BY updated_at DESC",
                filters["tags"],
            )
        else:
            rows = await conn.fetch("SELECT * FROM skills ORDER BY updated_at DESC")
        return [dict(row) for row in rows]


async def mark_skills_for_refresh(document_ids: List[str]) -> int:
    """
    Mark skills that depend on any of the given document IDs as needing refresh.
    Returns the number of skills marked.
    """
    if not document_ids:
        return 0
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE skills SET needs_refresh = TRUE WHERE dependencies && $1::text[]",
            document_ids,
        )
        # result is a string like "UPDATE 3"
        try:
            return int(result.split()[-1])
        except (IndexError, ValueError):
            return 0


async def get_skills_needing_refresh() -> List[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM skills WHERE needs_refresh = TRUE ORDER BY updated_at"
        )
        return [dict(row) for row in rows]


async def clear_refresh_flag(id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE skills SET needs_refresh = FALSE WHERE id = $1", id
        )
