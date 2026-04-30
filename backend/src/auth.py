"""
JWT authentication + FastAPI router for Shared Synapse.

Endpoints
---------
POST /auth/login    -> { access_token, refresh_token, token_type, role }
POST /auth/refresh  -> { access_token, token_type }
POST /auth/logout   -> { status }

RBAC dependency
---------------
require_role("admin")       - admin only
require_role("contributor") - admin or contributor
require_role("viewer")      - any authenticated user
"""
import os
import uuid
from datetime import datetime, UTC, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from .db.users_store import (
    authenticate_api_token,
    create_api_token,
    list_api_tokens,
    revoke_api_token,
    get_user_by_username,
    get_user_by_id,
    store_refresh_token,
    get_refresh_token,
    revoke_refresh_token,
    verify_password,
    ensure_admin_exists,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

ROLE_HIERARCHY = {"admin": 3, "contributor": 2, "viewer": 1}

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CreateApiTokenRequest(BaseModel):
    name: str


class ApiTokenRecord(BaseModel):
    id: str
    user_id: str
    name: str
    token_prefix: str
    created_at: str
    last_used_at: Optional[str] = None
    revoked: int


class CreateApiTokenResponse(BaseModel):
    token: str
    record: ApiTokenRecord


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _create_access_token(user_id: str, username: str, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _resolve_user_from_bearer_token(token: str) -> Optional[dict]:
    try:
        payload = _decode_token(token)
    except HTTPException:
        return None
    user = get_user_by_id(payload.get("sub", ""))
    if not user or not user.get("active"):
        return None
    return user


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    ensure_admin_exists()
    user = get_user_by_username(body.username)
    if not user or not user.get("active") or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    access = _create_access_token(user["id"], user["username"], user["role"])
    refresh = uuid.uuid4().hex
    store_refresh_token(refresh, user["id"])
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        role=user["role"],
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(body: RefreshRequest) -> AccessTokenResponse:
    record = get_refresh_token(body.refresh_token)
    if not record or record["revoked"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    expires_at = datetime.fromisoformat(record["expires_at"])
    if expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
    user = get_user_by_id(record["user_id"])
    if not user or not user.get("active"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    access = _create_access_token(user["id"], user["username"], user["role"])
    return AccessTokenResponse(access_token=access)


@router.post("/logout")
async def logout(body: RefreshRequest) -> dict:
    revoke_refresh_token(body.refresh_token)
    return {"status": "logged_out"}


# ---------------------------------------------------------------------------
# RBAC dependency
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    user = _resolve_user_from_bearer_token(token)
    if user:
        return user

    token_user = authenticate_api_token(token)
    if token_user and token_user.get("active"):
        return token_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(minimum_role: str):
    """Return a FastAPI dependency that enforces a minimum role level."""
    required_level = ROLE_HIERARCHY.get(minimum_role, 1)

    def _check(user: dict = Depends(get_current_user)) -> dict:
        user_level = ROLE_HIERARCHY.get(user.get("role", "viewer"), 1)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{minimum_role}' or higher",
            )
        return user

    return _check


@router.get("/api-tokens", response_model=list[ApiTokenRecord])
async def api_list_user_tokens(user: dict = Depends(get_current_user)) -> list[ApiTokenRecord]:
    return [ApiTokenRecord(**token) for token in list_api_tokens(user["id"])]


@router.post("/api-tokens", response_model=CreateApiTokenResponse, status_code=status.HTTP_201_CREATED)
async def api_create_user_token(
    body: CreateApiTokenRequest,
    user: dict = Depends(get_current_user),
) -> CreateApiTokenResponse:
    token_name = body.name.strip()
    if not token_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Token name is required")
    token_record, token_value = create_api_token(user["id"], token_name)
    return CreateApiTokenResponse(token=token_value, record=ApiTokenRecord(**token_record))


@router.delete("/api-tokens/{token_id}")
async def api_revoke_user_token(
    token_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    if not revoke_api_token(user["id"], token_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API token not found")
    return {"status": "revoked", "id": token_id}
