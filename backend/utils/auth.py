import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select

from backend.core.database import (
    engine,
    remote_users,
    db_list_user_kitchens,
    db_get_kitchen,
    db_get_organization,
)

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY env var is required. Set a random 32+ char string in .env")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── Password / token primitives ─────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── DB lookups ──────────────────────────────────────────────────────────────

def authenticate_user(username: str, password: str, org_slug: Optional[str] = None) -> Optional[dict]:
    """Authenticate by (org_slug, username, password).

    If `org_slug` is not given, pick the single matching user. When the same
    username exists in multiple orgs the caller must disambiguate with slug.
    """
    from backend.core.database import remote_organizations
    with engine.connect() as c:
        q = select(remote_users)
        if org_slug:
            q = q.join(remote_organizations, remote_users.c.org_id == remote_organizations.c.id)\
                 .where(
                     (remote_users.c.username == username) &
                     (remote_organizations.c.slug == org_slug)
                 )
        else:
            q = q.where(remote_users.c.username == username)
        rows = c.execute(q).all()
    if len(rows) == 0:
        return None
    if len(rows) > 1:
        # ambiguous — caller must pass org_slug
        return None
    row = rows[0]
    if not verify_password(password, row.password_hash):
        return None
    return {"id": row.id, "username": row.username, "role": row.role, "org_id": row.org_id}


def build_login_payload(user: dict) -> dict:
    """Build JWT claims including org_id and accessible kitchens."""
    kitchens = db_list_user_kitchens(user["id"])
    kitchen_ids = [k["id"] for k in kitchens]
    active_kitchen_id = kitchen_ids[0] if kitchen_ids else None
    return {
        "sub": user["username"],
        "id": user["id"],
        "role": user["role"],                 # platform_admin | superadmin | user | legacy "admin"
        "org_id": user.get("org_id"),
        "kitchen_ids": kitchen_ids,
        "active_kitchen_id": active_kitchen_id,
    }


# ── Dependencies ────────────────────────────────────────────────────────────

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Returns the full decoded JWT including org + kitchen claims."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        if payload.get("sub") is None:
            raise credentials_exception
        return {
            "id": payload.get("id"),
            "username": payload.get("sub"),
            "role": payload.get("role"),
            "org_id": payload.get("org_id"),
            "kitchen_ids": payload.get("kitchen_ids") or [],
            "active_kitchen_id": payload.get("active_kitchen_id"),
        }
    except JWTError:
        raise credentials_exception


def is_platform_admin(user: dict) -> bool:
    return user.get("role") == "platform_admin"


def is_superadmin(user: dict) -> bool:
    # platform_admin supersedes superadmin. legacy "admin" stays as org superadmin.
    return user.get("role") in ("platform_admin", "superadmin", "admin")


def get_current_kitchen(
    user: dict = Depends(get_current_user),
    x_kitchen_id: Optional[str] = Header(None, alias="X-Kitchen-Id"),
) -> dict:
    """Resolve the kitchen the request is acting on.

    Authorization:
      - platform_admin: any kitchen in any org.
      - superadmin of org X: any kitchen where kitchen.org_id == user.org_id.
      - user: kitchens listed in JWT.kitchen_ids.
    """
    requested_id: Optional[int] = None
    if x_kitchen_id:
        try:
            requested_id = int(x_kitchen_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-Kitchen-Id header")

    if requested_id is None:
        requested_id = user.get("active_kitchen_id")

    if requested_id is None and is_superadmin(user):
        fallback = db_get_kitchen(1)
        if fallback:
            return fallback
        raise HTTPException(status_code=400, detail="No kitchen available")

    if requested_id is None:
        raise HTTPException(status_code=400, detail="No kitchen in token; please log in again")

    kitchen = db_get_kitchen(requested_id)
    if not kitchen:
        raise HTTPException(status_code=404, detail="Kitchen not found")
    if not kitchen.get("active"):
        raise HTTPException(status_code=403, detail="Kitchen is inactive")

    # Authorization checks, ordered from most privileged to least.
    if is_platform_admin(user):
        return kitchen

    if user.get("role") in ("superadmin", "admin"):
        if user.get("org_id") is None or kitchen.get("org_id") == user.get("org_id"):
            return kitchen
        raise HTTPException(status_code=403, detail="Kitchen belongs to a different organization")

    if requested_id not in (user.get("kitchen_ids") or []):
        raise HTTPException(status_code=403, detail="You do not have access to this kitchen")
    return kitchen


def require_superadmin(user: dict = Depends(get_current_user)) -> dict:
    if not is_superadmin(user):
        raise HTTPException(status_code=403, detail="Superadmin only")
    return user


def require_platform_admin(user: dict = Depends(get_current_user)) -> dict:
    if not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="Platform admin only")
    return user


def get_user_org_id(user: dict) -> Optional[int]:
    """Org the user is scoped to — None for platform_admin (cross-org)."""
    if is_platform_admin(user):
        return None
    return user.get("org_id")
