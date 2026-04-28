"""Admin-only user management REST endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import require_role
from .db.users_store import (
    list_users,
    get_user_by_id,
    create_user,
    update_user_role,
    set_user_active,
    ROLES,
)
import uuid

router = APIRouter(prefix="/admin/users", tags=["user-management"])
_admin = Depends(require_role("admin"))


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UpdateRoleRequest(BaseModel):
    role: str


@router.get("", dependencies=[_admin])
async def api_list_users() -> dict:
    users = list_users()
    # Never expose hashed_password
    safe = [{k: v for k, v in u.items() if k != "hashed_password"} for u in users]
    return {"users": safe, "total": len(safe)}


@router.post("", dependencies=[_admin], status_code=status.HTTP_201_CREATED)
async def api_create_user(body: CreateUserRequest) -> dict:
    if body.role not in ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of: {', '.join(sorted(ROLES))}")
    user_id = uuid.uuid4().hex
    user = create_user(user_id, body.username, body.password, body.role)
    return {k: v for k, v in user.items() if k != "hashed_password"}


@router.patch("/{user_id}/role", dependencies=[_admin])
async def api_update_role(user_id: str, body: UpdateRoleRequest) -> dict:
    if body.role not in ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of: {', '.join(sorted(ROLES))}")
    user = update_user_role(user_id, body.role)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {k: v for k, v in user.items() if k != "hashed_password"}


@router.patch("/{user_id}/deactivate", dependencies=[_admin])
async def api_deactivate_user(user_id: str) -> dict:
    user = set_user_active(user_id, False)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {k: v for k, v in user.items() if k != "hashed_password"}


@router.patch("/{user_id}/activate", dependencies=[_admin])
async def api_activate_user(user_id: str) -> dict:
    user = set_user_active(user_id, True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {k: v for k, v in user.items() if k != "hashed_password"}
