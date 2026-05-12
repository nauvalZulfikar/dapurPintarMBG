"""Admin endpoints.

Three privilege tiers:
  - platform_admin : operates across all organizations (CRUD orgs, sees every kitchen)
  - superadmin     : operates within its own organization only
  - user           : no admin access

Endpoints here never leak data outside the caller's org unless the caller is
platform_admin.
"""
import secrets
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from backend.core.database import (
    engine,
    remote_organizations,
    remote_kitchens,
    remote_users,
    remote_user_kitchens,
    db_list_kitchens,
    db_list_organizations,
    db_get_organization,
    db_get_kitchen,
)
from backend.utils.auth import (
    require_superadmin, require_platform_admin,
    is_platform_admin, is_superadmin,
    hash_password, get_current_user,
)
from backend.utils.permissions import VALID_KITCHEN_ROLES, kitchen_admin_ids

router = APIRouter()


# ============================================================
#  Helpers
# ============================================================

def _kitchen_admin_scope(user: dict) -> set[int]:
    """kitchen_ids where the caller holds per-kitchen role='admin'. Empty for
    superadmins (who don't need this scoping — they see the whole org)."""
    return kitchen_admin_ids(user["id"])


def _require_admin_tier(user: dict = Depends(get_current_user)) -> dict:
    """Allow platform_admin, org superadmin, OR per-kitchen admin.

    Per-kitchen admins get scoped views (only kitchens/users they manage).
    Destructive ops (delete_kitchen, delete_user, role promotion) still require
    superadmin and re-check inside the handler.
    """
    if is_superadmin(user):
        return user
    if _kitchen_admin_scope(user):
        return user
    raise HTTPException(status_code=403, detail="Admin access required")


def _scope_kitchens_query(user: dict):
    q = select(remote_kitchens)
    if is_platform_admin(user):
        return q
    if is_superadmin(user):
        return q.where(remote_kitchens.c.org_id == user.get("org_id"))
    # per-kitchen admin: only kitchens they manage
    ids = _kitchen_admin_scope(user)
    return q.where(remote_kitchens.c.id.in_(ids)) if ids else q.where(remote_kitchens.c.id == -1)


def _scope_users_query(user: dict):
    q = select(remote_users.c.id, remote_users.c.username, remote_users.c.role,
               remote_users.c.org_id, remote_users.c.created_at)
    if is_platform_admin(user):
        return q
    if is_superadmin(user):
        return q.where(remote_users.c.org_id == user.get("org_id"))
    # per-kitchen admin: only users assigned to a kitchen they manage (+ themselves)
    ids = _kitchen_admin_scope(user)
    if not ids:
        return q.where(remote_users.c.id == -1)
    sub = select(remote_user_kitchens.c.user_id).where(
        remote_user_kitchens.c.kitchen_id.in_(ids)
    )
    return q.where(remote_users.c.id.in_(sub) | (remote_users.c.id == user["id"]))


def _assert_kitchen_access(user: dict, kitchen_id: int):
    """Caller may touch this kitchen.

    - platform_admin: any kitchen.
    - superadmin: any kitchen in its own org.
    - kitchen admin: only kitchens where their user_kitchens.role='admin'.
    """
    kitchen = db_get_kitchen(kitchen_id)
    if not kitchen:
        raise HTTPException(404, "Kitchen not found")
    if is_platform_admin(user):
        return kitchen
    if is_superadmin(user) and kitchen.get("org_id") == user.get("org_id"):
        return kitchen
    if not is_superadmin(user) and kitchen_id in _kitchen_admin_scope(user):
        return kitchen
    raise HTTPException(403, "You do not administer this kitchen")


# backward-compat alias for older callers (org-level check + kitchen-admin)
_assert_kitchen_in_org = _assert_kitchen_access


