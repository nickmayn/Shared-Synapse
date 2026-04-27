import json
from typing import List, Optional

from .connection import get_pool


async def upsert_tool(
    id: str,
    description: str,
    input_schema: dict,
    output_schema: dict,
    metadata: dict,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO tools (id, description, input_schema, output_schema, metadata)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (id) DO UPDATE
              SET description = EXCLUDED.description,
                  input_schema = EXCLUDED.input_schema,
                  output_schema = EXCLUDED.output_schema,
                  metadata = EXCLUDED.metadata
            """,
            id, description, json.dumps(input_schema), json.dumps(output_schema), json.dumps(metadata)
        )


async def get_tool(id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tools WHERE id = $1", id)
        if row is None:
            return None
        return dict(row)


async def list_tools(filters: Optional[dict] = None) -> List[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if filters and "tags" in filters:
            rows = await conn.fetch(
                "SELECT * FROM tools WHERE metadata->'tags' ?| $1",
                filters["tags"]
            )
        else:
            rows = await conn.fetch("SELECT * FROM tools")
        return [dict(row) for row in rows]
