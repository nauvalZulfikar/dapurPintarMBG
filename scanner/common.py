#!/usr/bin/env python3
"""
common.py

Scanner business logic for the 3 barcode-scanning steps:
  - Processing  (scans BHN-xxxxx, updates items table)
  - Packing     (scans TRY-xxxxx, updates trays table)
  - Delivery    (scans TRY-xxxxx, updates trays table)

Table ownership:
  items → BHN-xxxxx ingredients   label: "received" → "processed"
  trays → TRY-xxxxx physical trays label: "packed"  → "delivered"

Receiving is handled by receiving.py (Streamlit form),
which inserts into items with label="received".
"""

import os
import sys
import subprocess
import time
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy.exc import OperationalError

from backend.core.database import (
    engine,
    items,
    trays,
    scan_errors,
    metadata,
    db_get_item_label,
    db_update_item_label,
    db_is_tray_registered,
    db_get_tray_label,
    db_update_tray_label,
    db_log_scan_error,
)

load_dotenv()
_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, '..', '.env'))

def create_tables():
    """Create all tables (safe to call repeatedly). Schema lives in database.py."""
    metadata.create_all(engine)


# ─────────────────────────── DEFAULT CONFIG ──────────────────────────────────

SUCCESS_SOUND    = "scanner/SUCCESS.mp3"
FAILED_SOUND     = "scanner/FAILED.mp3"
DEBOUNCE_SECONDS = 0.7
DB_LOCK_RETRIES  = 6
DB_LOCK_SLEEP    = 0.15
BHN_PREFIX       = "BHN-"
TRAY_PREFIX      = "TRY-"
TRAY_LEN         = 12          # "TRY-" (4) + 8 chars = 12 total
ALLOWED_STEPS    = {"Processing", "Packing", "Delivery"}

# ─────────────────────────── OUTPUT HELPERS ──────────────────────────────────

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def print_status(ok: bool, when: str, reason: str = ""):
    if ok:
        sys.stdout.write(f"SUKSES\n{when}\n\n\n")
    else:
        sys.stdout.write(f"GAGAL\n{when}\n{reason}\n\n\n")
    sys.stdout.flush()


