"""Distribution layer (Phase 5).

Layered ON TOP of existing scan flow + `_scan_allocations()` smart batching
(MEALS_PER_SCAN=10, remainder-combine logic in `backend/api/scans.py`).
We do NOT modify that algorithm. We add:

  • Wave 1 vs Wave 2 classification — derived from school.age_group.
  • Today's per-school aggregate dashboard (target / dispatched / confirmed / sisa).
  • Public guru-confirmed receipt endpoint (no auth, gated by tray_id existence).
  • Leftover porsi log + categorisation.
  • Vehicle / driver master CRUD.

Permissions:
  distribution.view       — head_sppg, head_kitchen, nutritionist, accountant, aslap
  distribution.dispatch   — head_sppg, aslap
  distribution.leftover   — head_sppg, aslap
  vehicle.manage          — head_sppg, accountant
  driver.manage           — head_sppg, accountant
  (confirm-receipt is public — guru tap di HP, no login)
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from backend.core.database import (
    engine,
    remote_delivery_confirmations,
    remote_delivery_leftovers,
    remote_vehicles,
    remote_drivers,
    remote_trays,
    db_list_schools,
    db_audit_log,
)
from backend.utils.auth import get_current_user
from backend.utils.permissions import require_permission

router = APIRouter()

VALID_LEFTOVER_KATEGORI = ("return", "extra", "disposal")


# ── Wave classification ─────────────────────────────────────────────────────

WAVE1_KEYWORDS = ("PAUD", "TK (4-6", "SD (7-9")  # match age_group prefix


def school_to_wave(age_group: str) -> int:
    """Wave 1 (08:00) = PAUD, TK, SD kelas 1-3 (age 7-9).
    Wave 2 (10:00) = SD kelas 4-6 (age 10-12), SMP, SMA, ibu hamil.
    Defaults to wave 2 when age_group is unknown.
    """
    s = (age_group or "").upper()
    for kw in WAVE1_KEYWORDS:
        if s.startswith(kw.upper()):
            return 1
    return 2


@router.get("/distributions/schools-by-wave")
async def schools_by_wave(
    kitchen: dict = Depends(require_permission("distribution.view")),
):
    """Group active schools by wave for the ASLAP dispatch tablet."""
    schools = db_list_schools(kitchen["id"], active_only=True)
    waves: dict = {1: [], 2: []}
    for s in schools:
        w = school_to_wave(s.get("age_group") or "")
        waves[w].append({**s, "wave": w})
    return {
        "wave_1": waves[1],
        "wave_2": waves[2],
        "wave_1_total_students": sum(s["student_count"] for s in waves[1]),
        "wave_2_total_students": sum(s["student_count"] for s in waves[2]),
    }


# ── Today's aggregate dashboard ─────────────────────────────────────────────


@router.get("/distributions/today")
async def distributions_today(
    target_date: Optional[str] = None,
    kitchen: dict = Depends(require_permission("distribution.view")),
):
    """Per-school aggregate: target / dispatched / confirmed / leftover.

    target     = school.student_count (snapshot from master data)
    dispatched = sum of n_trays * MEALS_PER_SCAN allocated to school today
                 (computed via existing _scan_allocations())
    confirmed  = sum(delivery_confirmations.confirmed_count) for today × school
    leftover   = sum(delivery_leftovers.qty) by kategori for today × school
    """
    from backend.api.scans import _scan_allocations
    d = target_date or str(date.today())

    schools = db_list_schools(kitchen["id"], active_only=True)
    schools_sorted = sorted(schools, key=lambda s: s["distance"])

    # Load today's delivery scans for this kitchen.
    with engine.connect() as c:
        scan_rows = c.execute(text("""
            SELECT tray_id, created_at_delivery FROM trays
            WHERE created_date_delivery = :d AND delivery = true AND kitchen_id = :kid
            ORDER BY created_at_delivery ASC
        """), {"d": d, "kid": kitchen["id"]}).fetchall()

        confirms = c.execute(text("""
            SELECT school_name, SUM(confirmed_count) AS total
            FROM delivery_confirmations
            WHERE kitchen_id = :kid AND DATE(confirmed_at) = :d
            GROUP BY school_name
        """), {"d": d, "kid": kitchen["id"]}).fetchall()

        leftovers = c.execute(text("""
            SELECT school_name, kategori, SUM(qty) AS total
            FROM delivery_leftovers
            WHERE kitchen_id = :kid AND created_date = :d
            GROUP BY school_name, kategori
        """), {"d": d, "kid": kitchen["id"]}).fetchall()

    confirm_map = {r.school_name: int(r.total or 0) for r in confirms}
    leftover_map: dict = {}
    for r in leftovers:
        leftover_map.setdefault(r.school_name, {})[r.kategori] = int(r.total or 0)

    # Replay _scan_allocations for each scan to determine dispatched-per-school.
    dispatched_per_school: dict = {}
    for n_idx in range(1, len(scan_rows) + 1):
        allocs = _scan_allocations(n_idx, schools_sorted)
        for a in allocs:
            dispatched_per_school[a["school"]] = dispatched_per_school.get(a["school"], 0) + a["n_trays"]

    # Build per-school output.
    per_school = []
    total_target = total_dispatched = total_confirmed = 0
    for s in schools_sorted:
        target = int(s.get("student_count") or 0)
        dispatched = dispatched_per_school.get(s["name"], 0)
        confirmed = confirm_map.get(s["name"], 0)
        lo = leftover_map.get(s["name"], {})
        sisa = sum(lo.values())
        wave = school_to_wave(s.get("age_group") or "")
        per_school.append({
            "school_id": s.get("id"),
            "school_name": s["name"],
            "wave": wave,
            "level": s.get("level"),
            "age_group": s.get("age_group"),
            "target": target,
            "dispatched": dispatched,
            "confirmed": confirmed,
            "leftover_total": sisa,
            "leftover_by_kategori": lo,
            "gap_dispatched": target - dispatched,        # negative = over-shipped
            "gap_confirmed":  dispatched - confirmed,     # positive = belum confirm
        })
        total_target += target
        total_dispatched += dispatched
        total_confirmed += confirmed

    return {
        "date": d,
        "total_target": total_target,
        "total_dispatched": total_dispatched,
        "total_confirmed": total_confirmed,
        "scans_today": len(scan_rows),
        "schools": per_school,
    }


# ── Public confirm-receipt (guru) ───────────────────────────────────────────


class ConfirmReceiptBody(BaseModel):
    school_name:     str = Field(..., max_length=150)
    confirmed_count: int = Field(..., ge=0)
    notes:           Optional[str] = None
    photo_path:      Optional[str] = None


@router.post("/countdown/{tray_id}/confirm-receipt")
async def confirm_receipt(tray_id: str, body: ConfirmReceiptBody, request: Request):
    """Public — guru sekolah scan QR di label, tap "Konfirmasi Terima X ompreng".

    No auth required: gated by tray_id existence + IP/user-agent logged. The
    `school_name` is supplied by the guru (we trust + audit, not enforce).
    """
    with engine.connect() as c:
        tray = c.execute(
            select(remote_trays.c.kitchen_id, remote_trays.c.delivery)
            .where(remote_trays.c.tray_id == tray_id)
            .order_by(remote_trays.c.created_at_delivery.desc().nullslast())
            .limit(1)
        ).first()
    if not tray:
        raise HTTPException(404, "Tray tidak ditemukan.")
    if not tray.delivery:
        raise HTTPException(400, "Tray belum di-delivery — guru belum bisa konfirmasi.")

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:255]

    with engine.begin() as c:
        res = c.execute(
            remote_delivery_confirmations.insert()
            .values(
                kitchen_id=tray.kitchen_id,
                tray_id=tray_id,
                school_name=body.school_name,
                confirmed_count=body.confirmed_count,
                ip_address=ip,
                user_agent=ua,
                notes=body.notes,
                photo_path=body.photo_path,
            )
            .returning(remote_delivery_confirmations.c.id)
        )
        new_id = res.scalar()

    db_audit_log(
        action="distribution.receipt_confirmed",
        kitchen_id=tray.kitchen_id,
        target_type="tray",
        target_id=tray_id,
        ip_address=ip,
        details={"school_name": body.school_name, "count": body.confirmed_count},
    )
    return {"ok": True, "confirmation_id": new_id}


@router.get("/countdown/{tray_id}/confirmations")
async def list_confirmations_public(tray_id: str):
    """Public — show prior confirmations for this tray (guru can see what's been logged).
    Sorted oldest first. Used by Countdown page to show running total.
    """
    with engine.connect() as c:
        rows = c.execute(
            select(remote_delivery_confirmations).where(remote_delivery_confirmations.c.tray_id == tray_id)
            .order_by(remote_delivery_confirmations.c.confirmed_at.asc())
        ).all()
    return {
        "tray_id": tray_id,
        "confirmations": [
            {
                "id": r.id,
                "school_name": r.school_name,
                "confirmed_count": r.confirmed_count,
                "notes": r.notes,
                "confirmed_at": r.confirmed_at.isoformat() if r.confirmed_at else None,
            }
            for r in rows
        ],
    }


# ── Leftovers ───────────────────────────────────────────────────────────────


class LeftoverBody(BaseModel):
    qty:          int = Field(..., gt=0)
    kategori:     str = Field(..., max_length=20)   # return | extra | disposal
    tray_id:      Optional[str] = None
    school_id:    Optional[int] = None
    school_name:  Optional[str] = Field(None, max_length=150)
    photo_path:   Optional[str] = None
    notes:        Optional[str] = None


@router.post("/distributions/leftovers", status_code=201)
async def create_leftover(
    body: LeftoverBody,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("distribution.leftover")),
):
    if body.kategori not in VALID_LEFTOVER_KATEGORI:
        raise HTTPException(400, f"Kategori invalid. Valid: {', '.join(VALID_LEFTOVER_KATEGORI)}")
    today = date.today()
    with engine.begin() as c:
        res = c.execute(
            remote_delivery_leftovers.insert()
            .values(
                kitchen_id=kitchen["id"],
                tray_id=body.tray_id,
                school_id=body.school_id,
                school_name=body.school_name,
                qty=body.qty,
                kategori=body.kategori,
                photo_path=body.photo_path,
                notes=body.notes,
                created_by=user.get("id"),
                created_date=today,
            )
            .returning(remote_delivery_leftovers.c.id)
        )
        new_id = res.scalar()

    db_audit_log(
        action="distribution.leftover_logged",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="leftover",
        target_id=str(new_id),
        after_value={"qty": body.qty, "kategori": body.kategori, "school_name": body.school_name},
    )
    return {"id": new_id, "ok": True}


@router.get("/distributions/leftovers")
async def list_leftovers(
    target_date: Optional[str] = None,
    kategori: Optional[str] = None,
    kitchen: dict = Depends(require_permission("distribution.view")),
):
    d = target_date or str(date.today())
    with engine.connect() as c:
        q = select(remote_delivery_leftovers).where(
            (remote_delivery_leftovers.c.kitchen_id == kitchen["id"]) &
            (remote_delivery_leftovers.c.created_date == d)
        )
        if kategori:
            q = q.where(remote_delivery_leftovers.c.kategori == kategori)
        rows = c.execute(q.order_by(remote_delivery_leftovers.c.created_at.desc())).all()
    return {
        "date": d,
        "leftovers": [
            {
                "id": r.id, "tray_id": r.tray_id, "school_name": r.school_name,
                "qty": r.qty, "kategori": r.kategori, "notes": r.notes,
                "photo_path": r.photo_path,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


# ── Vehicles + Drivers (simple master) ──────────────────────────────────────


class VehicleIn(BaseModel):
    plate:           str = Field(..., max_length=20)
    model:           Optional[str] = Field(None, max_length=100)
    capacity_porsi:  int = Field(0, ge=0)


class DriverIn(BaseModel):
    name:        str = Field(..., max_length=150)
    phone:       Optional[str] = Field(None, max_length=30)
    license_no:  Optional[str] = Field(None, max_length=40)


@router.get("/vehicles")
async def list_vehicles(kitchen: dict = Depends(require_permission("distribution.view"))):
    with engine.connect() as c:
        rows = c.execute(
            select(remote_vehicles).where(
                (remote_vehicles.c.kitchen_id == kitchen["id"]) &
                (remote_vehicles.c.is_active.is_(True))
            ).order_by(remote_vehicles.c.id)
        ).all()
    return {"vehicles": [dict(r._mapping) for r in rows]}


@router.post("/vehicles", status_code=201)
async def create_vehicle(
    body: VehicleIn,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("vehicle.manage")),
):
    with engine.begin() as c:
        res = c.execute(
            remote_vehicles.insert()
            .values(kitchen_id=kitchen["id"], **body.model_dump(), is_active=True)
            .returning(remote_vehicles.c.id)
        )
        new_id = res.scalar()
    db_audit_log(
        action="vehicle.create",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="vehicle",
        target_id=str(new_id),
        after_value=body.model_dump(),
    )
    return {"id": new_id, **body.model_dump()}


@router.delete("/vehicles/{vid}")
async def delete_vehicle(
    vid: int,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("vehicle.manage")),
):
    with engine.begin() as c:
        c.execute(
            remote_vehicles.update()
            .where((remote_vehicles.c.id == vid) & (remote_vehicles.c.kitchen_id == kitchen["id"]))
            .values(is_active=False)
        )
    db_audit_log(
        action="vehicle.deactivate",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        target_type="vehicle",
        target_id=str(vid),
    )
    return {"ok": True}


@router.get("/drivers")
async def list_drivers(kitchen: dict = Depends(require_permission("distribution.view"))):
    with engine.connect() as c:
        rows = c.execute(
            select(remote_drivers).where(
                (remote_drivers.c.kitchen_id == kitchen["id"]) &
                (remote_drivers.c.is_active.is_(True))
            ).order_by(remote_drivers.c.id)
        ).all()
    return {"drivers": [dict(r._mapping) for r in rows]}


@router.post("/drivers", status_code=201)
async def create_driver(
    body: DriverIn,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("driver.manage")),
):
    with engine.begin() as c:
        res = c.execute(
            remote_drivers.insert()
            .values(kitchen_id=kitchen["id"], **body.model_dump(), is_active=True)
            .returning(remote_drivers.c.id)
        )
        new_id = res.scalar()
    db_audit_log(
        action="driver.create",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        org_id=user.get("org_id"),
        target_type="driver",
        target_id=str(new_id),
        after_value=body.model_dump(),
    )
    return {"id": new_id, **body.model_dump()}


@router.delete("/drivers/{did}")
async def delete_driver(
    did: int,
    user: dict = Depends(get_current_user),
    kitchen: dict = Depends(require_permission("driver.manage")),
):
    with engine.begin() as c:
        c.execute(
            remote_drivers.update()
            .where((remote_drivers.c.id == did) & (remote_drivers.c.kitchen_id == kitchen["id"]))
            .values(is_active=False)
        )
    db_audit_log(
        action="driver.deactivate",
        user_id=user.get("id"),
        kitchen_id=kitchen["id"],
        target_type="driver",
        target_id=str(did),
    )
    return {"ok": True}
