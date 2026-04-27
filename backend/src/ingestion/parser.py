import json
from pathlib import Path
from typing import Optional

import frontmatter
import yaml

# All valid document types recognised by the ingestion pipeline.
# Keep this in sync with the path-based type detection in _parse_markdown.
VALID_DOCUMENT_TYPES: frozenset = frozenset({
    "concept", "decision", "design",
    "skill", "rule",
    "context_pack", "tool", "document",
})


def parse_file(path: str) -> Optional[dict]:
    """
    Parse a file and return a dict with keys: id, type, content, metadata.
    Returns None if the file type is unsupported.
    """
    p = Path(path)
    ext = p.suffix.lower()
    rel = str(p)

    if ext in (".md", ".markdown"):
        return _parse_markdown(p, rel)
    elif ext in (".yaml", ".yml"):
        return _parse_yaml(p, rel)
    elif ext == ".json":
        return _parse_json(p, rel)
    return None


def _parse_markdown(p: Path, rel: str) -> dict:
    post = frontmatter.load(str(p))
    meta = dict(post.metadata)
    meta.setdefault("source_path", rel)

    if "/knowledge/concepts/" in rel:
        doc_type = "concept"
    elif "/knowledge/systems/" in rel:
        # Legacy folder retained for backward compatibility.
        doc_type = "concept"
    elif "/knowledge/decisions/" in rel:
        doc_type = "decision"
    elif "/knowledge/designs/" in rel:
        doc_type = "design"
    elif "/knowledge/skills/" in rel:
        doc_type = "skill"
    elif "/knowledge/playbooks/" in rel:
        # Legacy workflow docs now live under skills.
        doc_type = "skill"
    elif "/knowledge/rules/" in rel:
        doc_type = "rule"
    elif "/knowledge/tools/" in rel:
        doc_type = "tool"
    elif "/synapses/" in rel:
        doc_type = "context_pack"
    elif "/context-packs/" in rel:
        doc_type = "context_pack"
    else:
        doc_type = "document"

    doc_id = meta.get("id", _path_to_id(p))
    return {
        "id": doc_id,
        "type": doc_type,
        "content": post.content,
        "metadata": meta,
    }


def _parse_yaml(p: Path, rel: str) -> Optional[dict]:
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return None

    doc_id = data.get("name", _path_to_id(p))
    content = yaml.dump(data, default_flow_style=False)
    return {
        "id": doc_id,
        "type": "context_pack",
        "content": content,
        "metadata": {"source_path": rel, **{k: v for k, v in data.items() if k != "content"}},
    }


def _parse_json(p: Path, rel: str) -> Optional[dict]:
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return None

    doc_id = data.get("id", _path_to_id(p))
    content = json.dumps(data, indent=2)
    return {
        "id": doc_id,
        "type": "tool",
        "content": content,
        "metadata": {"source_path": rel, **{k: v for k, v in data.items() if k not in ("content", "id")}},
    }


def _path_to_id(p: Path) -> str:
    return p.stem.replace(" ", "-").lower()
