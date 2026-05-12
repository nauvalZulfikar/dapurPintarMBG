import os
import json
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text

from backend.core.database import (
    engine,
    remote_items,
    remote_trays,
    remote_tray_items,
    remote_scan_errors,
    db_get_kitchen_by_scanner_key,
    db_get_kitchen,
    db_list_schools,
)
from backend.services.printing import create_and_push_job
from backend.utils.datetime_helpers import now_local_iso
from backend.api.sse import broadcast

router = APIRouter()

BHN_PREFIX = "BHN-"
TRAY_PREFIX = "TRY-"
TRAY_LEN = 12

SCHOOLS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "schools.json",
)
COUNTDOWN_BASE_URL = (
    os.getenv("COUNTDOWN_BASE_URL") or
    os.getenv("API_BASE_URL", "http://localhost:8000")
).rstrip("/")

# Legacy single-tenant key; used as fallback if a kitchen hasn't been seeded yet.
_LEGACY_SCANNER_KEY = os.getenv("SCANNER_KEY", "")


class ScanRequest(BaseModel):
    code: str
    step: str  # "Processing" | "Packing" | "Delivery"


def _resolve_scanner_kitchen(key: Optional[str]) -> dict:
    """Resolve a scanner key to its kitchen. Scanner devices have no JWT,
    so the request is authenticated (and tenant-routed) by the key alone."""
    if not key:
        raise HTTPException(status_code=403, detail="Missing scanner key")

    kitchen = db_get_kitchen_by_scanner_key(key)
    if kitchen:
        return kitchen

    # Transitional: before migration runs, the legacy global key still maps
    # all scans to kitchen id=1.
    if _LEGACY_SCANNER_KEY and key == _LEGACY_SCANNER_KEY:
        fallback = db_get_kitchen(1)
        if fallback:
            return fallback

    raise HTTPException(status_code=403, detail="Invalid scanner key")


# ── Parsing ──────────────────────────────────────────────────────────────────

