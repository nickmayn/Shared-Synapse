"""
SQLite-backed user store for authentication and RBAC.

Schema
------
users (id TEXT PK, username TEXT UNIQUE, hashed_password TEXT,
       role TEXT, active INTEGER, created_at TEXT, updated_at TEXT)
refresh_tokens (token TEXT PK, user_id TEXT, expires_at TEXT, revoked INTEGER)
api_tokens (id TEXT PK, user_id TEXT, name TEXT, token_hash TEXT UNIQUE,
           token_prefix TEXT, created_at TEXT, last_used_at TEXT, revoked INTEGER)
"""
import os
import secrets
import hashlib
import sqlite3
import threading
from datetime import datetime, UTC, timedelta
from pathlib import Path
from typing import Optional

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_DB_PATH_ENV = "USERS_DB_PATH"
_LOCK = threading.Lock()
_conn: Optional[sqlite3.Connection] = None

ROLES = {"admin", "contributor", "viewer"}

REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30"))


def _db_path() -> str:
    default = str(Path(__file__).resolve().parents[3] / ".synapse_users.db")
    return os.getenv(_DB_PATH_ENV, default)


def _get_conn() -> sqlite3.Connection:
    global _conn
    with _LOCK:
        if _conn is None:
            path = _db_path()
            _conn = sqlite3.connect(path, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _init_schema(_conn)
        return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            username    TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'viewer',
            active      INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS refresh_tokens (
            token       TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            expires_at  TEXT NOT NULL,
            revoked     INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS api_tokens (
            id            TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL,
            name          TEXT NOT NULL,
            token_hash    TEXT UNIQUE NOT NULL,
            token_prefix  TEXT NOT NULL,
            created_at    TEXT NOT NULL,
            last_used_at  TEXT,
            revoked       INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.commit()


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def create_user(user_id: str, username: str, password: str, role: str = "viewer") -> dict:
    if role not in ROLES:
        raise ValueError(f"role must be one of: {', '.join(sorted(ROLES))}")
    hashed = _pwd_context.hash(password)
    now = _now()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO users (id, username, hashed_password, role, active, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 1, ?, ?)",
        (user_id, username, hashed, role, now, now),
    )
    conn.commit()
    return get_user_by_id(user_id)  # type: ignore[return-value]


def get_user_by_id(user_id: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_username(username: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def list_users() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, username, role, active, created_at, updated_at FROM users ORDER BY created_at"
    ).fetchall()
    return [dict(r) for r in rows]


def update_user_role(user_id: str, role: str) -> Optional[dict]:
    if role not in ROLES:
        raise ValueError(f"role must be one of: {', '.join(sorted(ROLES))}")
    conn = _get_conn()
    conn.execute(
        "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
        (role, _now(), user_id),
    )
    conn.commit()
    return get_user_by_id(user_id)


def set_user_active(user_id: str, active: bool) -> Optional[dict]:
    conn = _get_conn()
    conn.execute(
        "UPDATE users SET active = ?, updated_at = ? WHERE id = ?",
        (1 if active else 0, _now(), user_id),
    )
    conn.commit()
    return get_user_by_id(user_id)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# API token store
# ---------------------------------------------------------------------------

def _hash_api_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_api_token(user_id: str, name: str) -> tuple[dict, str]:
    token_value = f"sst_{secrets.token_urlsafe(32)}"
    token_hash = _hash_api_token(token_value)
    now = _now()
    token_id = secrets.token_hex(16)
    token_prefix = token_value[:12]
    conn = _get_conn()
    conn.execute(
        "INSERT INTO api_tokens (id, user_id, name, token_hash, token_prefix, created_at, last_used_at, revoked) "
        "VALUES (?, ?, ?, ?, ?, ?, NULL, 0)",
        (token_id, user_id, name, token_hash, token_prefix, now),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, user_id, name, token_prefix, created_at, last_used_at, revoked "
        "FROM api_tokens WHERE id = ?",
        (token_id,),
    ).fetchone()
    return dict(row), token_value


def list_api_tokens(user_id: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, user_id, name, token_prefix, created_at, last_used_at, revoked "
        "FROM api_tokens WHERE user_id = ? AND revoked = 0 ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def revoke_api_token(user_id: str, token_id: str) -> bool:
    conn = _get_conn()
    cursor = conn.execute(
        "UPDATE api_tokens SET revoked = 1 WHERE id = ? AND user_id = ?",
        (token_id, user_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def authenticate_api_token(token: str) -> Optional[dict]:
    token_hash = _hash_api_token(token)
    conn = _get_conn()
    row = conn.execute(
        "SELECT user_id FROM api_tokens WHERE token_hash = ? AND revoked = 0",
        (token_hash,),
    ).fetchone()
    if not row:
        return None

    conn.execute(
        "UPDATE api_tokens SET last_used_at = ? WHERE token_hash = ?",
        (_now(), token_hash),
    )
    conn.commit()
    return get_user_by_id(row["user_id"])


# ---------------------------------------------------------------------------
# Refresh-token store
# ---------------------------------------------------------------------------

def store_refresh_token(token: str, user_id: str) -> None:
    expires = (datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_TTL_DAYS)).isoformat()
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO refresh_tokens (token, user_id, expires_at, revoked) "
        "VALUES (?, ?, ?, 0)",
        (token, user_id, expires),
    )
    conn.commit()


def get_refresh_token(token: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM refresh_tokens WHERE token = ?", (token,)
    ).fetchone()
    return dict(row) if row else None


def revoke_refresh_token(token: str) -> None:
    conn = _get_conn()
    conn.execute("UPDATE refresh_tokens SET revoked = 1 WHERE token = ?", (token,))
    conn.commit()


def ensure_admin_exists() -> None:
    """Create a default admin user if no users exist at all."""
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        import uuid
        default_password = os.getenv("ADMIN_DEFAULT_PASSWORD", "changeme")
        create_user(
            user_id=uuid.uuid4().hex,
            username="admin",
            password=default_password,
            role="admin",
        )
