from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.utils.auth import get_current_user
from backend.utils.permissions import (
    require_permission, has_permission,
    kitchen_admin_ids, is_platform_admin, is_org_superadmin,
)
from backend.core.database import (
    db_list_saved_menus, db_save_menu, db_get_saved_menu, db_delete_saved_menu,
    db_menu_transition, db_audit_log, db_notify_users_with_perm,
)

router = APIRouter()


class SaveMenuBody(BaseModel):
    name: str = Field(..., max_length=150)
    payload: Dict[str, Any]                       # {request: {...}, result: {...}} OR manual menu
    source: Optional[str] = "optimizer"           # "optimizer" | "manual"
    target_date: Optional[str] = None             # YYYY-MM-DD
    target_school_id: Optional[int] = None


class TransitionBody(BaseModel):
    notes: Optional[str] = None


@router.get("/menu/saved")
async def list_saved_menus(
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    kitchen: dict = Depends(require_permission("menu.save")),
):
    menus = db_list_saved_menus(kitchen["id"], status=status, from_date=from_date, to_date=to_date)
    return {"menus": menus}


@router.get("/menu/saved/{menu_id}")
async def get_saved_menu(menu_id: int, kitchen: dict = Depends(require_permission("menu.save"))):
    menu = db_get_saved_menu(kitchen["id"], menu_id)
    if not menu:
        raise HTTPException(404, "Menu tidak ditemukan.")
    return menu


@router.post("/menu/saved")
async def save_menu(
    body: SaveMenuBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("menu.save")),
):
    if not body.name or not body.name.strip():
        raise HTTPException(400, "Nama menu tidak boleh kosong.")
    import json as _json
    encoded = _json.dumps(body.payload, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > 100 * 1024:
        raise HTTPException(400, "Menu payload terlalu besar (max 100KB)")
    if body.source not in ("optimizer", "manual"):
        raise HTTPException(400, "source harus 'optimizer' atau 'manual'.")

    row = db_save_menu(
        kitchen_id=kitchen["id"],
        name=body.name.strip(),
        created_by=user["id"],
        payload_dict=body.payload,
        source=body.source or "optimizer",
        target_date=body.target_date,
        target_school_id=body.target_school_id,
    )
    db_audit_log(
        action="menu.create",
        user_id=user["id"],
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="saved_menu",
        target_id=str(row["id"]),
        after_value={"name": row["name"], "source": body.source, "target_date": body.target_date},
    )
    return row


@router.delete("/menu/saved/{menu_id}")
async def delete_saved_menu(
    menu_id: int,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("menu.save")),
):
    menu = db_get_saved_menu(kitchen["id"], menu_id)
    if not menu:
        raise HTTPException(404, "Menu tidak ditemukan.")

    is_creator = menu["created_by"] == user["id"]
    is_kitchen_admin = kitchen["id"] in kitchen_admin_ids(user["id"])
    is_super = is_platform_admin(user) or is_org_superadmin(user)

    if not (is_creator or is_kitchen_admin or is_super):
        raise HTTPException(403, "Hanya pembuat menu atau admin dapur yang dapat menghapus.")

    deleted = db_delete_saved_menu(kitchen["id"], menu_id)
    db_audit_log(
        action="menu.delete",
        user_id=user["id"],
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="saved_menu",
        target_id=str(menu_id),
        before_value={"name": menu.get("name"), "status": menu.get("status")},
    )
    return {"ok": True, "deleted": deleted}


# ── Phase 2B — approval workflow state transitions ─────────────────────────


def _do_transition(action: str, perm: str, menu_id: int, body: TransitionBody, user: dict, kitchen: dict):
    if not has_permission(user, perm, kitchen_id=kitchen["id"]):
        raise HTTPException(403, f"Missing permission: {perm}")

    before = db_get_saved_menu(kitchen["id"], menu_id)
    if not before:
        raise HTTPException(404, "Menu tidak ditemukan.")

    try:
        after = db_menu_transition(
            kitchen_id=kitchen["id"],
            menu_id=menu_id,
            action=action,
            user_id=user["id"],
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    if after is None:
        raise HTTPException(404, "Menu tidak ditemukan setelah update.")

    db_audit_log(
        action=f"menu.{action}",
        user_id=user["id"],
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="saved_menu",
        target_id=str(menu_id),
        before_value={"status": before.get("status"), "name": before.get("name")},
        after_value={"status": after.get("status"), "review_notes": after.get("review_notes")},
    )
    # Phase 8 — notify head_sppg when Ahli Gizi submits menu for review.
    if action == "submit":
        try:
            db_notify_users_with_perm(
                perm="menu.approve",
                kitchen_id=kitchen["id"],
                type="menu.pending_review",
                category="menu",
                title=f'Menu "{after.get("name")}" nunggu approval',
                body=f"Disubmit oleh {user.get('username') or user.get('id')}. Target tanggal: {after.get('target_date') or '-'}",
                link=f"/menu-approval",
                payload={"menu_id": menu_id, "submitted_by": user.get("id")},
            )
        except Exception:
            pass  # notif is best-effort; transition already committed
    return after


@router.post("/menu/saved/{menu_id}/submit")
async def submit_menu_for_review(
    menu_id: int,
    body: TransitionBody = TransitionBody(),
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("menu.save")),
):
    """Ahli Gizi: draft → pending_review."""
    return _do_transition("submit", "menu.submit_for_review", menu_id, body, user, kitchen)


@router.post("/menu/saved/{menu_id}/approve")
async def approve_menu(
    menu_id: int,
    body: TransitionBody = TransitionBody(),
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("menu.save")),
):
    """Kepala SPPG: pending_review → approved."""
    return _do_transition("approve", "menu.approve", menu_id, body, user, kitchen)


@router.post("/menu/saved/{menu_id}/reject")
async def reject_menu(
    menu_id: int,
    body: TransitionBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("menu.save")),
):
    """Kepala SPPG: pending_review → rejected (with review_notes)."""
    if not body.notes or not body.notes.strip():
        raise HTTPException(400, "Catatan review wajib diisi saat reject.")
    return _do_transition("reject", "menu.approve", menu_id, body, user, kitchen)


@router.post("/menu/saved/{menu_id}/lock")
async def lock_menu(
    menu_id: int,
    body: TransitionBody = TransitionBody(),
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("menu.save")),
):
    """approved → locked. Menu tidak bisa diubah lagi setelah locked.
    Akan auto-trigger di Phase 4 saat production batch start.
    """
    return _do_transition("lock", "menu.lock", menu_id, body, user, kitchen)


@router.post("/menu/saved/{menu_id}/archive")
async def archive_menu(
    menu_id: int,
    body: TransitionBody = TransitionBody(),
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("menu.save")),
):
    """Move to archived. Allowed from approved / locked / draft / rejected."""
    return _do_transition("archive", "menu.save", menu_id, body, user, kitchen)


@router.post("/menu/saved/{menu_id}/revert-to-draft")
async def revert_to_draft(
    menu_id: int,
    body: TransitionBody = TransitionBody(),
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("menu.save")),
):
    """rejected → draft (Ahli Gizi mau revisi) ATAU pending_review → draft (Ahli Gizi
    tarik kembali sebelum di-approve).
    """
    return _do_transition("revert_to_draft", "menu.submit_for_review", menu_id, body, user, kitchen)