def _assert_user_accessible(user: dict, target_user_id: int) -> dict:
    """Caller may touch this user.

    - platform_admin: any user.
    - superadmin: any user in its own org.
    - kitchen admin: users assigned to at least one kitchen they manage.
    """
    with engine.connect() as c:
        row = c.execute(
            select(remote_users.c.id, remote_users.c.org_id, remote_users.c.role)
            .where(remote_users.c.id == target_user_id)
        ).first()
    if not row:
        raise HTTPException(404, "User not found")
    if is_platform_admin(user):
        return dict(row._mapping)
    if is_superadmin(user):
        if row.org_id != user.get("org_id"):
            raise HTTPException(403, "User belongs to a different organization")
        return dict(row._mapping)
    # per-kitchen admin: target must be same org AND
    #   (a) share at least one admin-kitchen, OR
    #   (b) have no kitchen assignments yet (freshly-invited user, not yet placed)
    # This lets a kitchen admin reset password / assign kitchen for users they
    # just invited.
    if row.org_id != user.get("org_id"):
        raise HTTPException(403, "User belongs to a different organization")
    admin_ids = _kitchen_admin_scope(user)
    if not admin_ids:
        raise HTTPException(403, "Not an admin")
    with engine.connect() as c:
        share = c.execute(
            select(remote_user_kitchens.c.user_id)
            .where(
                (remote_user_kitchens.c.user_id == target_user_id) &
                (remote_user_kitchens.c.kitchen_id.in_(admin_ids))
            )
            .limit(1)
        ).first()
        if not share:
            any_assign = c.execute(
                select(remote_user_kitchens.c.user_id)
                .where(remote_user_kitchens.c.user_id == target_user_id)
                .limit(1)
            ).first()
    if not share and any_assign and target_user_id != user["id"]:
        raise HTTPException(403, "You do not manage this user")
    return dict(row._mapping)


# backward-compat alias
_assert_user_in_org = _assert_user_accessible


# ============================================================
#  Organizations (platform_admin only)
# ============================================================

class OrgIn(BaseModel):
    slug: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    active: bool = True


