#!/usr/bin/env python3
"""
common.py

Merges:
  - SQLAlchemy engine/session setup from common.py (PostgreSQL-ready, scalable)
  - All scanner business logic from common_old.py (validation, debounce, sound, runner)

Usage:
  Set DATABASE_URL in .env (defaults to local SQLite scans.db if not set).
  Import run_scanner and call it with a mode string.
"""

import os
import sys
import subprocess
import time
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, MetaData, Table, Column,
    Integer, Text, UniqueConstraint,
    select, insert,
)
from sqlalchemy.exc import IntegrityError, OperationalError

# ─────────────────────────── ENV / ENGINE SETUP ──────────────────────────────

load_dotenv()

_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, '..', '.env'))

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("[WARN] DATABASE_URL not set — falling back to local SQLite. Data will NOT go to Supabase.", flush=True)
    DATABASE_URL = f"sqlite:///{os.path.join(_here, 'scans.db')}"

_engine_kwargs: dict = {"future": True, "pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
metadata = MetaData()

# ───────────────────────────── TABLE DEFINITIONS ─────────────────────────────

tray_items = Table(
    "tray_items", metadata,
    Column("tray_id", Text, primary_key=True),
)

scans = Table(
    "trays", metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("barcode",    Text,    nullable=False),
    Column("status",     Text,    nullable=False),
    Column("label",      Text,    nullable=False),
    Column("created_at", Text,    nullable=False),
    Column("created_date",  Text,    nullable=False),
    Column("reason",     Text),
    UniqueConstraint("barcode", "label", "created_date", name="uq_scans_barcode_label_day"),
)

scan_errors = Table(
    "scan_errors", metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("barcode",    Text),
    Column("label",      Text,    nullable=False),
    Column("created_at", Text,    nullable=False),
    Column("reason",     Text,    nullable=False),
)


def create_tables():
    """Create all tables (safe to call repeatedly; uses CREATE IF NOT EXISTS)."""
    metadata.create_all(engine)


# ─────────────────────────── DEFAULT CONFIG ──────────────────────────────────

SUCCESS_SOUND    = "./SUCCESS.mp3"
FAILED_SOUND     = "./FAILED.mp3"
DEBOUNCE_SECONDS = 0.7
DB_LOCK_RETRIES  = 6
DB_LOCK_SLEEP    = 0.15
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
    Normalises a raw scan string into a clean barcode/tray ID.

    Handles:
      - Plain TRY-XXXX strings
      - URLs containing tray_id=, ingredient_id=, id=, or barcode= params
      - Anything containing TRY- somewhere (strips surrounding delimiters)
    Falls back to the stripped raw value for non-tray codes (e.g. ingredient IDs).
    """
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

    idx = s.find(TRAY_PREFIX)
    if idx != -1:
        chunk = s[idx:idx + 64].split()[0]
        for delim in ["&", "?", "#", "/", "\\", '"', "'", ",", ";", ")", "(", "]", "[", "}", "{"]:
            chunk = chunk.split(delim)[0]
        return chunk

    return s


# ─────────────────────────── DB HELPERS ──────────────────────────────────────

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


def _log_error(conn, barcode: str, label: str, reason: str):
    when = now_str()
    _exec_retry(lambda: conn.execute(
        insert(scan_errors).values(barcode=barcode, label=label, created_at=when, reason=reason)
    ))


def _log_success(conn, barcode: str, label: str, reason: str = None):
    when      = now_str()
    scan_date = datetime.now().strftime("%Y-%m-%d")
    _exec_retry(lambda: conn.execute(
        insert(scans).values(
            barcode=barcode, status="SUKSES", label=label,
            created_at=when, created_date=scan_date, reason=reason,
        )
    ))


def _tray_is_registered(conn, tray_id: str) -> bool:
    row = _exec_retry(lambda: conn.execute(
        select(tray_items.c.tray_id).where(tray_items.c.tray_id == tray_id).limit(1)
    ).fetchone())
    return row is not None


def _latest_label(conn, barcode: str) -> str | None:
    row = _exec_retry(lambda: conn.execute(
        select(scans.c.label)
        .where(scans.c.barcode == barcode)
        .order_by(scans.c.created_at.desc(), scans.c.id.desc())
        .limit(1)
    ).fetchone())
    return row[0] if row else None


# ─────────────────────────── STEP VALIDATORS ─────────────────────────────────

def validate_processing(conn, code: str) -> tuple[bool, str]:
    """Ingredient must have been previously received (latest label == 'received')."""
    if not code:
        return False, "EMPTY_SCAN"
    last = _latest_label(conn, code)
    if last != "received":
        return False, f"NOT_RECEIVED (latest={last})"
    return True, ""


def validate_packing(conn, code: str) -> tuple[bool, str]:
    """Tray must match TRY- format, correct length, and be registered."""
    if not code:
        return False, "EMPTY_SCAN"
    if not code.startswith(TRAY_PREFIX) or len(code) != TRAY_LEN:
        return False, "INVALID_TRAY_ID_FORMAT"
    if not _tray_is_registered(conn, code):
        return False, "TRAY_ID_NOT_REGISTERED"
    return True, ""


def validate_delivery(conn, code: str) -> tuple[bool, str]:
    """Tray must pass packing validation AND have latest label == 'packed'."""
    ok, reason = validate_packing(conn, code)
    if not ok:
        return ok, reason
    last = _latest_label(conn, code)
    if last != "packed":
        return False, f"NOT_PACKED (latest={last})"
    return True, ""


# ─────────────────────────── MAIN RUNNER ─────────────────────────────────────

def run_scanner(
    mode: str,
    success_sound: str = SUCCESS_SOUND,
    failed_sound:  str = FAILED_SOUND,
):
    """
    Main blocking scanner loop.  Reads barcodes from stdin, one per line.

    mode:
      - "Processing"  → validates ingredient received; logs label 'processed'
      - "Packing"     → validates tray registered;     logs label 'packed'
      - "Delivery"    → validates tray packed;          logs label 'delivered'

    The db_path argument from common_old.py is removed; connection comes from
    the SQLAlchemy engine configured via DATABASE_URL in .env.
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

    with engine.connect() as conn:
        # Use a single open transaction per scan to keep things atomic.
        for line in sys.stdin:
            raw  = line.strip()
            when = now_str()
            code = extract_code(raw)

            # ── debounce ──────────────────────────────────────────────────────
            t = time.time()
            if code and code == last_code and (t - last_time) < DEBOUNCE_SECONDS:
                continue
            last_code, last_time = code, t

            try:
                with conn.begin():
                    ok, reason = validators[mode](conn, code)

                    if not ok:
                        _log_error(conn, code or raw, write_label, reason)
                        play_sound(failed_sound)
                        print_status(False, when, reason)
                        continue

                    try:
                        _log_success(conn, code, write_label)
                    except IntegrityError:
                        dup = "DUPLICATE_SAME_LABEL_SAME_DAY"
                        _log_error(conn, code, write_label, dup)
                        play_sound(failed_sound)
                        print_status(False, when, dup)
                        continue

                    play_sound(success_sound)
                    print_status(True, when)

            except Exception as e:
                err = f"EXCEPTION: {type(e).__name__}: {e}"
                try:
                    with conn.begin():
                        _log_error(conn, code or raw, write_label, err)
                except Exception:
                    pass
                play_sound(failed_sound)
                print_status(False, when, err)
