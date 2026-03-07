import json
import os
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, text

from backend.core.database import (
    engine,
    remote_items,
    remote_trays,
    remote_tray_items,
    remote_scan_errors,
    remote_print_jobs,
)
from backend.services.printing import generate_label, db_create_print_job
from backend.services.delivery_optimizer import (
    load_schools_from_json,
    fetch_trays_packed_times,
    assign_trays_to_schools,
)
from backend.utils.auth import get_current_user
from backend.utils.validators import new_item_id
from backend.utils.datetime_helpers import now_local_iso

router = APIRouter()

PAGE_SIZE = 50

SCHOOLS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "schools.json",
)


# ── Overview ─────────────────────────────────────────────────────────────────

@router.get("/overview")
async def overview(
    date_filter: Optional[str] = Query(None, alias="date"),
    user: dict = Depends(get_current_user),
):
    today = date.fromisoformat(date_filter) if date_filter else date.today()
    with engine.connect() as c:
        received = c.execute(
            select(func.count()).select_from(remote_items)
            .where(remote_items.c.created_date_receiving == today)
        ).scalar() or 0
        processed = c.execute(
            select(func.count()).select_from(remote_items)
            .where(remote_items.c.created_date_processing == today)
        ).scalar() or 0
        packed = c.execute(
            select(func.count()).select_from(remote_trays)
            .where(remote_trays.c.created_date_packing == today)
        ).scalar() or 0
        delivered = c.execute(
            select(func.count()).select_from(remote_trays)
            .where(remote_trays.c.created_date_delivery == today)
        ).scalar() or 0
    return {
        "items_received": received,
        "items_processed": processed,
        "trays_packed": packed,
        "trays_delivered": delivered,
        "date": str(today),
    }


# ── Items ────────────────────────────────────────────────────────────────────