class OrgPatch(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None


@router.get("/organizations", dependencies=[Depends(require_platform_admin)])
async def list_orgs():
    return {"organizations": db_list_organizations(active_only=False)}


@router.get("/roles", dependencies=[Depends(require_superadmin)])
async def list_kitchen_roles():
    """Valid per-kitchen role identifiers + their permission sets."""
    from backend.utils.permissions import ROLE_PERMS
    return {
        "roles": [
            {"id": r, "permissions": sorted(ROLE_PERMS[r])}
            for r in VALID_KITCHEN_ROLES
        ]
    }


@router.post("/organizations", status_code=201, dependencies=[Depends(require_platform_admin)])
async def create_org(body: OrgIn):
    with engine.begin() as c:
        res = c.execute(
            remote_organizations.insert()
            .values(**body.model_dump())
            .returning(remote_organizations.c.id)
        )
        new_id = res.scalar()
    return db_get_organization(new_id)


@router.patch("/organizations/{org_id}", dependencies=[Depends(require_platform_admin)])
async def patch_org(org_id: int, body: OrgPatch):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    if not values:
        raise HTTPException(400, "No fields to update")
    with engine.begin() as c:
        res = c.execute(
            remote_organizations.update()
            .where(remote_organizations.c.id == org_id)
            .values(**values)
        )
        if res.rowcount == 0:
            raise HTTPException(404, "Organization not found")
    return db_get_organization(org_id)


@router.delete("/organizations/{org_id}", dependencies=[Depends(require_platform_admin)])
async def deactivate_org(org_id: int):
    with engine.begin() as c:
        res = c.execute(
            remote_organizations.update()
            .where(remote_organizations.c.id == org_id)
            .values(active=False)
        )
        if res.rowcount == 0:
            raise HTTPException(404, "Organization not found")
    return {"ok": True}


# ============================================================
#  Kitchens (superadmin for own org, platform_admin any)
# ============================================================

class KitchenIn(BaseModel):
    slug: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    printer_name: Optional[str] = None
    printer_lang: Optional[str] = "ZPL"
    label_title: Optional[str] = None
    scanner_key: Optional[str] = None
    cloud_print_key: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = "Asia/Jakarta"
    active: bool = True
    org_id: Optional[int] = None   # ignored unless caller is platform_admin


class KitchenPatch(BaseModel):
    name: Optional[str] = None
    printer_name: Optional[str] = None
    printer_lang: Optional[str] = None
    label_title: Optional[str] = None
    scanner_key: Optional[str] = None
    cloud_print_key: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = None
    active: Optional[bool] = None


@router.get("/kitchens")
async def list_kitchens(user: dict = Depends(_require_admin_tier)):
    with engine.connect() as c:
        rows = c.execute(_scope_kitchens_query(user).order_by(remote_kitchens.c.id)).all()
    return {"kitchens": [dict(r._mapping) for r in rows]}


@router.post("/kitchens", status_code=201)
async def create_kitchen(body: KitchenIn, user: dict = Depends(require_superadmin)):
    values = body.model_dump()
    # scope to caller's org unless platform_admin explicitly overrides
    if is_platform_admin(user):
        if values.get("org_id") is None:
            raise HTTPException(400, "platform_admin must specify org_id")
    else:
        values["org_id"] = user.get("org_id")

    values["scanner_key"] = values.get("scanner_key") or secrets.token_urlsafe(24)
    values["cloud_print_key"] = values.get("cloud_print_key") or secrets.token_urlsafe(24)
    if not values.get("label_title"):
        values["label_title"] = values["name"]

    with engine.begin() as c:
        res = c.execute(remote_kitchens.insert().values(**values).returning(remote_kitchens.c.id))
        new_id = res.scalar()
    return db_get_kitchen(new_id)


@router.patch("/kitchens/{kitchen_id}")
async def patch_kitchen(kitchen_id: int, body: KitchenPatch, user: dict = Depends(_require_admin_tier)):
    _assert_kitchen_access(user, kitchen_id)
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    # kitchen admins may not deactivate their own kitchen — too disruptive
    if not is_superadmin(user) and "active" in values:
        raise HTTPException(403, "Only superadmin can change kitchen active status")
    if not values:
        raise HTTPException(400, "No fields to update")
    with engine.begin() as c:
        c.execute(
            remote_kitchens.update()
            .where(remote_kitchens.c.id == kitchen_id)
            .values(**values)
        )
    return db_get_kitchen(kitchen_id)


@router.delete("/kitchens/{kitchen_id}")
async def delete_kitchen(kitchen_id: int, user: dict = Depends(require_superadmin)):
    _assert_kitchen_in_org(user, kitchen_id)
    with engine.begin() as c:
        c.execute(
            remote_kitchens.update()
            .where(remote_kitchens.c.id == kitchen_id)
            .values(active=False)
        )
    return {"ok": True}


@router.post("/kitchens/{kitchen_id}/rotate-scanner-key")
async def rotate_scanner_key(kitchen_id: int, user: dict = Depends(_require_admin_tier)):
    _assert_kitchen_access(user, kitchen_id)
    new_key = secrets.token_urlsafe(24)
    with engine.begin() as c:
        c.execute(
            remote_kitchens.update()
            .where(remote_kitchens.c.id == kitchen_id)
            .values(scanner_key=new_key)
        )
    return {"scanner_key": new_key}


@router.post("/kitchens/{kitchen_id}/rotate-print-key")
async def rotate_print_key(kitchen_id: int, user: dict = Depends(_require_admin_tier)):
    _assert_kitchen_access(user, kitchen_id)
    new_key = secrets.token_urlsafe(24)
    with engine.begin() as c:
        c.execute(
            remote_kitchens.update()
            .where(remote_kitchens.c.id == kitchen_id)
            .values(cloud_print_key=new_key)
        )
    return {"cloud_print_key": new_key}


# ============================================================
#  Users (superadmin for own org, platform_admin any)
# ============================================================

class UserIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = "user"                    # platform_admin | superadmin | user
    org_id: Optional[int] = None          # ignored unless platform_admin


class UserPatch(BaseModel):
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    role: Optional[str] = None


class KitchenAssignment(BaseModel):
    kitchen_id: int
    role: str = "admin"                   # admin | ahli_gizi | accountant


@router.get("/users")
async def list_users(user: dict = Depends(_require_admin_tier)):
    users_q = _scope_users_query(user)
    with engine.connect() as c:
        rows = c.execute(users_q.order_by(remote_users.c.id)).all()
        user_ids = [r.id for r in rows]

        assign_q = (
            select(
                remote_user_kitchens.c.user_id,
                remote_user_kitchens.c.kitchen_id,
                remote_user_kitchens.c.role,
                remote_kitchens.c.name,
                remote_kitchens.c.slug,
            )
            .select_from(
                remote_user_kitchens.join(
                    remote_kitchens,
                    remote_user_kitchens.c.kitchen_id == remote_kitchens.c.id,
                )
            )
        )
        if user_ids:
            assign_q = assign_q.where(remote_user_kitchens.c.user_id.in_(user_ids))
        assignments = c.execute(assign_q).all()

    per_user: dict = {}
    for a in assignments:
        per_user.setdefault(a.user_id, []).append({
            "kitchen_id": a.kitchen_id, "role": a.role,
            "name": a.name, "slug": a.slug,
        })

    return {
        "users": [
            {
                "id": u.id, "username": u.username, "role": u.role,
                "org_id": u.org_id,
                "created_at": str(u.created_at) if u.created_at else None,
                "kitchens": per_user.get(u.id, []),
            }
            for u in rows
        ]
    }


@router.post("/users", status_code=201)
async def create_user(body: UserIn, user: dict = Depends(_require_admin_tier)):
    # scope org
    if is_platform_admin(user):
        if body.role == "platform_admin" and body.org_id is not None:
            raise HTTPException(400, "platform_admin users cannot be scoped to an org")
        # platform_admin may pass any org_id; if omitted and role != platform_admin,
        # default to their own current org so the common in-org flow still works.
        if body.org_id is not None:
            new_org_id = body.org_id
        elif body.role == "platform_admin":
            new_org_id = None
        else:
            new_org_id = user.get("org_id")
    else:
        # Non-platform-admins can never create platform_admin or superadmin accounts.
        if body.role == "platform_admin":
            raise HTTPException(403, "Only platform_admin can create platform_admin users")
        if body.role == "superadmin" and not is_superadmin(user):
            raise HTTPException(403, "Kitchen admins may only invite regular users")
        new_org_id = user.get("org_id")

    with engine.begin() as c:
        exists_q = select(remote_users.c.id).where(remote_users.c.username == body.username)
        if new_org_id is not None:
            exists_q = exists_q.where(remote_users.c.org_id == new_org_id)
        else:
            exists_q = exists_q.where(remote_users.c.org_id.is_(None))
        if c.execute(exists_q).first():
            raise HTTPException(409, "Username already exists in this organization")

        res = c.execute(
            remote_users.insert()
            .values(
                username=body.username,
                password_hash=hash_password(body.password),
                role=body.role,
                org_id=new_org_id,
            )
            .returning(remote_users.c.id)
        )
        new_id = res.scalar()
    return {"id": new_id, "username": body.username, "role": body.role, "org_id": new_org_id}


@router.patch("/users/{user_id}")
async def patch_user(user_id: int, body: UserPatch, user: dict = Depends(_require_admin_tier)):
    target = _assert_user_accessible(user, user_id)
    # Only platform_admin can grant platform_admin.
    if body.role == "platform_admin" and not is_platform_admin(user):
        raise HTTPException(403, "Only platform_admin can grant platform_admin")
    # Kitchen admins can only reset passwords, not change global roles.
    if body.role is not None and not is_superadmin(user):
        raise HTTPException(403, "Only superadmin can change user's global role")

    values = {}
    if body.role is not None:
        values["role"] = body.role
    if body.password is not None:
        values["password_hash"] = hash_password(body.password)
    if not values:
        raise HTTPException(400, "No fields to update")
    with engine.begin() as c:
        c.execute(remote_users.update().where(remote_users.c.id == user_id).values(**values))
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, user: dict = Depends(require_superadmin)):
    _assert_user_in_org(user, user_id)
    with engine.begin() as c:
        c.execute(remote_users.delete().where(remote_users.c.id == user_id))
    return {"ok": True}


