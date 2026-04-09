import os
import json
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, text

from backend.core.database import (
    engine,
    remote_items,
    remote_trays,
    remote_tray_items,
    remote_scan_errors,
)
from backend.services.printing import create_and_push_job
from backend.utils.datetime_helpers import now_local_iso
from backend.api.sse import broadcast

router = APIRouter()

SCANNER_KEY = os.getenv("SCANNER_KEY", "")
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


class ScanRequest(BaseModel):
    code: str
    step: str  # "Processing" | "Packing" | "Delivery"


def _check_scanner_key(key: Optional[str]):
    if SCANNER_KEY and key != SCANNER_KEY:
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


# ── Validators ───────────────────────────────────────────────────────────────

def validate_processing(code: str) -> tuple[bool, str]:
    if not code:
        return False, "EMPTY_SCAN"
    if not code.upper().startswith(BHN_PREFIX):
        return False, f"NOT_AN_INGREDIENT_CODE (expected BHN-, got: {code[:8]})"
    with engine.connect() as c:
        row = c.execute(
            select(remote_items.c.receiving, remote_items.c.processing)
            .where(remote_items.c.id == code)
        ).first()
    if row is None:
        return False, "INGREDIENT_NOT_FOUND"
    if not row.receiving:
        return False, "NOT_RECEIVED"
    if row.processing:
        return False, "ALREADY_PROCESSED"
    return True, ""


def validate_packing(code: str) -> tuple[bool, str]:
    if not code:
        return False, "EMPTY_SCAN"
    if not code.upper().startswith(TRAY_PREFIX):
        return False, f"NOT_A_TRAY_CODE (expected TRY-, got: {code[:8]})"
    if len(code) != TRAY_LEN:
        return False, f"INVALID_TRAY_ID_LENGTH (expected {TRAY_LEN}, got {len(code)})"
    with engine.connect() as c:
        registered = c.execute(
            select(remote_tray_items.c.tray_id)
            .where(remote_tray_items.c.tray_id == code)
        ).first() is not None
        row = c.execute(
            select(remote_trays.c.packing, remote_trays.c.created_date_packing)
            .where(remote_trays.c.tray_id == code)
        ).first()
    if not registered:
        return False, "TRAY_NOT_REGISTERED"
    if row and row.packing and row.created_date_packing == date.today():
        return False, "ALREADY_PACKED_TODAY"
    return True, ""


def validate_delivery(code: str) -> tuple[bool, str]:
    if not code:
        return False, "EMPTY_SCAN"
    if not code.upper().startswith(TRAY_PREFIX):
        return False, f"NOT_A_TRAY_CODE (expected TRY-, got: {code[:8]})"
    if len(code) != TRAY_LEN:
        return False, f"INVALID_TRAY_ID_LENGTH (expected {TRAY_LEN}, got {len(code)})"
    with engine.connect() as c:
        registered = c.execute(
            select(remote_tray_items.c.tray_id)
            .where(remote_tray_items.c.tray_id == code)
        ).first() is not None
        row = c.execute(
            select(
                remote_trays.c.packing,
                remote_trays.c.delivery,
                remote_trays.c.created_date_delivery,
            ).where(remote_trays.c.tray_id == code)
        ).first()
    if not registered:
        return False, "TRAY_NOT_REGISTERED"
    if not row or not row.packing:
        return False, "NOT_PACKED"
    if row.delivery and row.created_date_delivery == date.today():
        return False, "ALREADY_DELIVERED_TODAY"
    return True, ""


# ── Apply scan to DB ────────────────────────────────────────────────────────

def apply_processing(code: str):
    with engine.begin() as c:
        c.execute(
            remote_items.update()
            .where(remote_items.c.id == code)
            .values(
                processing=True,
                created_at_processing=datetime.now(),
                created_date_processing=date.today(),
            )
        )


def apply_packing(code: str):
    with engine.begin() as c:
        existing = c.execute(
            select(remote_trays.c.tray_id).where(remote_trays.c.tray_id == code)
        ).first()
        if existing:
            c.execute(
                remote_trays.update()
                .where(remote_trays.c.tray_id == code)
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
                    packing=True,
                    created_at_packing=datetime.now(),
                    created_date_packing=date.today(),
                )
            )


