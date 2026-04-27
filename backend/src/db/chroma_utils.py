import json
import re
from datetime import datetime, UTC
from typing import Any, Optional


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def encode_json(value: Any) -> str:
    return json.dumps(value if value is not None else {})


def decode_json(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def slugify_token(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "value"


def compact_metadata(metadata: dict) -> dict:
    return {key: value for key, value in metadata.items() if value is not None}


def add_tag_flags(target: dict, tags: list[str]) -> None:
    for tag in tags:
        target[f"tag__{slugify_token(str(tag))}"] = True


def build_or_filter(clauses: list[dict]) -> Optional[dict]:
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$or": clauses}


def build_and_filter(clauses: list[dict]) -> Optional[dict]:
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def iter_collection_rows(result: dict) -> list[tuple[str, Optional[str], Optional[dict]]]:
    ids = result.get("ids") or []
    documents = result.get("documents") or [None] * len(ids)
    metadatas = result.get("metadatas") or [None] * len(ids)
    return list(zip(ids, documents, metadatas))