# ============================================================
#  User ↔ Kitchen assignment
# ============================================================

@router.post("/users/{user_id}/kitchens")
async def assign_kitchen(user_id: int, body: KitchenAssignment, user: dict = Depends(_require_admin_tier)):
    if body.role not in VALID_KITCHEN_ROLES:
        raise HTTPException(400, f"Invalid role. Valid: {', '.join(VALID_KITCHEN_ROLES)}")
    # Kitchen admins cannot promote another user to kitchen-admin role
    if body.role == "admin" and not is_superadmin(user):
        raise HTTPException(403, "Only superadmin can grant kitchen-admin role")
    target = _assert_user_accessible(user, user_id)
    kitchen = _assert_kitchen_access(user, body.kitchen_id)
    # Extra guard: the user and kitchen must belong to the same org.
    if target.get("org_id") != kitchen.get("org_id"):
        raise HTTPException(400, "User and kitchen belong to different organizations")

    with engine.begin() as c:
        c.execute(text("""
            INSERT INTO user_kitchens (user_id, kitchen_id, role)
            VALUES (:uid, :kid, :role)
            ON CONFLICT ON CONSTRAINT uq_user_kitchen
            DO UPDATE SET role = EXCLUDED.role
        """), {"uid": user_id, "kid": body.kitchen_id, "role": body.role})
    return {"ok": True}


