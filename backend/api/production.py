"""Production batches (Phase 4).

Cerita pagi Kepala Chef:
- Buka tablet, tap "Confirm & Mulai Produksi" pada menu approved hari ini.
- Sistem auto-debit BHN dari inventory (FIFO: oldest container first) sampai
  cukup recipe × target_porsi. Setiap container yang dipakai dapat row di
  batch_consumed_items + items.processing=true.
- Timer 6 jam start dari started_at (SOP BGN: konsumsi max 6 jam dari masak).
- Selesai masak → Ahli Gizi QC approve + foto → auto-create food_samples
  (1 porsi simpan kulkas 48h).
- Status lifecycle: started → qc_pending → qc_passed → ended | aborted

Permissions:
  production.view              — head_sppg, head_kitchen, nutritionist, aslap
  production.start_batch       — head_sppg, head_kitchen
  production.end_batch         — head_sppg, head_kitchen
  production.qc_approve        — head_sppg, nutritionist
  sample.view                  — head_sppg, nutritionist, aslap, head_kitchen
  sample.manage                — head_sppg, nutritionist
"""
from datetime import datetime, timedelta, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from backend.core.database import (
    engine,
    remote_items,
    remote_saved_menus,
    remote_production_batches,
    remote_batch_consumed_items,
    remote_food_samples,
    db_get_saved_menu,
    db_audit_log,
)
from backend.utils.auth import get_current_user
from backend.utils.permissions import require_permission

router = APIRouter()

SAMPLE_RETENTION_HOURS = 48
SOP_MAX_HOURS = 6


# ── Helpers ─────────────────────────────────────────────────────────────────

def _extract_recipe(payload: dict) -> list[dict]:
    """Pull list of {name, grams} from a saved_menu payload. Handles both
    forward optimizer (week[].items) and reverse manual mode (items[]).
    Returns the FIRST day's items for week-mode (kepala chef cooks 1 menu/day).
    """
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("items"), list) and payload["items"]:
        return [{"name": it.get("name"), "grams": float(it.get("grams") or 0)} for it in payload["items"] if isinstance(it, dict)]
    week = payload.get("week")
    if isinstance(week, list) and week:
        for day in week:
            if isinstance(day, dict) and isinstance(day.get("items"), list) and day["items"]:
                return [{"name": it.get("name"), "grams": float(it.get("grams") or 0)} for it in day["items"] if isinstance(it, dict)]
    groups = payload.get("groups")
    if isinstance(groups, list) and groups:
        for g in groups:
            if isinstance(g, dict) and isinstance(g.get("week"), list):
                for day in g["week"]:
                    if isinstance(day, dict) and isinstance(day.get("items"), list) and day["items"]:
                        return [{"name": it.get("name"), "grams": float(it.get("grams") or 0)} for it in day["items"] if isinstance(it, dict)]
    return []


def _name_match(item_name: str, recipe_name: str) -> bool:
    """Loose name match: either side contains the other (case-insensitive).
    Tight enough that "Ayam Fillet" matches "Ayam Bakar" recipe via word
    overlap, while still avoiding false matches.
    """
    if not item_name or not recipe_name:
        return False
    a, b = item_name.lower().strip(), recipe_name.lower().strip()
    if a == b:
        return True
    a_words = set(w for w in a.split() if len(w) > 2)
    b_words = set(w for w in b.split() if len(w) > 2)
    return bool(a_words & b_words)


def _fifo_pick_containers(kitchen_id: int, recipe_name: str, grams_needed: float) -> list[dict]:
    """Find oldest available containers matching recipe ingredient name,
    return list of {item_id, name, available_grams, take_grams} sufficient
    to satisfy grams_needed. Caller commits the debit.

    "available" = receiving=true, processing=false, kitchen scope, and not
    yet defected/consumed past its weight. We compute leftover via:
        weight_grams - SUM(defect_items.weight_grams)
                     - SUM(batch_consumed_items.grams_used).
    """
    rows = []
    with engine.connect() as c:
        result = c.execute(text("""
            SELECT i.id, i.name, i.weight_grams, i.created_at_receiving,
                   COALESCE((SELECT SUM(d.weight_grams) FROM defect_items d WHERE d.item_id = i.id), 0) AS defected,
                   COALESCE((SELECT SUM(b.grams_used) FROM batch_consumed_items b WHERE b.item_id = i.id), 0) AS consumed
            FROM items i
            WHERE i.kitchen_id = :kid
              AND i.receiving = true
              AND COALESCE(i.processing, false) = false
            ORDER BY i.created_at_receiving ASC, i.id ASC
        """), {"kid": kitchen_id}).fetchall()

    picked: list[dict] = []
    remaining = grams_needed
    for r in result:
        if remaining <= 0:
            break
        if not _name_match(r.name or "", recipe_name):
            continue
        avail = max(0, int(r.weight_grams or 0) - int(r.defected or 0) - int(r.consumed or 0))
        if avail <= 0:
            continue
        take = min(avail, int(remaining))
        if take <= 0:
            continue
        picked.append({
            "item_id": r.id,
            "name": r.name,
            "available_grams": avail,
            "take_grams": take,
            "fully_consumed": (avail - take) <= 0,
        })
        remaining -= take

    return picked