@router.get("/items")
async def get_items(
    date_filter: Optional[str] = Query(None, alias="date"),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    offset = (page - 1) * PAGE_SIZE
    q = select(remote_items).order_by(remote_items.c.created_at_receiving.desc())
    count_q = select(func.count()).select_from(remote_items)

    if date_filter:
        q = q.where(remote_items.c.created_date_receiving == date_filter)
        count_q = count_q.where(remote_items.c.created_date_receiving == date_filter)
    if search:
        q = q.where(remote_items.c.name.ilike(f"%{search}%"))
        count_q = count_q.where(remote_items.c.name.ilike(f"%{search}%"))

    with engine.connect() as c:
        total = c.execute(count_q).scalar() or 0
        rows = c.execute(q.limit(PAGE_SIZE).offset(offset)).fetchall()

    items = []
    for r in rows:
        items.append({
            "id": r.id,
            "name": r.name,
            "weight_grams": r.weight_grams,
            "unit": r.unit,
            "reason": r.reason,
            "receiving": r.receiving,
            "created_at_receiving": str(r.created_at_receiving) if r.created_at_receiving else None,
            "processing": r.processing,
            "created_at_processing": str(r.created_at_processing) if r.created_at_processing else None,
        })

    return {
        "items": items,
        "page": page,
        "page_size": PAGE_SIZE,
        "total": total,
        "total_pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
    }


class CreateItemRequest(BaseModel):
    name: str
    weight: float
    unit: str = "g"
    checklist: Optional[dict] = None
    notes: Optional[str] = None


@router.post("/items")
async def create_item(body: CreateItemRequest, user: dict = Depends(get_current_user)):
    # Generate unique BHN ID
    item_id = new_item_id()
    with engine.connect() as c:
        while c.execute(
            select(remote_items.c.id).where(remote_items.c.id == item_id)
        ).first():
            item_id = new_item_id()

    # Convert weight to grams
    weight_g = int(body.weight)
    if body.unit == "kg":
        weight_g = int(body.weight * 1000)

    # Build reason JSON (QC checklist + notes)
    reason_data = {}
    if body.checklist:
        reason_data["checklist"] = body.checklist
    if body.notes:
        reason_data["notes"] = body.notes
    reason = json.dumps(reason_data) if reason_data else None

    # Insert item
    with engine.begin() as c:
        c.execute(remote_items.insert().values(
            id=item_id,
            name=body.name,
            weight_grams=weight_g,
            unit=body.unit,
            reason=reason,
            receiving=True,
            created_at_receiving=datetime.now(),
            created_date_receiving=date.today(),
        ))

    # Generate label and create print job
    label = generate_label(item_id, body.name, weight_g)
    job_id = db_create_print_job(label)

    return {
        "id": item_id,
        "name": body.name,
        "weight_grams": weight_g,
        "unit": body.unit,
        "print_job_id": job_id,
    }


# ── Trays ────────────────────────────────────────────────────────────────────

@router.get("/trays")
async def get_trays(
    date_filter: Optional[str] = Query(None, alias="date"),
    page: int = Query(1, ge=1),
    user: dict = Depends(get_current_user),
):
    offset = (page - 1) * PAGE_SIZE
    q = select(remote_trays).order_by(remote_trays.c.created_at_packing.desc().nullslast())
    count_q = select(func.count()).select_from(remote_trays)

    if date_filter:
        q = q.where(remote_trays.c.created_date_packing == date_filter)
        count_q = count_q.where(remote_trays.c.created_date_packing == date_filter)

    with engine.connect() as c:
        total = c.execute(count_q).scalar() or 0
        rows = c.execute(q.limit(PAGE_SIZE).offset(offset)).fetchall()

    trays = []
    for r in rows:
        trays.append({
            "id": r.id,
            "tray_id": r.tray_id,
            "reason": r.reason,
            "packing": r.packing,
            "created_at_packing": str(r.created_at_packing) if r.created_at_packing else None,
            "delivery": r.delivery,
            "created_at_delivery": str(r.created_at_delivery) if r.created_at_delivery else None,
        })

    return {
        "trays": trays,
        "page": page,
        "page_size": PAGE_SIZE,
        "total": total,
        "total_pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
    }


# ── Delivery ─────────────────────────────────────────────────────────────────

MEALS_PER_SCAN = 10


def _compute_deliveries(n_scans: int, schools_sorted: list, delivery_rows: list) -> list:
    """
    For each school return meals_delivered and last_delivered_at given n_scans today.

    Phase 1 — full batches: school i's floor(students/10) scans come first
    in distance order. Each scan = MEALS_PER_SCAN meals to that school only.

    Phase 2 — remainder pool: remainders (students % 10) are pooled in
    distance order, filled scan-by-scan across schools.
    """
    meals: dict = {s["school_id"]: 0 for s in schools_sorted}
    last_idx: dict = {}

    # Phase 1
    remaining = n_scans
    scan_cursor = 0  # 0-based index into delivery_rows
    for school in schools_sorted:
        sid = school["school_id"]
        n_full = int(school["student_count"]) // MEALS_PER_SCAN
        used = min(n_full, remaining)
        if used > 0:
            meals[sid] += used * MEALS_PER_SCAN
            last_idx[sid] = scan_cursor + used - 1
        scan_cursor += n_full
        remaining -= used
        if remaining <= 0:
            break

    total_full_scans = sum(int(s["student_count"]) // MEALS_PER_SCAN for s in schools_sorted)

    # Phase 2
    if remaining > 0:
        combined_avail = remaining * MEALS_PER_SCAN
        cum_rem = 0
        for school in schools_sorted:
            sid = school["school_id"]
            remainder = int(school["student_count"]) % MEALS_PER_SCAN
            if remainder == 0:
                continue
            take = min(remainder, combined_avail)
            if take > 0:
                meals[sid] += take
                # Last meal position in the combined pool (1-based)
                last_meal_pos = cum_rem + take
                last_combined_scan = (last_meal_pos - 1) // MEALS_PER_SCAN
                last_idx[sid] = total_full_scans + last_combined_scan
            combined_avail -= take
            cum_rem += remainder
            if combined_avail <= 0:
                break

    result = []
    for school in schools_sorted:
        sid = school["school_id"]
        last_delivered_at = None
        idx = last_idx.get(sid)
        if idx is not None and idx < len(delivery_rows):
            ts = delivery_rows[idx].created_at_delivery
            last_delivered_at = str(ts) if ts else None
        result.append({
            "school_id": int(sid),
            "school_name": school["name"],
            "student_count": int(school["student_count"]),
            "meals_delivered": meals[sid],
            "distance": school["distance"],
            "last_delivered_at": last_delivered_at,
        })
    return result


@router.get("/delivery")
async def get_delivery(
    date_filter: Optional[str] = Query(None, alias="date"),
    user: dict = Depends(get_current_user),
):
    target_date = date.fromisoformat(date_filter) if date_filter else date.today()

    with open(SCHOOLS_FILE, "r", encoding="utf-8") as f:
        schools_raw = json.load(f)
    schools_sorted = sorted(schools_raw, key=lambda s: s["distance"])

    with engine.connect() as c:
        delivery_rows = c.execute(text("""
            SELECT tray_id, created_at_delivery FROM trays
            WHERE created_date_delivery = :d AND delivery = true
            ORDER BY created_at_delivery ASC
        """), {"d": str(target_date)}).fetchall()

    result = _compute_deliveries(len(delivery_rows), schools_sorted, delivery_rows)
    return {"assignments": result, "date": str(target_date)}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(
    date_filter: Optional[str] = Query(None, alias="date"),
    user: dict = Depends(get_current_user),
):
    from datetime import timedelta
    target = date.fromisoformat(date_filter) if date_filter else date.today()
    week_start = target - timedelta(days=6)

    with engine.connect() as c:
        # Hourly scan activity (all scan types combined)
        hourly_rows = c.execute(text("""
            SELECT hour, SUM(cnt) AS scans FROM (
                SELECT EXTRACT(HOUR FROM created_at_receiving)::int AS hour, COUNT(*) AS cnt
                FROM items WHERE created_date_receiving = :d AND created_at_receiving IS NOT NULL GROUP BY 1
                UNION ALL
                SELECT EXTRACT(HOUR FROM created_at_processing)::int, COUNT(*)
                FROM items WHERE created_date_processing = :d AND created_at_processing IS NOT NULL GROUP BY 1
                UNION ALL
                SELECT EXTRACT(HOUR FROM created_at_packing)::int, COUNT(*)
                FROM trays WHERE created_date_packing = :d AND created_at_packing IS NOT NULL GROUP BY 1
                UNION ALL
                SELECT EXTRACT(HOUR FROM created_at_delivery)::int, COUNT(*)
                FROM trays WHERE created_date_delivery = :d AND created_at_delivery IS NOT NULL GROUP BY 1
            ) sub GROUP BY hour ORDER BY hour
        """), {"d": str(target)}).fetchall()

        # 7-day receiving trend
        trend_rows = c.execute(text("""
            SELECT created_date_receiving AS day, COUNT(*) AS received
            FROM items
            WHERE created_date_receiving >= :start AND created_date_receiving <= :end
            GROUP BY created_date_receiving ORDER BY created_date_receiving
        """), {"start": str(week_start), "end": str(target)}).fetchall()

        # Avg receiving → processing duration (minutes)
        r2p = c.execute(text("""
            SELECT AVG(EXTRACT(EPOCH FROM (created_at_processing - created_at_receiving)) / 60)
            FROM items
            WHERE created_date_receiving = :d
              AND created_at_processing IS NOT NULL AND created_at_receiving IS NOT NULL
        """), {"d": str(target)}).scalar()

        # Avg packing → delivery duration (minutes)
        p2d = c.execute(text("""
            SELECT AVG(EXTRACT(EPOCH FROM (created_at_delivery - created_at_packing)) / 60)
            FROM trays
            WHERE created_date_packing = :d
              AND created_at_delivery IS NOT NULL AND created_at_packing IS NOT NULL
        """), {"d": str(target)}).scalar()

    schools = load_schools_from_json(SCHOOLS_FILE)
    total_students = sum(int(s.student_count) for s in schools)

    return {
        "date": str(target),
        "hourly_scans": [{"hour": int(r[0]), "scans": int(r[1])} for r in hourly_rows],
        "weekly_trend": [{"date": str(r[0]), "received": int(r[1])} for r in trend_rows],
        "avg_receive_to_process_mins": round(float(r2p), 1) if r2p else None,
        "avg_pack_to_deliver_mins": round(float(p2d), 1) if p2d else None,
        "total_students": total_students,
    }


# ── Scan Errors ──────────────────────────────────────────────────────────────

@router.get("/scan-errors")
async def get_scan_errors(
    page: int = Query(1, ge=1),
    user: dict = Depends(get_current_user),
):
    offset = (page - 1) * PAGE_SIZE
    with engine.connect() as c:
        total = c.execute(
            select(func.count()).select_from(remote_scan_errors)
        ).scalar() or 0
        rows = c.execute(
            select(remote_scan_errors)
            .order_by(remote_scan_errors.c.id.desc())
            .limit(PAGE_SIZE).offset(offset)
        ).fetchall()

    errors = []
    for r in rows:
        errors.append({
            "id": r.id,
            "code": r.code,
            "step": r.step,
            "created_at": r.created_at,
            "reason": r.reason,
        })

    return {
        "errors": errors,
        "page": page,
        "page_size": PAGE_SIZE,
        "total": total,
        "total_pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
    }


# ── Schools ──────────────────────────────────────────────────────────────────

@router.get("/schools")
async def get_schools(user: dict = Depends(get_current_user)):
    with open(SCHOOLS_FILE, "r", encoding="utf-8") as f:
        schools = json.load(f)
    return {"schools": schools}


# ── Countdown (public — no auth) ──────────────────────────────────────────────

SAFE_HOURS = 4


@router.get("/countdown/{tray_id}")
async def get_countdown(tray_id: str):
    from datetime import timedelta
    from backend.api.scans import _scan_allocations

    with engine.connect() as c:
        row = c.execute(
            select(
                remote_trays.c.delivery,
                remote_trays.c.created_at_delivery,
                remote_trays.c.created_date_delivery,
            ).where(remote_trays.c.tray_id == tray_id)
        ).first()

    if row is None:
        raise HTTPException(status_code=404, detail="Tray not found")

    delivered_at = None
    safe_until = None
    allocations = []

    if row.delivery and row.created_at_delivery:
        from backend.core.config import TZ_REGION
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(TZ_REGION)
        except Exception:
            tz = None
        delivered_at_dt = row.created_at_delivery
        if tz and delivered_at_dt.tzinfo is None:
            delivered_at_dt = delivered_at_dt.replace(tzinfo=tz)
        safe_until_dt = delivered_at_dt + timedelta(hours=SAFE_HOURS)
        delivered_at = delivered_at_dt.isoformat()
        safe_until = safe_until_dt.isoformat()

        with engine.connect() as c:
            scan_rows = c.execute(text("""
                SELECT tray_id FROM trays
                WHERE created_date_delivery = :d AND delivery = true
                ORDER BY created_at_delivery ASC
            """), {"d": str(row.created_date_delivery)}).fetchall()

        scan_order = [r[0] for r in scan_rows]
        try:
            n = scan_order.index(tray_id) + 1
        except ValueError:
            n = len(scan_order)

        with open(SCHOOLS_FILE, "r", encoding="utf-8") as f:
            schools = json.load(f)
        schools_sorted = sorted(schools, key=lambda s: s["distance"])
        allocations = _scan_allocations(n, schools_sorted)

    return {
        "tray_id": tray_id,
        "delivered_at": delivered_at,
        "safe_until": safe_until,
        "allocations": allocations,
    }