def play_sound(path: str):
    """Play audio via termux-media-player; silently skipped if unavailable."""
    try:
        subprocess.run(
            ["pkill", "-f", "termux-media-player"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["termux-media-player", "play", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def warn(msg: str):
    sys.stdout.write(f"[WARN] {msg}\n")
    sys.stdout.flush()


# ─────────────────────────── PARSING ─────────────────────────────────────────

def extract_code(raw: str) -> str:
    """
    Normalises a raw scan string into a clean BHN- or TRY- code.

    Handles plain codes, URLs with query params, and embedded codes inside
    longer strings.
    """
    s = (raw or "").strip()
    if not s:
        return ""

    lower = s.lower()

    # Handle URL-encoded params
    if any(k in lower for k in ("tray_id=", "ingredient_id=", "id=", "barcode=")):
        for part in s.replace("?", "&").split("&"):
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k.strip().lower() in {"tray_id", "ingredient_id", "id", "barcode"} and v.strip():
                return v.strip()

    # Handle embedded TRY- or BHN- inside a longer string
    for prefix in (TRAY_PREFIX, BHN_PREFIX):
        idx = s.find(prefix)
        if idx != -1:
            chunk = s[idx:idx + 64].split()[0]
            for delim in ["&", "?", "#", "/", "\\", '"', "'", ",", ";", ")", "(", "]", "[", "}", "{"]:
                chunk = chunk.split(delim)[0]
            return chunk

    return s


# ─────────────────────────── RETRY ───────────────────────────────────────────

def _exec_retry(fn):
    """Retry fn() on transient DB lock/busy errors (SQLite WAL contention)."""
    last_err = None
    for _ in range(DB_LOCK_RETRIES):
        try:
            return fn()
        except OperationalError as e:
            last_err = e
            if any(kw in str(e).lower() for kw in ("locked", "busy")):
                time.sleep(DB_LOCK_SLEEP)
                continue
            raise
    raise last_err


# ─────────────────────────── STEP VALIDATORS ─────────────────────────────────

def validate_processing(code: str) -> tuple[bool, str]:
    """
    Processing validator — operates on items table.
    - Code must be BHN- prefix.
    - Item must exist with label == "received".
    """
    if not code:
        return False, "EMPTY_SCAN"
    if not code.startswith(BHN_PREFIX):
        return False, f"NOT_AN_INGREDIENT_CODE (expected BHN-, got: {code[:8]})"
    label = _exec_retry(lambda: db_get_item_label(code))
    if label is None:
        return False, "INGREDIENT_NOT_FOUND"
    if label != "received":
        return False, f"NOT_RECEIVED (current label={label})"
    return True, ""


def validate_packing(code: str) -> tuple[bool, str]:
    """
    Packing validator — operates on trays table.
    - Code must be TRY- prefix with correct length.
    - Tray must be registered (exists in trays table).
    - Tray must not already be packed or delivered.
    """
    if not code:
        return False, "EMPTY_SCAN"
    if not code.startswith(TRAY_PREFIX):
        return False, f"NOT_A_TRAY_CODE (expected TRY-, got: {code[:8]})"
    if len(code) != TRAY_LEN:
        return False, f"INVALID_TRAY_ID_LENGTH (expected {TRAY_LEN}, got {len(code)})"
    if not _exec_retry(lambda: db_is_tray_registered(code)):
        return False, "TRAY_NOT_REGISTERED"
    label = _exec_retry(lambda: db_get_tray_label(code))
    if label in ("packed", "delivered"):
        return False, f"ALREADY_{label.upper()}"
    return True, ""


def validate_delivery(code: str) -> tuple[bool, str]:
    """
    Delivery validator — operates on trays table.
    - Code must pass basic tray format/registration check.
    - Tray must have label == "packed".
    """
    if not code:
        return False, "EMPTY_SCAN"
    if not code.startswith(TRAY_PREFIX):
        return False, f"NOT_A_TRAY_CODE (expected TRY-, got: {code[:8]})"
    if len(code) != TRAY_LEN:
        return False, f"INVALID_TRAY_ID_LENGTH (expected {TRAY_LEN}, got {len(code)})"
    if not _exec_retry(lambda: db_is_tray_registered(code)):
        return False, "TRAY_NOT_REGISTERED"
    label = _exec_retry(lambda: db_get_tray_label(code))
    if label != "packed":
        return False, f"NOT_PACKED (current label={label})"
    return True, ""


# ─────────────────────────── MAIN RUNNER ─────────────────────────────────────

def run_scanner(
    mode: str,
    success_sound: str = SUCCESS_SOUND,
    failed_sound:  str = FAILED_SOUND,
):
    """
    Main blocking scanner loop. Reads barcodes from stdin, one per line.

    mode:
      "Processing" → scans BHN-xxxxx; validates label=="received";  updates items label→"processed"
      "Packing"    → scans TRY-xxxxx; validates tray registered;    updates trays label→"packed"
      "Delivery"   → scans TRY-xxxxx; validates label=="packed";    updates trays label→"delivered"
    """
    if mode not in ALLOWED_STEPS:
        raise ValueError(f"Invalid mode: {mode!r}. Must be one of: {sorted(ALLOWED_STEPS)}")

    write_label = {"Processing": "processed", "Packing": "packed", "Delivery": "delivered"}[mode]

    sys.stdout.write(f"=== SCANNER MODE: {mode.upper()} (writes label='{write_label}') ===\n")
    sys.stdout.write("Scan now...\n\n")
    sys.stdout.flush()

    create_tables()

    validators = {
        "Processing": validate_processing,
        "Packing":    validate_packing,
        "Delivery":   validate_delivery,
    }

    last_code = None
    last_time = 0.0

    for line in sys.stdin:
        raw  = line.strip()
        when = now_str()
        code = extract_code(raw)

        # ── debounce ──────────────────────────────────────────────────────────
        t = time.time()
        if code and code == last_code and (t - last_time) < DEBOUNCE_SECONDS:
            continue
        last_code, last_time = code, t

        try:
            ok, reason = validators[mode](code)

            if not ok:
                db_log_scan_error(code or raw, mode, reason)
                play_sound(failed_sound)
                print_status(False, when, reason)
                continue

            # Write the new label to the correct table
            if mode == "Processing":
                _exec_retry(lambda: db_update_item_label(code, "processed"))
            elif mode == "Packing":
                _exec_retry(lambda: db_update_tray_label(code, "packed"))
            elif mode == "Delivery":
                _exec_retry(lambda: db_update_tray_label(code, "delivered"))

            play_sound(success_sound)
            print_status(True, when)

        except Exception as e:
            err = f"EXCEPTION: {type(e).__name__}: {e}"
            try:
                db_log_scan_error(code or raw, mode, err)
            except Exception:
                pass
            play_sound(failed_sound)
            print_status(False, when, err)