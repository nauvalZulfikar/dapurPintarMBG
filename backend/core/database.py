# DPMBG_Project/backend/core/database.py
import os
from datetime import date, datetime
from typing import Optional

from backend.utils.datetime_helpers import now_local_iso

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Text,
    DateTime, Date, Boolean, Index, select, func, insert, update
)

# ============================================================
# STREAMLIT SECRETS BRIDGE
# ============================================================
try:
    import streamlit as st
    _db_url = st.secrets.get("DATABASE_URL")
    if _db_url:
        os.environ["DATABASE_URL"] = _db_url
except Exception:
    pass

# ============================================================
# ENGINES
# ============================================================
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DB_URL  = f"sqlite:///{os.path.join(BASE_DIR, 'local_scans.db')}"
REMOTE_DB_URL = os.getenv("DATABASE_URL")

local_engine = create_engine(
    LOCAL_DB_URL,
    future=True,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False},
)

remote_engine = None
if REMOTE_DB_URL:
    remote_engine = create_engine(REMOTE_DB_URL, future=True, pool_pre_ping=True)

# engine = remote for Streamlit/receiving, local for scanner
engine = remote_engine if remote_engine else local_engine

# ============================================================
# LOCAL TABLES (SQLite on Android/Windows scanner)
# ============================================================
local_metadata = MetaData()

local_scan_queue = Table(
    "local_scan_queue", local_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("code",       Text, nullable=False),
    Column("step",       Text, nullable=False),    # "Processing" / "Packing" / "Delivery"
    Column("label",      Text, nullable=False),    # "processed" / "packed" / "delivered"
    Column("created_at", Text, nullable=False),
    Column("synced",     Integer, default=0),
)

local_scan_errors = Table(
    "local_scan_errors", local_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("code",       Text),
    Column("step",       Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("reason",     Text, nullable=False),
    Column("synced",     Integer, default=0),
)

# ============================================================
# REMOTE TABLE REFERENCES (Supabase)
# ============================================================
remote_metadata = MetaData()

# --- Ingredients (BHN-xxxxx)
# One row per ingredient. Boolean columns track pipeline progress.
# Timestamps record when each step happened.
remote_items = Table(
    "items", remote_metadata,
    Column("id",                      String, primary_key=True),
    Column("name",                    String),
    Column("weight_grams",            Integer),
    Column("unit",                    String),
    Column("reason",                  Text),
    Column("receiving",               Boolean, default=False),
    Column("created_at_receiving",    DateTime),
    Column("created_date_receiving",  Date),
    Column("processing",              Boolean, default=False),
    Column("created_at_processing",   DateTime),
    Column("created_date_processing", Date),
)

# --- Trays (TRY-xxxxx)
# One row per tray. Boolean columns track pipeline progress.
# Timestamps record when each step happened.
remote_trays = Table(
    "trays", remote_metadata,
    Column("id",                    Integer, primary_key=True, autoincrement=True),
    Column("tray_id",               String, nullable=False, unique=True),
    Column("reason",                Text),
    Column("packing",               Boolean, default=False),
    Column("created_at_packing",    DateTime),
    Column("created_date_packing",  Date),
    Column("delivery",              Boolean, default=False),
    Column("created_at_delivery",   DateTime),
    Column("created_date_delivery", Date),
)

# --- Tray registry (used for Packing validation)
remote_tray_items = Table(
    "tray_items", remote_metadata,
    Column("id",      Integer, primary_key=True, autoincrement=True),
    Column("tray_id", String, nullable=False, unique=True),
)

# --- Scan errors
remote_scan_errors = Table(
    "scan_errors", remote_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("code",       Text),
    Column("step",       Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("reason",     Text, nullable=False),
)

# --- Print jobs
remote_print_jobs = Table(
    "print_jobs", remote_metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("tspl",       Text, nullable=False),
    Column("created_at", DateTime, server_default=func.now()),
    Column("printed",    Integer, server_default=func.cast(0, Integer)),
    Column("printed_at", DateTime, nullable=True),
)

# ============================================================
# INIT
# ============================================================

def init_db():
    """Create local SQLite tables. Call once on scanner startup."""
    local_metadata.create_all(local_engine)

# ============================================================
# HELPERS
# ============================================================

def _iso_now() -> str:
    return now_local_iso()

# ---------- Local scan queue ----------

def local_enqueue_scan(code: str, step: str, label: str) -> None:
    with local_engine.begin() as c:
        c.execute(local_scan_queue.insert().values(
            code=code,
            step=step,
            label=label,
            created_at=_iso_now(),
            synced=0,
        ))

def local_enqueue_error(code: str, step: str, reason: str) -> None:
    with local_engine.begin() as c:
        c.execute(local_scan_errors.insert().values(
            code=code,
            step=step,
            created_at=_iso_now(),
            reason=reason,
            synced=0,
        ))

# ---------- Remote helpers (receiving.py / Streamlit) ----------

def db_insert_item(item_id: str, name: str, weight_g: int, unit: str = "g",
                   reason: Optional[str] = None) -> None:
    """Insert a new ingredient into Supabase with receiving=True."""
    with engine.begin() as c:
        c.execute(remote_items.insert().values(
            id=item_id,
            name=name,
            weight_grams=weight_g,
            unit=unit,
            reason=reason,
            receiving=True,
            created_at_receiving=datetime.now(),
            created_date_receiving=date.today(),
        ))

def db_register_tray(tray_id: str) -> None:
    """Register a new tray in Supabase."""
    with engine.begin() as c:
        if not c.execute(
            select(remote_trays.c.tray_id).where(remote_trays.c.tray_id == tray_id)
        ).first():
            c.execute(remote_trays.insert().values(tray_id=tray_id))

def db_enqueue_print(tspl: str) -> int:
    with engine.begin() as c:
        res = c.execute(remote_print_jobs.insert().values(tspl=tspl))
        pk = res.inserted_primary_key
        return int(pk[0]) if pk and pk[0] is not None else -1

def db_fetch_next_print_job() -> Optional[dict]:
    with engine.connect() as c:
        row = c.execute(
            select(remote_print_jobs)
            .where(remote_print_jobs.c.printed == 0)
            .order_by(remote_print_jobs.c.id.asc())
            .limit(1)
        ).first()
        return dict(row._mapping) if row else None

def db_mark_printed(job_id: int) -> None:
    with engine.begin() as c:
        c.execute(
            remote_print_jobs.update()
            .where(remote_print_jobs.c.id == job_id)
            .values(printed=1, printed_at=func.now())
        )