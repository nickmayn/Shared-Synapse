"""
Config management for the Synapse CLI.

Config is stored at ~/.synapse/config.toml:

[default]
server_url = "http://localhost:8000"
access_token = "..."
refresh_token = "..."
username = "..."
"""
import os
from pathlib import Path
from typing import Optional

try:
    import toml
except ImportError:
    import tomllib as toml  # type: ignore[no-redef]

CONFIG_DIR = Path.home() / ".synapse"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def _load() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "rb") as fh:
            return toml.load(fh)
    except Exception:
        return {}


def _save(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        toml.dump(data, fh)
    # Restrict permissions so only the owner can read credentials
    CONFIG_FILE.chmod(0o600)


def get_profile(profile: str = "default") -> dict:
    return _load().get(profile, {})


def set_profile(values: dict, profile: str = "default") -> None:
    data = _load()
    existing = data.get(profile, {})
    existing.update(values)
    data[profile] = existing
    _save(data)


def get_server_url(profile: str = "default") -> str:
    url = os.getenv("SYNAPSE_URL") or get_profile(profile).get("server_url", "")
    if not url:
        raise SystemExit(
            "No server URL configured. Run: synapse connect <server-url>"
        )
    return url.rstrip("/")


def get_access_token(profile: str = "default") -> Optional[str]:
    return os.getenv("SYNAPSE_TOKEN") or get_profile(profile).get("access_token")


def get_refresh_token(profile: str = "default") -> Optional[str]:
    return get_profile(profile).get("refresh_token")
