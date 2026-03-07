#!/usr/bin/env python3
"""
common.py

Scanner business logic for Processing, Packing, Delivery.

Flow:
  1. Scan barcode from stdin (HID device)
  2. POST to FastAPI /api/scans for validation + DB write
  3. On network failure: queue locally in SQLite, retry via background thread every 30s
"""

import os
import sys
import json
import sqlite3
import subprocess
import threading
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()
_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, '..', '.env'))

# ============================================================
# CONFIG
# ============================================================

API_BASE_URL     = os.getenv("API_BASE_URL", "http://localhost:8000")
SCANNER_KEY      = os.getenv("SCANNER_KEY", "")
SUCCESS_SOUND    = os.path.join(_here, "SUCCESS.mp3")
FAILED_SOUND     = os.path.join(_here, "FAILED.mp3")
DEBOUNCE_SECONDS = 0.7
ALLOWED_STEPS    = {"Processing", "Packing", "Delivery"}
HTTP_TIMEOUT     = 5
RETRY_INTERVAL   = 30

# Local SQLite for offline queue
LOCAL_DB_PATH = os.path.join(_here, "local_queue.db")
BHN_PREFIX    = "BHN-"
TRAY_PREFIX   = "TRY-"

# ============================================================
# LOCAL SQLITE QUEUE (offline resilience)
# ============================================================

def _get_local_db():
    conn = sqlite3.connect(LOCAL_DB_PATH, timeout=5)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            step TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def local_enqueue(code: str, step: str):
    conn = _get_local_db()
    conn.execute(
        "INSERT INTO pending_scans (code, step, created_at) VALUES (?, ?, ?)",
        (code, step, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def _retry_pending():
    """Background thread: retry pending scans every RETRY_INTERVAL seconds."""
    while True:
        time.sleep(RETRY_INTERVAL)
        try:
            conn = _get_local_db()
            rows = conn.execute("SELECT id, code, step FROM pending_scans ORDER BY id").fetchall()
            if not rows:
                conn.close()
                continue

            for row_id, code, step in rows:
                try:
                    resp = requests.post(
                        f"{API_BASE_URL}/api/scans",
                        json={"code": code, "step": step},
                        headers={"X-Scanner-Key": SCANNER_KEY},
                        timeout=HTTP_TIMEOUT,
                    )
                    if resp.status_code == 200:
                        conn.execute("DELETE FROM pending_scans WHERE id = ?", (row_id,))
                        conn.commit()
                        sys.stdout.write(f"[SYNC] Retried {code} ({step}) -> OK\n")
                        sys.stdout.flush()
                except requests.RequestException:
                    break  # Network still down, stop retrying this cycle

            conn.close()
        except Exception as e:
            sys.stdout.write(f"[SYNC] Error: {e}\n")
            sys.stdout.flush()


def start_retry_thread():
    t = threading.Thread(target=_retry_pending, daemon=True)
    t.start()


# ============================================================
# API CALL
# ============================================================

def post_scan(code: str, step: str) -> tuple[bool, str, dict]:
    """
    POST to /api/scans. Returns (ok, reason, data).
    On network failure returns (False, "NETWORK_ERROR: ...", {}).
    """
    try:
        resp = requests.post(
            f"{API_BASE_URL}/api/scans",
            json={"code": code, "step": step},
            headers={"X-Scanner-Key": SCANNER_KEY},
            timeout=HTTP_TIMEOUT,
        )
        body = resp.json()
        if resp.status_code == 403:
            return False, "AUTH_FAILED: Invalid scanner key", {}
        if resp.status_code == 400:
            return False, body.get("detail", "BAD_REQUEST"), {}
        return body.get("ok", False), body.get("reason", ""), body.get("data") or {}
    except requests.RequestException as e:
        return False, f"NETWORK_ERROR: {e}", {}


# ============================================================
# OUTPUT HELPERS
# ============================================================

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


# ============================================================
# PARSING
# ============================================================

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


# ============================================================
# MAIN RUNNER
# ============================================================

def run_scanner(
    mode: str,
    success_sound: str = "",
    failed_sound: str = "",
):
    if mode not in ALLOWED_STEPS:
        raise ValueError(f"Invalid mode: {mode!r}. Must be one of: {sorted(ALLOWED_STEPS)}")

    if not success_sound:
        success_sound = SUCCESS_SOUND
    if not failed_sound:
        failed_sound = FAILED_SOUND

    sys.stdout.write(f"=== SCANNER MODE: {mode.upper()} ===\n")
    sys.stdout.write(f"API: {API_BASE_URL}\n")
    sys.stdout.write("Scan now...\n\n")
    sys.stdout.flush()

    # Start background retry thread for offline queue
    start_retry_thread()

    last_code = None
    last_time = 0.0

    for line in sys.stdin:
        raw = line.strip()
        when = now_str()
        code = extract_code(raw)

        # Debounce duplicate scans
        t = time.time()
        if code and code == last_code and (t - last_time) < DEBOUNCE_SECONDS:
            continue
        last_code, last_time = code, t

        if not code:
            play_sound(failed_sound)
            print_status(False, when, "EMPTY_SCAN")
            continue

        try:
            ok, reason, data = post_scan(code, mode)

            if reason.startswith("NETWORK_ERROR"):
                # Save to local queue for retry
                local_enqueue(code, mode)
                play_sound(failed_sound)
                sys.stdout.write(f"OFFLINE QUEUED\n{when}\n{code} -> will retry\n\n\n")
                sys.stdout.flush()
                continue

            if not ok:
                play_sound(failed_sound)
                print_status(False, when, reason)
                continue

            play_sound(success_sound)
            print_status(True, when)

            # Show delivery allocations if present
            if data and "allocations" in data:
                for alloc in data["allocations"]:
                    sys.stdout.write(f"  {alloc['school']}: {alloc['n_trays']} trays\n")
                sys.stdout.flush()

        except Exception as e:
            err = f"EXCEPTION: {type(e).__name__}: {e}"
            play_sound(failed_sound)
            print_status(False, when, err)
