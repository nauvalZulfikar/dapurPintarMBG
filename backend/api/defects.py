"""Defect items — barang yang ditolak saat receiving QC.

Workflow terpisah dari `items` table karena defect rows tidak masuk ke
processing/packing/delivery pipeline. Disimpan untuk supplier accountability
& BGN audit reporting.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select, text

from backend.core.database import engine, remote_defect_items, db_get_item_availability, db_audit_log
from backend.utils.auth import get_current_user
from backend.utils.permissions import require_permission
from backend.utils.validators import new_defect_id

router = APIRouter()
log = logging.getLogger(__name__)

PAGE_SIZE = 50
MAX_PHOTO_BYTES = 5 * 1024 * 1024   # 5 MB
ALLOWED_EXT = {"jpg", "jpeg", "png", "webp"}

_PHOTO_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "defect_photos",
)


def _save_photo(photo: UploadFile, kitchen_id: int, defect_id: str) -> str:
    """Persist the uploaded photo under data/defect_photos/{kid}/{YYYY-MM-DD}/{id}.{ext}.

    Returns the path relative to the photo root, suitable for storing in DB.
    Raises HTTPException on validation failure.
    """
    raw = photo.filename or ""
    ext = raw.rsplit(".", 1)[-1].lower() if "." in raw else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported photo type. Allowed: {sorted(ALLOWED_EXT)}")

    blob = photo.file.read(MAX_PHOTO_BYTES + 1)
    if len(blob) > MAX_PHOTO_BYTES:
        raise HTTPException(413, f"Photo exceeds {MAX_PHOTO_BYTES // (1024*1024)}MB limit")
    if not blob:
        raise HTTPException(400, "Empty photo upload")

    today = date.today().isoformat()
    rel_dir = os.path.join(str(kitchen_id), today)
    abs_dir = os.path.join(_PHOTO_ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    fname = f"{defect_id}.{ext}"
    abs_path = os.path.join(abs_dir, fname)
    with open(abs_path, "wb") as f:
        f.write(blob)

    return os.path.join(rel_dir, fname).replace("\\", "/")


@router.post("/defects", status_code=201)
async def create_defect(
    name: str = Form(...),
    weight: float = Form(...),
    unit: str = Form("g"),
    defect_reason: str = Form(...),
    checklist: Optional[str] = Form(None),       # JSON string, optional
    notes: Optional[str] = Form(None),
    item_id: Optional[str] = Form(None),         # link to source BHN (skenario C); empty = skenario A
    allow_old_bhn: bool = Form(False),           # explicit override for >1 day BHN (audited)
    photo: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("items.create")),
):
    """Record a defect item rejected during receiving QC. Optional photo evidence.

    Two modes:
      - skenario A (item_id=None): reject sebelum BHN dicetak (supplier ditolak di pintu)
      - skenario C (item_id set):  defect parsial dari BHN existing
    """
    if not name.strip():
        raise HTTPException(400, "Name is required")
    if weight <= 0:
        raise HTTPException(400, "Weight must be > 0")
    if not defect_reason.strip():
        raise HTTPException(400, "Defect reason is required")

    weight_g = int(weight * 1000) if unit == "kg" else int(weight)

    # ── Skenario C validation: must reference a real BHN, not exceed available, fresh ≤1 day
    linked_item_id: Optional[str] = None
    if item_id and item_id.strip():
        avail = db_get_item_availability(item_id.strip(), kitchen["id"])
        if not avail:
            raise HTTPException(404, "BHN tidak ditemukan atau bukan dari dapur kamu")
        if avail["available_grams"] <= 0:
            raise HTTPException(400, "BHN ini sudah fully defected (tidak ada sisa)")
        if weight_g > avail["available_grams"]:
            raise HTTPException(
                400,
                f"Berat defect melebihi sisa available. Maks {avail['available_grams']} g.",
            )

        # Freshness rule: SOP MBG = 4-6 hours from receiving to consumption,
        # so a defect raised >1 day after receiving is unusual. Require explicit
        # override + audit trail.
        if avail.get("created_date_receiving"):
            try:
                rec_date = date.fromisoformat(avail["created_date_receiving"])
                days_old = (date.today() - rec_date).days
                if days_old > 1 and not allow_old_bhn:
                    raise HTTPException(
                        400,
                        f"BHN ini sudah {days_old} hari sejak diterima. "
                        "Centang opsi 'Bahan lama' untuk override.",
                    )
            except (TypeError, ValueError):
                pass

        linked_item_id = avail["id"]

    parsed_checklist = None
    if checklist:
        try:
            parsed_checklist = json.loads(checklist)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid checklist JSON")

    defect_id = new_defect_id()
    photo_rel = None
    if photo and photo.filename:
        photo_rel = _save_photo(photo, kitchen["id"], defect_id)

    reason_blob = json.dumps({
        "defect_reason": defect_reason.strip(),
        "checklist": parsed_checklist or {},
        "notes": (notes or "").strip() or None,
    }, ensure_ascii=False)

    with engine.begin() as c:
        c.execute(remote_defect_items.insert().values(
            id=defect_id,
            kitchen_id=kitchen["id"],
            name=name.strip(),
            weight_grams=weight_g,
            unit=unit,
            reason=reason_blob,
            photo_path=photo_rel,
            item_id=linked_item_id,
            created_by=user.get("id"),
            created_at=datetime.now(),
            created_date=date.today(),
        ))

    if linked_item_id and allow_old_bhn:
        db_audit_log(
            action="defect.override_old_bhn",
            user_id=user.get("id"),
            kitchen_id=kitchen["id"],
            target_type="defect_item",
            target_id=defect_id,
            details={"linked_bhn": linked_item_id, "weight_g": weight_g},
        )

    return {
        "id": defect_id,
        "name": name.strip(),
        "weight_grams": weight_g,
        "unit": unit,
        "defect_reason": defect_reason.strip(),
        "photo_path": photo_rel,
        "item_id": linked_item_id,
    }


@router.get("/defects")
async def list_defects(
    date_filter: Optional[str] = Query(None, alias="date"),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    kitchen: dict = Depends(require_permission("items.view")),
):
    offset = (page - 1) * PAGE_SIZE
    kid = kitchen["id"]

    q = (
        select(remote_defect_items)
        .where(remote_defect_items.c.kitchen_id == kid)
        .order_by(remote_defect_items.c.created_at.desc())
    )
    count_q = (
        select(func.count())
        .select_from(remote_defect_items)
        .where(remote_defect_items.c.kitchen_id == kid)
    )
    if date_filter:
        q = q.where(remote_defect_items.c.created_date == date_filter)
        count_q = count_q.where(remote_defect_items.c.created_date == date_filter)
    if search:
        q = q.where(remote_defect_items.c.name.ilike(f"%{search}%"))
        count_q = count_q.where(remote_defect_items.c.name.ilike(f"%{search}%"))

    with engine.connect() as c:
        total = c.execute(count_q).scalar() or 0
        rows = c.execute(q.limit(PAGE_SIZE).offset(offset)).fetchall()

    # Resolve source-BHN names in one batched lookup (avoid N+1)
    linked_ids = [r.item_id for r in rows if r.item_id]
    src_name_map: dict = {}
    if linked_ids:
        with engine.connect() as c:
            src_rows = c.execute(
                text("SELECT id, name FROM items WHERE id = ANY(:ids)"),
                {"ids": linked_ids},
            ).fetchall()
            src_name_map = {r.id: r.name for r in src_rows}

    items = []
    for r in rows:
        try:
            reason_obj = json.loads(r.reason) if r.reason else {}
        except json.JSONDecodeError:
            reason_obj = {"raw": r.reason}
        items.append({
            "id": r.id,
            "name": r.name,
            "weight_grams": r.weight_grams,
            "unit": r.unit,
            "defect_reason": reason_obj.get("defect_reason"),
            "checklist": reason_obj.get("checklist") or {},
            "notes": reason_obj.get("notes"),
            "photo_path": r.photo_path,
            "item_id": r.item_id,
            "source_item_name": src_name_map.get(r.item_id),
            "created_at": str(r.created_at) if r.created_at else None,
        })

    return {
        "defects": items,
        "page": page,
        "page_size": PAGE_SIZE,
        "total": total,
        "total_pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
    }


@router.get("/defects/{defect_id}/photo")
async def get_defect_photo(
    defect_id: str,
    kitchen: dict = Depends(require_permission("items.view")),
):
    with engine.connect() as c:
        row = c.execute(
            select(remote_defect_items.c.photo_path, remote_defect_items.c.kitchen_id)
            .where(remote_defect_items.c.id == defect_id)
        ).first()
    if not row:
        raise HTTPException(404, "Defect not found")
    if row.kitchen_id != kitchen["id"]:
        raise HTTPException(403, "Not your kitchen's defect")
    if not row.photo_path:
        raise HTTPException(404, "No photo attached")

    abs_path = os.path.join(_PHOTO_ROOT, row.photo_path)
    if not os.path.isfile(abs_path):
        raise HTTPException(404, "Photo file missing on disk")
    return FileResponse(abs_path)


@router.delete("/defects/{defect_id}")
async def delete_defect(
    defect_id: str,
    kitchen: dict = Depends(require_permission("items.edit")),
):
    with engine.begin() as c:
        row = c.execute(
            select(remote_defect_items.c.photo_path, remote_defect_items.c.kitchen_id)
            .where(remote_defect_items.c.id == defect_id)
        ).first()
        if not row:
            raise HTTPException(404, "Defect not found")
        if row.kitchen_id != kitchen["id"]:
            raise HTTPException(403, "Not your kitchen's defect")
        c.execute(
            remote_defect_items.delete().where(
                (remote_defect_items.c.id == defect_id) &
                (remote_defect_items.c.kitchen_id == kitchen["id"])
            )
        )

    if row.photo_path:
        try:
            os.remove(os.path.join(_PHOTO_ROOT, row.photo_path))
        except OSError as e:
            log.warning("photo cleanup failed for %s: %s", defect_id, e)

    return {"ok": True}
