"""
YAML-backed synapse (neuron activation bundle) store.

Synapses live as YAML files under the `synapses/` directory.
Active/inactive state for optional synapses is tracked in a lightweight
SQLite table alongside the users database so it survives restarts.
"""
import os
import sqlite3
import threading
from pathlib import Path
from typing import Optional

import yaml

from .chroma_utils import now_iso

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SYNAPSES_DIR_ENV = "SYNAPSES_DIR"
_DB_PATH_ENV = "USERS_DB_PATH"


def _synapses_dir() -> Path:
    default = Path(__file__).resolve().parents[4] / "synapses"
    return Path(os.getenv(_SYNAPSES_DIR_ENV, str(default)))


_LOCK = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    with _LOCK:
        if _conn is None:
            from .users_store import _db_path
            _conn = sqlite3.connect(_db_path(), check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS active_synapses (
                    name TEXT PRIMARY KEY,
                    activated_at TEXT NOT NULL
                );
                """
            )
            _conn.commit()
        return _conn


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def _synapse_path(name: str) -> Path:
    safe = name.replace("..", "").replace("/", "").replace("\\", "")
    return _synapses_dir() / f"{safe}.yaml"


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _save_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_synapses() -> list[dict]:
    """Return all synapse definitions from the synapses/ directory."""
    directory = _synapses_dir()
    if not directory.exists():
        return []
    active_names = _active_synapse_names()
    synapses = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            data = _load_yaml(path)
        except Exception:
            continue
        name = data.get("name") or path.stem
        synapses.append({
            "name": name,
            "description": data.get("description", ""),
            "activation": data.get("activation", "optional"),
            "includes": data.get("includes", []),
            "tags": data.get("tags", []),
            "common_tasks": data.get("common_tasks", []),
            "recommended_tools": data.get("recommended_tools", []),
            "extends": data.get("extends", []),
            "active": data.get("activation") == "core" or name in active_names,
        })
    return synapses


def get_synapse(name: str) -> Optional[dict]:
    """Return a single synapse definition, or None if not found."""
    path = _synapse_path(name)
    if not path.exists():
        return None
    try:
        data = _load_yaml(path)
    except Exception:
        return None
    active_names = _active_synapse_names()
    synapse_name = data.get("name") or name
    return {
        "name": synapse_name,
        "description": data.get("description", ""),
        "activation": data.get("activation", "optional"),
        "includes": data.get("includes", []),
        "tags": data.get("tags", []),
        "common_tasks": data.get("common_tasks", []),
        "recommended_tools": data.get("recommended_tools", []),
        "extends": data.get("extends", []),
        "active": data.get("activation") == "core" or synapse_name in active_names,
    }


def upsert_synapse(
    name: str,
    description: str,
    activation: str = "optional",
    includes: Optional[list] = None,
    tags: Optional[list] = None,
    common_tasks: Optional[list] = None,
    recommended_tools: Optional[list] = None,
    extends: Optional[list] = None,
) -> dict:
    """Create or update a synapse YAML file. Returns the saved definition."""
    if activation not in ("core", "optional"):
        raise ValueError("activation must be 'core' or 'optional'")
    data: dict = {
        "name": name,
        "description": description,
        "activation": activation,
    }
    if extends:
        data["extends"] = extends
    if includes:
        data["includes"] = includes
    if common_tasks:
        data["common_tasks"] = common_tasks
    if recommended_tools:
        data["recommended_tools"] = recommended_tools
    if tags:
        data["tags"] = tags
    _save_yaml(_synapse_path(name), data)
    return get_synapse(name)  # type: ignore[return-value]


def delete_synapse(name: str) -> bool:
    """Delete a synapse YAML file. Returns True if deleted, False if not found."""
    path = _synapse_path(name)
    if not path.exists():
        return False
    path.unlink()
    # Also deactivate if it was active
    deactivate_synapse(name)
    return True


# ---------------------------------------------------------------------------
# Activation tracking
# ---------------------------------------------------------------------------

def _active_synapse_names() -> set:
    conn = _get_conn()
    rows = conn.execute("SELECT name FROM active_synapses").fetchall()
    return {r["name"] for r in rows}


def activate_synapse(name: str) -> bool:
    """Mark an optional synapse as active. Returns True if the file exists."""
    if get_synapse(name) is None:
        return False
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO active_synapses (name, activated_at) VALUES (?, ?)",
        (name, now_iso()),
    )
    conn.commit()
    return True


def deactivate_synapse(name: str) -> None:
    """Remove an optional synapse from the active set."""
    conn = _get_conn()
    conn.execute("DELETE FROM active_synapses WHERE name = ?", (name,))
    conn.commit()