def _row_to_batch_dict(r) -> dict:
    return {
        "id":           r.id,
        "kitchen_id":   r.kitchen_id,
        "menu_plan_id": r.menu_plan_id,
        "menu_name":    r.menu_name,
        "target_porsi": r.target_porsi,
        "started_at":   r.started_at.isoformat() if r.started_at else None,
        "ended_at":     r.ended_at.isoformat() if r.ended_at else None,
        "head_chef_id": r.head_chef_id,
        "status":       r.status,
        "notes":        r.notes,
    }


def _enrich_batch(batch_id: int, kitchen_id: int) -> dict:
    """Return batch + consumed items + samples + elapsed minutes."""
    with engine.connect() as c:
        batch_row = c.execute(
            select(remote_production_batches).where(
                (remote_production_batches.c.id == batch_id) &
                (remote_production_batches.c.kitchen_id == kitchen_id)
            )
        ).first()
        if not batch_row:
            return None
        consumed = c.execute(
            select(
                remote_batch_consumed_items.c.id,
                remote_batch_consumed_items.c.item_id,
                remote_batch_consumed_items.c.grams_used,
                remote_batch_consumed_items.c.ingredient_name,
                remote_batch_consumed_items.c.consumed_at,
            ).where(remote_batch_consumed_items.c.batch_id == batch_id)
            .order_by(remote_batch_consumed_items.c.id)
        ).all()
        samples = c.execute(
            select(remote_food_samples).where(remote_food_samples.c.batch_id == batch_id)
            .order_by(remote_food_samples.c.id)
        ).all()

    out = _row_to_batch_dict(batch_row)
    out["consumed_items"] = [
        {
            "id": r.id, "item_id": r.item_id,
            "grams_used": r.grams_used, "ingredient_name": r.ingredient_name,
            "consumed_at": r.consumed_at.isoformat() if r.consumed_at else None,
        }
        for r in consumed
    ]
    out["samples"] = [
        {
            "id": s.id, "menu_name": s.menu_name,
            "photo_path": s.photo_path, "location": s.location,
            "collected_at": s.collected_at.isoformat() if s.collected_at else None,
            "expire_at": s.expire_at.isoformat() if s.expire_at else None,
            "status": s.status,
        }
        for s in samples
    ]

    # Elapsed timer (minutes since started_at if not yet ended).
    started = batch_row.started_at
    ended = batch_row.ended_at
    end_ts = ended or datetime.now()
    elapsed_minutes = int((end_ts - started).total_seconds() / 60) if started else 0
    out["elapsed_minutes"] = elapsed_minutes
    out["sop_max_minutes"] = SOP_MAX_HOURS * 60
    out["sop_breached"] = elapsed_minutes > SOP_MAX_HOURS * 60
    return out


# ── Pydantic ────────────────────────────────────────────────────────────────


class StartBatchBody(BaseModel):
    menu_plan_id: int
    target_porsi: int = Field(..., gt=0)
    notes:        Optional[str] = None
    dry_run:      bool = False    # if true, return debit plan without committing


class EndBatchBody(BaseModel):
    notes: Optional[str] = None