def extract_code(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    lower = s.lower()
    if any(k in lower for k in ("tray_id=", "ingredient_id=", "id=", "barcode=")):
        for part in s.replace("?", "&").split("&"):
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k.strip().lower() in {"tray_id", "ingredient_id", "id", "barcode"} and v.strip():
                return v.strip()
    for prefix in (TRAY_PREFIX, BHN_PREFIX):
        idx = s.find(prefix)
        if idx != -1:
            chunk = s[idx:idx + 64].split()[0]
            for delim in ["&", "?", "#", "/", "\\", '"', "'", ",", ";", ")", "(", "]", "[", "}", "{"]:
                chunk = chunk.split(delim)[0]
            return chunk
    return s


# ── Validators (all scoped by kitchen_id) ────────────────────────────────────

def validate_processing(code: str, kitchen_id: int) -> tuple[bool, str]:
    if not code:
        return False, "EMPTY_SCAN"
    if not code.upper().startswith(BHN_PREFIX):
        return False, f"NOT_AN_INGREDIENT_CODE (expected BHN-, got: {code[:8]})"
    with engine.connect() as c:
        row = c.execute(
            select(remote_items.c.receiving, remote_items.c.processing)
            .where(
                (remote_items.c.id == code) &
                (remote_items.c.kitchen_id == kitchen_id)
            )
        ).first()
    if row is None:
        return False, "INGREDIENT_NOT_FOUND"
    if not row.receiving:
        return False, "NOT_RECEIVED"
    if row.processing:
        return False, "ALREADY_PROCESSED"
    return True, ""


def validate_packing(code: str, kitchen_id: int) -> tuple[bool, str]:
    if not code:
        return False, "EMPTY_SCAN"
    if not code.upper().startswith(TRAY_PREFIX):
        return False, f"NOT_A_TRAY_CODE (expected TRY-, got: {code[:8]})"
    if len(code) != TRAY_LEN:
        return False, f"INVALID_TRAY_ID_LENGTH (expected {TRAY_LEN}, got {len(code)})"
    with engine.connect() as c:
        registered = c.execute(
            select(remote_tray_items.c.tray_id)
            .where(
                (remote_tray_items.c.tray_id == code) &
                (remote_tray_items.c.kitchen_id == kitchen_id)
            )
        ).first() is not None
        row = c.execute(
            select(remote_trays.c.packing, remote_trays.c.created_date_packing)
            .where(
                (remote_trays.c.tray_id == code) &
                (remote_trays.c.kitchen_id == kitchen_id)
            )
        ).first()
    if not registered:
        return False, "TRAY_NOT_REGISTERED"
    if row and row.packing and row.created_date_packing == date.today():
        return False, "ALREADY_PACKED_TODAY"
    return True, ""


def validate_delivery(code: str, kitchen_id: int) -> tuple[bool, str]:
    if not code:
        return False, "EMPTY_SCAN"
    if not code.upper().startswith(TRAY_PREFIX):
        return False, f"NOT_A_TRAY_CODE (expected TRY-, got: {code[:8]})"
    if len(code) != TRAY_LEN:
        return False, f"INVALID_TRAY_ID_LENGTH (expected {TRAY_LEN}, got {len(code)})"
    with engine.connect() as c:
        registered = c.execute(
            select(remote_tray_items.c.tray_id)
            .where(
                (remote_tray_items.c.tray_id == code) &
                (remote_tray_items.c.kitchen_id == kitchen_id)
            )
        ).first() is not None
        row = c.execute(
            select(
                remote_trays.c.packing,
                remote_trays.c.delivery,
                remote_trays.c.created_date_delivery,
            ).where(
                (remote_trays.c.tray_id == code) &
                (remote_trays.c.kitchen_id == kitchen_id)
            )
        ).first()
    if not registered:
        return False, "TRAY_NOT_REGISTERED"
    if not row or not row.packing:
        return False, "NOT_PACKED"
    if row.delivery and row.created_date_delivery == date.today():
        return False, "ALREADY_DELIVERED_TODAY"
    return True, ""


# ── Apply scan to DB (always scoped by kitchen) ─────────────────────────────

def apply_processing(code: str, kitchen_id: int):
    with engine.begin() as c:
        c.execute(
            remote_items.update()
            .where(
                (remote_items.c.id == code) &
                (remote_items.c.kitchen_id == kitchen_id)
            )
            .values(
                processing=True,
                created_at_processing=datetime.now(),
                created_date_processing=date.today(),
            )
        )


def apply_packing(code: str, kitchen_id: int):
    with engine.begin() as c:
        existing = c.execute(
            select(remote_trays.c.tray_id).where(
                (remote_trays.c.tray_id == code) &
                (remote_trays.c.kitchen_id == kitchen_id)
            )
        ).first()
        if existing:
            c.execute(
                remote_trays.update()
                .where(
                    (remote_trays.c.tray_id == code) &
                    (remote_trays.c.kitchen_id == kitchen_id)
                )
                .values(
                    packing=True,
                    created_at_packing=datetime.now(),
                    created_date_packing=date.today(),
                )
            )
        else:
            c.execute(
                remote_trays.insert().values(
                    tray_id=code,
                    kitchen_id=kitchen_id,
                    packing=True,
                    created_at_packing=datetime.now(),
                    created_date_packing=date.today(),
                )
            )


def apply_delivery(code: str, kitchen_id: int):
    from backend.core.config import TZ_REGION
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(tz=ZoneInfo(TZ_REGION))
    except Exception:
        now = datetime.now()
    with engine.begin() as c:
        c.execute(
            remote_trays.update()
            .where(
                (remote_trays.c.tray_id == code) &
                (remote_trays.c.kitchen_id == kitchen_id)
            )
            .values(
                delivery=True,
                created_at_delivery=now,
                created_date_delivery=now.date(),
            )
        )


def log_scan_error(code: str, step: str, reason: str, kitchen_id: int):
    with engine.begin() as c:
        c.execute(
            remote_scan_errors.insert().values(
                kitchen_id=kitchen_id,
                code=code,
                step=step,
                created_at=now_local_iso(),
                reason=reason,
            )
        )


# ── Delivery allocation ─────────────────────────────────────────────────────

MEALS_PER_SCAN = 10


def _scan_allocations(n: int, schools_sorted: list) -> list:
    """Return [{school, n_trays}] for the n-th delivery scan of the day."""
    full_offset = 0
    for school in schools_sorted:
        n_full = int(school["student_count"]) // MEALS_PER_SCAN
        if n <= full_offset + n_full:
            return [{"school": school["name"], "n_trays": MEALS_PER_SCAN}]
        full_offset += n_full

    rem_scan_n = n - full_offset
    meal_start = (rem_scan_n - 1) * MEALS_PER_SCAN + 1
    meal_end = rem_scan_n * MEALS_PER_SCAN

    allocations = []
    cumulative = 0
    for school in schools_sorted:
        remainder = int(school["student_count"]) % MEALS_PER_SCAN
        if remainder == 0:
            continue
        overlap_start = max(meal_start, cumulative + 1)
        overlap_end = min(meal_end, cumulative + remainder)
        if overlap_start <= overlap_end:
            allocations.append({"school": school["name"], "n_trays": overlap_end - overlap_start + 1})
        cumulative += remainder
        if cumulative >= meal_end:
            break

    return allocations


async def process_delivery_allocation(tray_id: str, kitchen: dict) -> dict:
    kitchen_id = kitchen["id"]
    # Phase 1: schools come from DB (kitchen-scoped). Fallback to JSON only if
    # the DB has no rows for this kitchen (e.g. fresh tenant with no master data).
    schools = db_list_schools(kitchen_id, active_only=True)
    if not schools and os.path.isfile(SCHOOLS_FILE):
        with open(SCHOOLS_FILE, "r", encoding="utf-8") as f:
            schools = json.load(f)
    schools_sorted = sorted(schools, key=lambda s: s["distance"])

    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT tray_id FROM trays
            WHERE created_date_delivery = :today AND delivery = true AND kitchen_id = :kid
            ORDER BY created_at_delivery ASC
        """), {"today": str(date.today()), "kid": kitchen_id}).fetchall()

    scan_order = [r[0] for r in rows]
    try:
        n = scan_order.index(tray_id) + 1
    except ValueError:
        n = len(scan_order)

    allocations = _scan_allocations(n, schools_sorted)

    qr_link = f"{COUNTDOWN_BASE_URL}/countdown/{tray_id}"
    y = 15
    lines = ""
    for alloc in allocations:
        lines += f'TEXT 10,{y},"0",0,6,6,"{alloc["school"]} x{alloc["n_trays"]}"\n'
        y += 12

    tspl = f"""
SIZE 50 mm, 21 mm
GAP 1 mm, 0 mm
SPEED 4
DENSITY 15
CLS
{lines}
QRCODE 300,5,L,3,A,0,"{qr_link}"
PRINT 1,1
"""
    await create_and_push_job(tspl, kitchen_id=kitchen_id, printer_name=kitchen.get("printer_name"))
    return {"tray_id": tray_id, "allocations": allocations}


# ── Main endpoint ────────────────────────────────────────────────────────────

VALIDATORS = {
    "Processing": validate_processing,
    "Packing":    validate_packing,
    "Delivery":   validate_delivery,
}

APPLIERS = {
    "Processing": apply_processing,
    "Packing":    apply_packing,
    "Delivery":   apply_delivery,
}


@router.post("/scans")
async def post_scan(
    body: ScanRequest,
    x_scanner_key: Optional[str] = Header(None, alias="X-Scanner-Key"),
    authorization: Optional[str] = Header(None),
):
    """Phase 4 — dual-auth: prefer JWT (tablet/Kepala Chef) over scanner key.

    Existing scanner-key flow keeps working unchanged. When a JWT is provided,
    we resolve the user's active kitchen via auth.get_current_user_from_token
    and require the `production.processing_scan` permission for the Processing
    step. Receiving / Packing / Delivery still accept scanner-key auth (used
    by USB scanner devices that have no login).
    """
    kitchen = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            from backend.utils.auth import decode_access_token
            from backend.core.database import db_get_kitchen
            from backend.utils.permissions import has_permission
            payload = decode_access_token(token)
            kid = payload.get("active_kitchen_id")
            uid = payload.get("id")
            if kid:
                k = db_get_kitchen(int(kid))
                if k:
                    # Permission gate for tablet-driven Processing.
                    if body.step == "Processing":
                        user_dict = {"id": int(uid) if uid else 0, "role": payload.get("role"), "org_id": payload.get("org_id")}
                        if not has_permission(user_dict, "production.processing_scan", kitchen_id=k["id"]):
                            raise HTTPException(status_code=403, detail="Missing permission: production.processing_scan")
                    kitchen = k
        except HTTPException:
            raise
        except Exception:
            kitchen = None

    if kitchen is None:
        kitchen = _resolve_scanner_kitchen(x_scanner_key)
    kitchen_id = kitchen["id"]

    if body.step not in VALIDATORS:
        raise HTTPException(400, f"Invalid step: {body.step}. Must be Processing, Packing, or Delivery.")

    code = extract_code(body.code)
    ok, reason = VALIDATORS[body.step](code, kitchen_id)

    if not ok:
        log_scan_error(code or body.code, body.step, reason, kitchen_id)
        await broadcast("scan_error", {"code": code, "step": body.step, "reason": reason, "kitchen_id": kitchen_id})
        return {"ok": False, "code": code, "step": body.step, "reason": reason, "data": None, "kitchen_id": kitchen_id}

    APPLIERS[body.step](code, kitchen_id)

    data = None
    if body.step == "Delivery":
        data = await process_delivery_allocation(code, kitchen)

    await broadcast("scan_ok", {"code": code, "step": body.step, "kitchen_id": kitchen_id})
    return {"ok": True, "code": code, "step": body.step, "reason": "", "data": data, "kitchen_id": kitchen_id}
