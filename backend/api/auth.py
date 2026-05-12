from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.utils.auth import (
    authenticate_user,
    create_access_token,
    build_login_payload,
    get_current_user,
    is_superadmin,
    is_platform_admin,
)
from backend.utils.permissions import permissions_for, ALL_PERMS
from backend.core.database import (
    db_list_user_kitchens, db_list_kitchens, db_get_kitchen,
    db_get_organization, db_audit_log,
)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class LoginRequest(BaseModel):
    username: str
    password: str
    org_slug: Optional[str] = None   # required when the same username exists in multiple orgs


class SwitchKitchenRequest(BaseModel):
    kitchen_id: int


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest):
    ip = request.client.host if request.client else None
    user = authenticate_user(body.username, body.password, org_slug=body.org_slug)
    if not user:
        db_audit_log(
            action="login.fail",
            ip_address=ip,
            details={"username": body.username[:80], "org_slug": body.org_slug},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password (or org_slug required)",
        )
    payload = build_login_payload(user)
    token = create_access_token(payload)
    db_audit_log(
        action="login.success",
        user_id=user["id"],
        org_id=user.get("org_id"),
        ip_address=ip,
    )

    # Surface kitchens so the UI can render the switcher immediately.
    if is_platform_admin(user):
        # platform_admin sees every kitchen in every org
        kitchens = [
            {"id": k["id"], "slug": k["slug"], "name": k["name"],
             "label_title": k.get("label_title"), "org_id": k.get("org_id"),
             "role": "platform_admin"}
            for k in db_list_kitchens(active_only=True)
        ]
    elif is_superadmin(user):
        kitchens = [
            {"id": k["id"], "slug": k["slug"], "name": k["name"],
             "label_title": k.get("label_title"), "org_id": k.get("org_id"),
             "role": "superadmin"}
            for k in db_list_kitchens(active_only=True, org_id=user.get("org_id"))
        ]
    else:
        kitchens = db_list_user_kitchens(user["id"])

    org = db_get_organization(user["org_id"]) if user.get("org_id") else None
    active_kid = payload["active_kitchen_id"]
    perms = sorted(permissions_for(user, kitchen_id=active_kid))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"], "username": user["username"], "role": user["role"],
            "org_id": user.get("org_id"),
        },
        "organization": {"id": org["id"], "slug": org["slug"], "name": org["name"]} if org else None,
        "kitchens": kitchens,
        "active_kitchen_id": active_kid,
        "permissions": perms,
    }


@router.post("/switch-kitchen")
async def switch_kitchen(body: SwitchKitchenRequest, user: dict = Depends(get_current_user)):
    """Re-issue a JWT with a different `active_kitchen_id`."""
    if not is_superadmin(user):
        allowed = user.get("kitchen_ids") or []
        if body.kitchen_id not in allowed:
            raise HTTPException(status_code=403, detail="You do not have access to this kitchen")

    kitchen = db_get_kitchen(body.kitchen_id)
    if not kitchen or not kitchen.get("active"):
        raise HTTPException(status_code=404, detail="Kitchen not found or inactive")

    # Rebuild the payload using a fresh kitchens lookup to stay in sync if
    # the user's kitchen mappings changed since login.
    payload = {
        "sub": user["username"],
        "id": user["id"],
        "role": user["role"],
        "kitchen_ids": user.get("kitchen_ids") or [],
        "active_kitchen_id": body.kitchen_id,
    }
    token = create_access_token(payload)
    perms = sorted(permissions_for(user, kitchen_id=body.kitchen_id))
    return {
        "access_token": token,
        "token_type": "bearer",
        "active_kitchen_id": body.kitchen_id,
        "kitchen": {"id": kitchen["id"], "slug": kitchen["slug"], "name": kitchen["name"]},
        "permissions": perms,
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    if is_platform_admin(user):
        kitchens = [
            {"id": k["id"], "slug": k["slug"], "name": k["name"],
             "label_title": k.get("label_title"), "org_id": k.get("org_id"),
             "role": "platform_admin"}
            for k in db_list_kitchens(active_only=True)
        ]
    elif is_superadmin(user):
        kitchens = [
            {"id": k["id"], "slug": k["slug"], "name": k["name"],
             "label_title": k.get("label_title"), "org_id": k.get("org_id"),
             "role": "superadmin"}
            for k in db_list_kitchens(active_only=True, org_id=user.get("org_id"))
        ]
    else:
        kitchens = db_list_user_kitchens(user["id"])
    org = db_get_organization(user["org_id"]) if user.get("org_id") else None
    active_kid = user.get("active_kitchen_id")
    perms = sorted(permissions_for(user, kitchen_id=active_kid))
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "org_id": user.get("org_id"),
        "organization": {"id": org["id"], "slug": org["slug"], "name": org["name"]} if org else None,
        "kitchens": kitchens,
        "active_kitchen_id": active_kid,
        "permissions": perms,
    }