class QCApproveBody(BaseModel):
    photo_path:        Optional[str] = None
    sample_location:   Optional[str] = "Kulkas QC"
    sample_photo_path: Optional[str] = None
    notes:             Optional[str] = None


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/production/today-menu")
async def today_menu(
    target_date: Optional[str] = None,
    kitchen: dict = Depends(require_permission("production.view")),
):
    """List approved/locked menus targeting today (or `target_date`).
    Powers the tablet "Menu Hari Ini" view.
    """
    d = target_date or str(date.today())
    with engine.connect() as c:
        rows = c.execute(
            select(
                remote_saved_menus.c.id,
                remote_saved_menus.c.name,
                remote_saved_menus.c.status,
                remote_saved_menus.c.target_date,
                remote_saved_menus.c.target_school_id,
            ).where(
                (remote_saved_menus.c.kitchen_id == kitchen["id"]) &
                (remote_saved_menus.c.status.in_(["approved", "locked"])) &
                (
                    (remote_saved_menus.c.target_date == d) |
                    (remote_saved_menus.c.target_date.is_(None))
                )
            ).order_by(remote_saved_menus.c.target_date.desc().nullslast(), remote_saved_menus.c.id.desc())
        ).all()

    menus = []
    for r in rows:
        full = db_get_saved_menu(kitchen["id"], r.id)
        if not full:
            continue
        recipe = _extract_recipe(full.get("payload") or {})
        menus.append({
            "id": r.id, "name": r.name, "status": r.status,
            "target_date": str(r.target_date) if r.target_date else None,
            "target_school_id": r.target_school_id,
            "recipe": recipe,
        })
    return {"date": d, "menus": menus}


@router.get("/production/batches")
async def list_batches(
    status: Optional[str] = None,
    kitchen: dict = Depends(require_permission("production.view")),
):
    with engine.connect() as c:
        q = select(remote_production_batches).where(remote_production_batches.c.kitchen_id == kitchen["id"])
        if status:
            q = q.where(remote_production_batches.c.status == status)
        rows = c.execute(q.order_by(remote_production_batches.c.started_at.desc())).all()
    return {"batches": [_row_to_batch_dict(r) for r in rows]}


@router.get("/production/batches/{batch_id}")
async def get_batch(
    batch_id: int,
    kitchen: dict = Depends(require_permission("production.view")),
):
    out = _enrich_batch(batch_id, kitchen["id"])
    if not out:
        raise HTTPException(404, "Batch tidak ditemukan.")
    return out


@router.post("/production/batches", status_code=201)
async def start_batch(
    body: StartBatchBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("production.start_batch")),
):
    """Start a production batch. FIFO-debits BHN containers from inventory.

    `dry_run=true` returns the debit plan + shortage info without committing —
    useful for tablet to preview "ada cukup ayam gak?" before tap.
    """
    menu = db_get_saved_menu(kitchen["id"], body.menu_plan_id)
    if not menu:
        raise HTTPException(404, "Menu tidak ditemukan.")
    if menu.get("status") not in ("approved", "locked"):
        raise HTTPException(400, f"Menu harus approved/locked. Status sekarang: {menu.get('status')}.")

    recipe = _extract_recipe(menu.get("payload") or {})
    if not recipe:
        raise HTTPException(400, "Menu tidak punya recipe items.")

    # Compute total grams needed per ingredient, then FIFO-pick containers.
    plan: list[dict] = []
    shortages: list[dict] = []
    for ing in recipe:
        if not ing.get("name") or not ing.get("grams"):
            continue
        need = float(ing["grams"]) * body.target_porsi
        picks = _fifo_pick_containers(kitchen["id"], ing["name"], need)
        taken = sum(p["take_grams"] for p in picks)
        plan.append({
            "ingredient_name": ing["name"],
            "grams_needed": int(need),
            "grams_picked": taken,
            "containers": picks,
            "shortage_grams": max(0, int(need) - taken),
        })
        if taken < need:
            shortages.append({"ingredient_name": ing["name"], "needed": int(need), "available": taken})

    if shortages and not body.dry_run:
        parts = [
            "{} (kurang {}g)".format(s["ingredient_name"], s["needed"] - s["available"])
            for s in shortages
        ]
        raise HTTPException(400, "Bahan kurang: " + ", ".join(parts))

    if body.dry_run:
        return {"dry_run": True, "menu": menu.get("name"), "target_porsi": body.target_porsi, "plan": plan, "shortages": shortages}

    # Commit: insert batch row + consumed_items + flip items.processing=true
    # for fully-consumed containers (partial consumption keeps processing=false
    # so the leftover is still pickable for the next batch).
    today = date.today()
    now = datetime.now()
    with engine.begin() as c:
        res = c.execute(
            remote_production_batches.insert()
            .values(
                kitchen_id=kitchen["id"],
                menu_plan_id=body.menu_plan_id,
                menu_name=menu.get("name"),
                target_porsi=body.target_porsi,
                head_chef_id=user.get("id"),
                status="started",
                notes=body.notes,
            )
            .returning(remote_production_batches.c.id)
        )
        batch_id = res.scalar()

        for line in plan:
            for pick in line["containers"]:
                c.execute(
                    remote_batch_consumed_items.insert().values(
                        batch_id=batch_id,
                        item_id=pick["item_id"],
                        grams_used=pick["take_grams"],
                        ingredient_name=line["ingredient_name"],
                    )
                )
                if pick["fully_consumed"]:
                    c.execute(
                        remote_items.update()
                        .where(remote_items.c.id == pick["item_id"])
                        .values(
                            processing=True,
                            created_at_processing=now,
                            created_date_processing=today,
                        )
                    )

    db_audit_log(
        action="batch.started",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="batch",
        target_id=str(batch_id),
        after_value={
            "menu_plan_id": body.menu_plan_id,
            "menu_name": menu.get("name"),
            "target_porsi": body.target_porsi,
            "ingredients": [{"name": p["ingredient_name"], "grams": p["grams_picked"], "containers": len(p["containers"])} for p in plan],
        },
    )
    return _enrich_batch(batch_id, kitchen["id"])


