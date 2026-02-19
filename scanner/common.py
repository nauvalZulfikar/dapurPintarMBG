#!/usr/bin/env python3
"""
common.py

Scanner business logic for Processing, Packing, Delivery.

Flow:
  1. Scan barcode
  2. Validate against Supabase directly (simple label check)
  3. Write result to local SQLite queue immediately
  4. Background thread (syncer.py) pushes local → Supabase every 60s, then deletes synced rows
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from backend.core.database import (
    local_engine,
    remote_engine,
    remote_items,
    remote_trays,
    remote_tray_items,
    local_enqueue_scan,
    local_enqueue_error,
    init_db,
)
from backend.core.syncer import start_sync_thread

load_dotenv()
_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, '..', '.env'))


# ─────────────────────────── CONFIG ──────────────────────────────────────────

SUCCESS_SOUND    = "scanner/SUCCESS.mp3"
FAILED_SOUND     = "scanner/FAILED.mp3"
DEBOUNCE_SECONDS = 0.7
DB_LOCK_RETRIES  = 6
DB_LOCK_SLEEP    = 0.15
BHN_PREFIX       = "BHN-"
TRAY_PREFIX      = "TRY-"
TRAY_LEN         = 12
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
    try:
        subprocess.run(["pkill", "-f", "termux-media-player"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    try:
        subprocess.run(["termux-media-player", "play", path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def warn(msg: str):
    sys.stdout.write(f"[WARN] {msg}\n")
    sys.stdout.flush()

# ─────────────────────────── PARSING ─────────────────────────────────────────

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

# ─────────────────────────── RETRY ───────────────────────────────────────────

def _exec_retry(fn):
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

# ─────────────────────────── VALIDATORS ──────────────────────────────────────
# Validators query Supabase directly — just a quick label check.
# If Supabase is unreachable, validation fails with a clear error.

def _get_remote_item_label(code: str) -> Optional[str]:
    if not remote_engine:
        return None
    with remote_engine.connect() as c:
        row = c.execute(
            select(remote_items.c.label).where(remote_items.c.id == code)
        ).first()
        return row[0] if row else None

def _get_remote_tray_label(tray_id: str) -> Optional[str]:
    if not remote_engine:
        return None
    with remote_engine.connect() as c:
        row = c.execute(
            select(remote_trays.c.label).where(remote_trays.c.tray_id == tray_id)
        ).first()
        return row[0] if row else None

def _is_remote_tray_registered(tray_id: str) -> bool:
    if not remote_engine:
        return False
    with remote_engine.connect() as c:
        return c.execute(
            select(remote_tray_items.c.tray_id).where(remote_tray_items.c.tray_id == tray_id)
        ).first() is not None

def validate_processing(code: str) -> tuple[bool, str]:
    if not code:
        return False, "EMPTY_SCAN"
    if not code.startswith(BHN_PREFIX):
        return False, f"NOT_AN_INGREDIENT_CODE (expected BHN-, got: {code[:8]})"
    try:
        label = _get_remote_item_label(code)
    except Exception as e:
        return False, f"SUPABASE_UNREACHABLE: {e}"
    if label is None:
        return False, "INGREDIENT_NOT_FOUND"
    if label != "received":
        return False, f"NOT_RECEIVED (current label={label})"
    return True, ""


def validate_packing(code: str) -> tuple[bool, str]:
    if not code:
        return False, "EMPTY_SCAN"
    if not code.startswith(TRAY_PREFIX):
        return False, f"NOT_A_TRAY_CODE (expected TRY-, got: {code[:8]})"
    if len(code) != TRAY_LEN:
        return False, f"INVALID_TRAY_ID_LENGTH (expected {TRAY_LEN}, got {len(code)})"
    try:
        registered = _is_remote_tray_registered(code)
        label = _get_remote_tray_label(code)
    except Exception as e:
        return False, f"SUPABASE_UNREACHABLE: {e}"
    if not registered:
        return False, "TRAY_NOT_REGISTERED"
    if label in ("packed", "delivered"):
        return False, f"ALREADY_{label.upper()}"
    return True, ""


def validate_delivery(code: str) -> tuple[bool, str]:
    if not code:
        return False, "EMPTY_SCAN"
    if not code.startswith(TRAY_PREFIX):
        return False, f"NOT_A_TRAY_CODE (expected TRY-, got: {code[:8]})"
    if len(code) != TRAY_LEN:
        return False, f"INVALID_TRAY_ID_LENGTH (expected {TRAY_LEN}, got {len(code)})"
    try:
        registered = _is_remote_tray_registered(code)
        label = _get_remote_tray_label(code)
    except Exception as e:
        return False, f"SUPABASE_UNREACHABLE: {e}"
    if not registered:
        return False, "TRAY_NOT_REGISTERED"
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
      "Processing" → validates BHN in Supabase → stores locally → syncer updates Supabase label
      "Packing"    → validates TRY in Supabase  → stores locally → syncer updates Supabase label
      "Delivery"   → validates TRY in Supabase  → stores locally → syncer updates Supabase label
    """
    if mode not in ALLOWED_STEPS:
        raise ValueError(f"Invalid mode: {mode!r}. Must be one of: {sorted(ALLOWED_STEPS)}")

    write_label = {"Processing": "processed", "Packing": "packed", "Delivery": "delivered"}[mode]

    sys.stdout.write(f"=== SCANNER MODE: {mode.upper()} (writes label='{write_label}') ===\n")
    sys.stdout.write("Scan now...\n\n")
    sys.stdout.flush()

    # Init local SQLite tables
    init_db()

    # Start background sync thread
    start_sync_thread()

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

        # debounce
        t = time.time()
        if code and code == last_code and (t - last_time) < DEBOUNCE_SECONDS:
            continue
        last_code, last_time = code, t

        try:
            ok, reason = validators[mode](code)

            if not ok:
                _exec_retry(lambda: local_enqueue_error(code or raw, mode, reason))
                play_sound(failed_sound)
                print_status(False, when, reason)
                continue

            # Write to local SQLite immediately
            _exec_retry(lambda: local_enqueue_scan(code, mode, write_label))

            play_sound(success_sound)
            print_status(True, when)

        except Exception as e:
            err = f"EXCEPTION: {type(e).__name__}: {e}"
            try:
                local_enqueue_error(code or raw, mode, err)
            except Exception:
                pass
            play_sound(failed_sound)
            print_status(False, when, err)