import json
import logging
import os
from uuid import uuid4
from typing import Any, Optional

from ..db.connection import get_collection

logger = logging.getLogger(__name__)

# Allowlist of tool IDs that can be executed (empty = all allowed in dev mode)
TOOL_ALLOWLIST: set = set()
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"


def validate_query(query: str) -> str:
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")
    if len(query) > 4096:
        raise ValueError("query exceeds maximum length of 4096 characters")
    return query


def validate_tool_id(tool_id: str) -> str:
    if not isinstance(tool_id, str):
        raise ValueError("tool_id must be a string")
    tool_id = tool_id.strip()
    if not tool_id:
        raise ValueError("tool_id must not be empty")
    if any(c in tool_id for c in ("../", "/", "\\")):
        raise ValueError(f"Invalid tool_id: {tool_id!r}")
    return tool_id


def validate_tool_input(input_data: Any, input_schema: dict) -> None:
    """Basic schema validation (type checks on required fields)."""
    required = input_schema.get("required", [])
    if not isinstance(input_data, dict):
        raise ValueError("Tool input must be a JSON object")
    for field in required:
        if field not in input_data:
            raise ValueError(f"Missing required field: {field}")


def check_tool_allowed(tool_id: str) -> None:
    if not DEV_MODE and TOOL_ALLOWLIST and tool_id not in TOOL_ALLOWLIST:
        raise PermissionError(f"Tool {tool_id!r} is not in the allowlist")


async def audit_log(
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    actor: Optional[str] = "agent",
    details: Optional[dict] = None,
) -> None:
    try:
        collection = await get_collection("audit_log")
        metadata = {
            "action": action,
            "actor": actor or "agent",
        }
        if resource_type is not None:
            metadata["resource_type"] = resource_type
        if resource_id is not None:
            metadata["resource_id"] = resource_id

        collection.add(
            ids=[uuid4().hex],
            documents=[json.dumps(details or {})],
            metadatas=[metadata],
        )
    except Exception as e:
        logger.warning(f"Audit log failed: {e}")