def apply_delivery(code: str):
    from backend.core.config import TZ_REGION
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(tz=ZoneInfo(TZ_REGION))
    except Exception:
        now = datetime.now()
    with engine.begin() as c:
        c.execute(
            remote_trays.update()
            .where(remote_trays.c.tray_id == code)
            .values(
                delivery=True,
                created_at_delivery=now,
                created_date_delivery=now.date(),
            )
        )


def log_scan_error(code: str, step: str, reason: str):
    with engine.begin() as c:
        c.execute(
            remote_scan_errors.insert().values(
                code=code,
                step=step,
                created_at=now_local_iso(),
                reason=reason,
            )
        )


# ── Delivery allocation ─────────────────────────────────────────────────────

MEALS_PER_SCAN = 10


def _scan_allocations(n: int, schools_sorted: list) -> list:
    """
    Return [{school, n_trays}] for the n-th delivery scan (1-based).

    Phase 1 — full batches: each school's floor(students/10) scans go out
    sequentially by distance. Each scan delivers exactly 10 meals to one school.

    Phase 2 — remainder pool: once all full batches are done, the remainders
    (students % 10) from every school are pooled in distance order and filled
    scan-by-scan. One remainder scan can cover multiple schools.
    """
    # Phase 1: full-batch scans (one school per scan, exactly MEALS_PER_SCAN meals)
    full_offset = 0
    for school in schools_sorted:
        n_full = int(school["student_count"]) // MEALS_PER_SCAN
        if n <= full_offset + n_full:
            return [{"school": school["name"], "n_trays": MEALS_PER_SCAN}]
        full_offset += n_full

    # Phase 2: combined remainder scans
    rem_scan_n = n - full_offset          # 1-based position within remainder scans
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


async def process_delivery_allocation(tray_id: str) -> dict:
    with open(SCHOOLS_FILE, "r", encoding="utf-8") as f:
        schools = json.load(f)
    schools_sorted = sorted(schools, key=lambda s: s["distance"])

    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT tray_id FROM trays
            WHERE created_date_delivery = :today AND delivery = true
            ORDER BY created_at_delivery ASC
        """), {"today": str(date.today())}).fetchall()

    scan_order = [r[0] for r in rows]
    try:
        n = scan_order.index(tray_id) + 1
    except ValueError:
        n = len(scan_order)

    allocations = _scan_allocations(n, schools_sorted)

    # Generate delivery label
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
    await create_and_push_job(tspl)
    return {"tray_id": tray_id, "allocations": allocations}


# ── Main endpoint ────────────────────────────────────────────────────────────

VALIDATORS = {
    "Processing": validate_processing,
    "Packing": validate_packing,
    "Delivery": validate_delivery,
}

APPLIERS = {
    "Processing": apply_processing,
    "Packing": apply_packing,
    "Delivery": apply_delivery,
}


@router.post("/scans")
async def post_scan(
    body: ScanRequest,
    x_scanner_key: Optional[str] = Header(None, alias="X-Scanner-Key"),
):
    _check_scanner_key(x_scanner_key)

    if body.step not in VALIDATORS:
        raise HTTPException(400, f"Invalid step: {body.step}. Must be Processing, Packing, or Delivery.")

    code = extract_code(body.code)
    ok, reason = VALIDATORS[body.step](code)

    if not ok:
        log_scan_error(code or body.code, body.step, reason)
        await broadcast("scan_error", {"code": code, "step": body.step, "reason": reason})
        return {"ok": False, "code": code, "step": body.step, "reason": reason, "data": None}

    # Apply the scan to the database
    APPLIERS[body.step](code)

    data = None
    if body.step == "Delivery":
        data = await process_delivery_allocation(code)

    await broadcast("scan_ok", {"code": code, "step": body.step})
    return {"ok": True, "code": code, "step": body.step, "reason": "", "data": data}
