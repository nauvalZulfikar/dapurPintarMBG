"""Notifications (Phase 8).

In-app notifications + future PWA push subscriptions. Triggers fire from
events in Phase 2-7 (menu submit, inspection create, etc.) via
`db_create_notification` / `db_notify_users_with_perm` helpers.

Permissions:
  notification.view      — all roles (everyone needs notifs)
  notification.subscribe — all roles (opt-in push)
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func, text

from backend.core.database import (
    engine,
    remote_notifications,
    remote_notification_subscriptions,
    remote_notification_preferences,
    VALID_NOTIF_CATEGORIES,
)
from backend.utils.auth import get_current_user
from backend.utils.permissions import require_permission

router = APIRouter()


# ── List + read ─────────────────────────────────────────────────────────────


@router.get("/notifications")
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    if limit < 1 or limit > 200:
        raise HTTPException(400, "limit must be 1-200")

    with engine.connect() as c:
        q = select(remote_notifications).where(remote_notifications.c.user_id == user["id"])
        if unread_only:
            q = q.where(remote_notifications.c.read_at.is_(None))
        rows = c.execute(q.order_by(remote_notifications.c.created_at.desc()).limit(limit)).all()

    import json as _json
    out = []
    for r in rows:
        try:
            payload = _json.loads(r.payload_json) if r.payload_json else None
        except Exception:
            payload = None
        out.append({
            "id": r.id, "type": r.type, "category": r.category,
            "title": r.title, "body": r.body, "link": r.link,
            "payload": payload,
            "read": r.read_at is not None,
            "read_at": r.read_at.isoformat() if r.read_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"notifications": out}


@router.get("/notifications/unread-count")
async def unread_count(user: dict = Depends(get_current_user)):
    with engine.connect() as c:
        n = c.execute(
            select(func.count()).select_from(remote_notifications).where(
                (remote_notifications.c.user_id == user["id"]) &
                (remote_notifications.c.read_at.is_(None))
            )
        ).scalar() or 0
    return {"unread": int(n)}


@router.post("/notifications/{notif_id}/read")
async def mark_read(notif_id: int, user: dict = Depends(get_current_user)):
    with engine.begin() as c:
        res = c.execute(
            remote_notifications.update()
            .where(
                (remote_notifications.c.id == notif_id) &
                (remote_notifications.c.user_id == user["id"]) &
                (remote_notifications.c.read_at.is_(None))
            )
            .values(read_at=datetime.now())
        )
    return {"ok": True, "updated": res.rowcount}


@router.post("/notifications/mark-all-read")
async def mark_all_read(user: dict = Depends(get_current_user)):
    with engine.begin() as c:
        res = c.execute(
            remote_notifications.update()
            .where(
                (remote_notifications.c.user_id == user["id"]) &
                (remote_notifications.c.read_at.is_(None))
            )
            .values(read_at=datetime.now())
        )
    return {"ok": True, "updated": res.rowcount}


# ── Push subscriptions (PWA, future) ───────────────────────────────────────


class SubscriptionIn(BaseModel):
    endpoint:   str
    p256dh:     Optional[str] = None
    auth:       Optional[str] = None
    user_agent: Optional[str] = None


@router.post("/notifications/subscriptions", status_code=201)
async def subscribe_push(
    body: SubscriptionIn,
    user: dict = Depends(get_current_user),
):
    """Store a Web Push subscription. Actual VAPID push send is wired later
    when VAPID keys are configured. For now this just persists the endpoint.
    """
    with engine.begin() as c:
        # Idempotent: replace existing subscription for same endpoint+user.
        c.execute(
            remote_notification_subscriptions.delete().where(
                (remote_notification_subscriptions.c.user_id == user["id"]) &
                (remote_notification_subscriptions.c.endpoint == body.endpoint)
            )
        )
        res = c.execute(
            remote_notification_subscriptions.insert()
            .values(
                user_id=user["id"],
                endpoint=body.endpoint,
                p256dh=body.p256dh,
                auth=body.auth,
                user_agent=(body.user_agent or "")[:255] or None,
            )
            .returning(remote_notification_subscriptions.c.id)
        )
        new_id = res.scalar()
    return {"id": new_id}


@router.delete("/notifications/subscriptions/{sub_id}")
async def unsubscribe_push(sub_id: int, user: dict = Depends(get_current_user)):
    with engine.begin() as c:
        c.execute(
            remote_notification_subscriptions.delete().where(
                (remote_notification_subscriptions.c.id == sub_id) &
                (remote_notification_subscriptions.c.user_id == user["id"])
            )
        )
    return {"ok": True}


# ── Preferences ────────────────────────────────────────────────────────────


@router.get("/notifications/preferences")
async def get_preferences(user: dict = Depends(get_current_user)):
    with engine.connect() as c:
        rows = c.execute(
            select(remote_notification_preferences).where(
                remote_notification_preferences.c.user_id == user["id"]
            )
        ).all()
    existing = {r.category: bool(r.enabled) for r in rows}
    # Default: all categories enabled unless user has explicitly opted out.
    return {"preferences": {cat: existing.get(cat, True) for cat in VALID_NOTIF_CATEGORIES}}


class PreferencesIn(BaseModel):
    preferences: dict[str, bool]   # {category: enabled}


@router.put("/notifications/preferences")
async def set_preferences(
    body: PreferencesIn,
    user: dict = Depends(get_current_user),
):
    with engine.begin() as c:
        for cat, enabled in body.preferences.items():
            if cat not in VALID_NOTIF_CATEGORIES:
                continue
            existing = c.execute(
                select(remote_notification_preferences.c.id).where(
                    (remote_notification_preferences.c.user_id == user["id"]) &
                    (remote_notification_preferences.c.category == cat)
                )
            ).first()
            if existing:
                c.execute(
                    remote_notification_preferences.update()
                    .where(remote_notification_preferences.c.id == existing.id)
                    .values(enabled=bool(enabled))
                )
            else:
                c.execute(
                    remote_notification_preferences.insert().values(
                        user_id=user["id"],
                        category=cat,
                        enabled=bool(enabled),
                    )
                )
    return {"ok": True}


# ── Manual create (admin / dev) ─────────────────────────────────────────────


class NotifIn(BaseModel):
    user_id:  int
    type:     str = Field(..., max_length=50)
    title:    str = Field(..., max_length=150)
    category: str = "system"
    body:     Optional[str] = None
    link:     Optional[str] = Field(None, max_length=255)


@router.post("/notifications/test", status_code=201)
async def test_notify(
    body: NotifIn,
    user: dict = Depends(get_current_user),
):
    """Dev-only endpoint to manually trigger a notification (for QA)."""
    from backend.core.database import db_create_notification
    nid = db_create_notification(
        user_id=body.user_id,
        type=body.type,
        title=body.title,
        category=body.category,
        body=body.body,
        link=body.link,
    )
    if not nid:
        raise HTTPException(500, "Failed to create notification (or user has opted out of category).")
    return {"id": nid}