@router.delete("/users/{user_id}/kitchens/{kitchen_id}")
async def unassign_kitchen(user_id: int, kitchen_id: int, user: dict = Depends(_require_admin_tier)):
    _assert_user_accessible(user, user_id)
    _assert_kitchen_access(user, kitchen_id)
    with engine.begin() as c:
        res = c.execute(
            remote_user_kitchens.delete().where(
                (remote_user_kitchens.c.user_id == user_id) &
                (remote_user_kitchens.c.kitchen_id == kitchen_id)
            )
        )
        if res.rowcount == 0:
            raise HTTPException(404, "Mapping not found")
    return {"ok": True}


# ============================================================
#  Cross-kitchen overview
# ============================================================

@router.get("/overview")
async def cross_kitchen_overview(
    date_filter: Optional[str] = Query(None, alias="date"),
    user: dict = Depends(_require_admin_tier),
):
    """Aggregate per-kitchen metrics.

    Scoped to the caller's org (platform_admin sees everything).
    """
    target = date.fromisoformat(date_filter) if date_filter else date.today()
    week_start = target - timedelta(days=6)
    org_id = None if is_platform_admin(user) else user.get("org_id")

    with engine.connect() as c:
        kq = select(
            remote_kitchens.c.id, remote_kitchens.c.slug,
            remote_kitchens.c.name, remote_kitchens.c.active,
            remote_kitchens.c.org_id,
        )
        if org_id is not None:
            kq = kq.where(remote_kitchens.c.org_id == org_id)
        kitchens = c.execute(kq.order_by(remote_kitchens.c.id)).all()

        org_filter = "" if org_id is None else " AND k.org_id = :org"

        today_rows = c.execute(text(f"""
            SELECT k.id AS kitchen_id,
              COALESCE(SUM(CASE WHEN i.created_date_receiving = :d THEN 1 ELSE 0 END), 0) AS received,
              COALESCE(SUM(CASE WHEN i.created_date_processing = :d THEN 1 ELSE 0 END), 0) AS processed
            FROM   kitchens k
            LEFT   JOIN items i ON i.kitchen_id = k.id
              AND (i.created_date_receiving = :d OR i.created_date_processing = :d)
            WHERE  k.active = TRUE{org_filter}
            GROUP  BY k.id
        """), {"d": str(target), **({"org": org_id} if org_id is not None else {})}).fetchall()

        tray_rows = c.execute(text(f"""
            SELECT k.id AS kitchen_id,
              COALESCE(SUM(CASE WHEN t.created_date_packing  = :d THEN 1 ELSE 0 END), 0) AS packed,
              COALESCE(SUM(CASE WHEN t.created_date_delivery = :d THEN 1 ELSE 0 END), 0) AS delivered,
              MAX(t.created_at_delivery) AS last_delivery
            FROM   kitchens k
            LEFT   JOIN trays t ON t.kitchen_id = k.id
            WHERE  k.active = TRUE{org_filter}
            GROUP  BY k.id
        """), {"d": str(target), **({"org": org_id} if org_id is not None else {})}).fetchall()

        err_q = "SELECT kitchen_id, COUNT(*) n FROM scan_errors WHERE kitchen_id IS NOT NULL AND created_at LIKE :like"
        err_params = {"like": f"{target}%"}
        if org_id is not None:
            err_q += " AND kitchen_id IN (SELECT id FROM kitchens WHERE org_id = :org)"
            err_params["org"] = org_id
        err_q += " GROUP BY kitchen_id"
        err_rows = c.execute(text(err_q), err_params).fetchall()

        trend_q = (
            "SELECT i.kitchen_id AS kitchen_id, i.created_date_receiving AS trend_date, COUNT(*) AS n "
            "FROM items i WHERE i.created_date_receiving BETWEEN :start AND :end"
        )
        trend_params = {"start": str(week_start), "end": str(target)}
        if org_id is not None:
            trend_q += " AND i.kitchen_id IN (SELECT id FROM kitchens WHERE org_id = :org)"
            trend_params["org"] = org_id
        trend_q += " GROUP BY i.kitchen_id, i.created_date_receiving"
        trend_rows = c.execute(text(trend_q), trend_params).fetchall()

    today_by_kid = {r.kitchen_id: {"received": r.received, "processed": r.processed} for r in today_rows}
    tray_by_kid = {r.kitchen_id: r for r in tray_rows}
    err_by_kid = {r.kitchen_id: r.n for r in err_rows}
    trend_by_kid: dict = {}
    for r in trend_rows:
        trend_by_kid.setdefault(r.kitchen_id, []).append({"date": str(r.trend_date), "received": int(r.n)})

    summary = []
    totals = {"received": 0, "processed": 0, "packed": 0, "delivered": 0, "errors": 0}
    for k in kitchens:
        t = today_by_kid.get(k.id, {"received": 0, "processed": 0})
        tr = tray_by_kid.get(k.id)
        packed = int(tr.packed) if tr else 0
        delivered = int(tr.delivered) if tr else 0
        last_delivery = str(tr.last_delivery) if tr and tr.last_delivery else None
        errors = int(err_by_kid.get(k.id, 0))

        summary.append({
            "kitchen_id": k.id, "slug": k.slug, "name": k.name,
            "active": k.active, "org_id": k.org_id,
            "received": int(t["received"]), "processed": int(t["processed"]),
            "packed": packed, "delivered": delivered, "errors": errors,
            "last_delivery": last_delivery,
            "trend": trend_by_kid.get(k.id, []),
        })
        totals["received"]  += int(t["received"])
        totals["processed"] += int(t["processed"])
        totals["packed"]    += packed
        totals["delivered"] += delivered
        totals["errors"]    += errors

    return {
        "date": str(target),
        "week_start": str(week_start),
        "org_id": org_id,
        "kitchens": summary,
        "totals": totals,
    }