@router.post("/production/batches/{batch_id}/qc")
async def qc_approve(
    batch_id: int,
    body: QCApproveBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("production.qc_approve")),
):
    """Ahli Gizi tap "QC OK" + foto → auto-create food_samples row (48h retention)."""
    batch = _enrich_batch(batch_id, kitchen["id"])
    if not batch:
        raise HTTPException(404, "Batch tidak ditemukan.")
    if batch["status"] not in ("started", "qc_pending"):
        raise HTTPException(400, f"Batch status harus 'started' atau 'qc_pending'. Sekarang: {batch['status']}.")

    expire_at = datetime.now() + timedelta(hours=SAMPLE_RETENTION_HOURS)
    with engine.begin() as c:
        c.execute(
            remote_production_batches.update()
            .where(remote_production_batches.c.id == batch_id)
            .values(status="qc_passed")
        )
        c.execute(
            remote_food_samples.insert().values(
                kitchen_id=kitchen["id"],
                batch_id=batch_id,
                menu_name=batch["menu_name"] or "Unknown",
                photo_path=body.sample_photo_path,
                location=body.sample_location,
                collected_by=user.get("id"),
                expire_at=expire_at,
                status="active",
                notes=body.notes,
            )
        )

    db_audit_log(
        action="batch.qc_approved",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="batch",
        target_id=str(batch_id),
        after_value={"status": "qc_passed", "sample_expire_at": expire_at.isoformat()},
    )
    return _enrich_batch(batch_id, kitchen["id"])


@router.post("/production/batches/{batch_id}/end")
async def end_batch(
    batch_id: int,
    body: EndBatchBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("production.end_batch")),
):
    """Mark batch as ended (production complete). QC ideally done first, but
    we allow end-without-QC for emergencies (logged in audit).
    """
    batch = _enrich_batch(batch_id, kitchen["id"])
    if not batch:
        raise HTTPException(404, "Batch tidak ditemukan.")
    if batch["status"] in ("ended", "aborted"):
        raise HTTPException(400, f"Batch sudah selesai (status={batch['status']}).")

    with engine.begin() as c:
        c.execute(
            remote_production_batches.update()
            .where(remote_production_batches.c.id == batch_id)
            .values(status="ended", ended_at=datetime.now(), notes=body.notes)
        )

    db_audit_log(
        action="batch.ended",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="batch",
        target_id=str(batch_id),
        before_value={"status": batch["status"]},
        after_value={"status": "ended", "elapsed_minutes": batch["elapsed_minutes"]},
    )
    return _enrich_batch(batch_id, kitchen["id"])


# ── Samples ────────────────────────────────────────────────────────────────


@router.get("/samples")
async def list_samples(
    status: Optional[str] = None,
    kitchen: dict = Depends(require_permission("sample.view")),
):
    with engine.connect() as c:
        q = select(remote_food_samples).where(remote_food_samples.c.kitchen_id == kitchen["id"])
        if status:
            q = q.where(remote_food_samples.c.status == status)
        rows = c.execute(q.order_by(remote_food_samples.c.collected_at.desc())).all()
    now = datetime.now()
    return {"samples": [
        {
            "id": s.id, "batch_id": s.batch_id, "menu_name": s.menu_name,
            "photo_path": s.photo_path, "location": s.location,
            "collected_at": s.collected_at.isoformat() if s.collected_at else None,
            "expire_at": s.expire_at.isoformat() if s.expire_at else None,
            "status": s.status, "notes": s.notes,
            "expired": (s.expire_at and s.expire_at < now) if s.expire_at else False,
        }
        for s in rows
    ]}
