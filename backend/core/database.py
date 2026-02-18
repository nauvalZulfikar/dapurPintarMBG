# DPMBG_Project/backend/core/database.py
import os
import json
from datetime import date
from typing import Optional, Tuple

from backend.utils.datetime_helpers import now_local_iso

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Text, DateTime,
    Index, select, func, UniqueConstraint, insert
)

# ============================================================
# DB (SQLAlchemy)
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(BASE_DIR, 'scans.db')}"
)

engine_kwargs = {"future": True, "pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite:///"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
metadata = MetaData()

# ============================================================
# TABLES
# ============================================================

# --- Master entities (ingredients/items)
# Pure registry: only stores what the ingredient IS, not where it is in the pipeline.
# Pipeline state (received/processed/packed/delivered) is tracked in the trays table.
items = Table(
    "items", metadata,
    Column("id", String, primary_key=True),   # BHN-xxxxx
    Column("name", String),
    Column("weight_grams", Integer),
    Column("unit", String),
    Column("created_at", DateTime, server_default=func.now()),
)

# --- Tray registry (allowed trays for Packing step)
tray_items = Table(
    "tray_items", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tray_id", String, nullable=False, unique=True),  # TRY-xxxxx
)
Index("ix_tray_items_tray", tray_items.c.tray_id)

# --- Scan event log (single source of truth for pipeline state)
#
# STEP        | tray_id value | label written
# ------------|---------------|---------------
# Receiving   | BHN-xxxxx     | "received"
# Processing  | BHN-xxxxx     | "processed"
# Packing     | TRY-xxxxx     | "packed"
# Delivery    | TRY-xxxxx     | "delivered"
#
# Validation rules (enforced in common.py / receiving.py):
#   Processing  → requires latest label for BHN code == "received"
#   Packing     → requires tray_id registered in tray_items
#   Delivery    → requires latest label for TRY code == "packed"
trays = Table(
    "trays", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tray_id", Text, nullable=False),         # scanned code (BHN-... or TRY-...)
    Column("status", Text, nullable=False),          # "SUKSES" / "GAGAL"
    Column("label", Text, nullable=False),           # "received" / "processed" / "packed" / "delivered"
    Column("created_at", Text, nullable=False),      # ISO string
    Column("created_date", Text, nullable=False),    # YYYY-MM-DD string
    Column("reason", Text, nullable=True),           # optional message / QC payload
    UniqueConstraint("tray_id", "label", "created_date", name="uq_scans_code_label_day"),
)
Index("ix_trays_code", trays.c.tray_id)
Index("ix_trays_label_date", trays.c.label, trays.c.created_date)

# --- Print jobs (queue for mini PC polling)
print_jobs = Table(
    "print_jobs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tspl", Text, nullable=False),
    Column("created_at", DateTime, server_default=func.now()),
    Column("printed", Integer, server_default=func.cast(0, Integer)),
    Column("printed_at", DateTime, nullable=True),
)

# Create tables
metadata.create_all(engine)

# ============================================================
# HELPERS
# ============================================================

def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")

def _iso_now() -> str:
    return now_local_iso()

# ---------- Items ----------
def db_insert_item(item_id: str, name: str, weight_g: int, unit: str = "g"):
    """Insert ingredient into items registry. Does NOT log the scan event — call db_log_scan separately."""
    with engine.begin() as c:
        if not c.execute(select(items.c.id).where(items.c.id == item_id)).first():
            c.execute(items.insert().values(id=item_id, name=name, weight_grams=weight_g, unit=unit))

def db_item_exists(item_id: str) -> bool:
    """Return True if item_id exists in the items registry."""
    with engine.connect() as c:
        return c.execute(select(items.c.id).where(items.c.id == item_id)).first() is not None

# ---------- Tray registry ----------
def db_register_tray(tray_id: str):
    """Add tray_id into tray_items registry if not exists."""
    with engine.begin() as c:
        if not c.execute(select(tray_items.c.tray_id).where(tray_items.c.tray_id == tray_id)).first():
            c.execute(tray_items.insert().values(tray_id=tray_id))

def db_is_tray_registered(tray_id: str) -> bool:
    """Return True if tray_id exists in tray_items registry."""
    with engine.connect() as c:
        return c.execute(select(tray_items.c.tray_id).where(tray_items.c.tray_id == tray_id)).first() is not None

# ---------- Scan event log ----------
def db_log_scan(code: str, label: str, status: str = "SUKSES", reason: Optional[str] = None,
                created_at_iso: Optional[str] = None, created_date: Optional[str] = None) -> int:
    """
    Insert one scan event row into trays table.

    - code:   BHN-xxxxx (for receiving/processing) or TRY-xxxxx (for packing/delivery)
    - label:  "received" / "processed" / "packed" / "delivered"
    - status: "SUKSES" / "GAGAL"
    - reason: optional QC payload or error reason
    """
    created_at_iso = created_at_iso or _iso_now()
    created_date = created_date or _today_str()

    with engine.begin() as c:
        res = c.execute(
            insert(trays).values(
                tray_id=code,
                status=status,
                label=label,
                created_at=created_at_iso,
                created_date=created_date,
                reason=reason
            )
        )
        pk = res.inserted_primary_key
        return int(pk[0]) if pk and pk[0] is not None else -1

def db_get_latest_label(code: str) -> Optional[str]:
    """Return the latest pipeline label for a given code (BHN or TRY)."""
    with engine.connect() as c:
        row = c.execute(
            select(trays.c.label)
            .where(trays.c.tray_id == code)
            .order_by(trays.c.id.desc())
            .limit(1)
        ).first()
        return row[0] if row else None

# ---------- Print jobs ----------
def db_enqueue_print(tspl: str) -> int:
    """Insert print job, return job id."""
    with engine.begin() as c:
        res = c.execute(print_jobs.insert().values(tspl=tspl))
        pk = res.inserted_primary_key
        return int(pk[0]) if pk and pk[0] is not None else -1

def db_fetch_next_print_job() -> Optional[dict]:
    """Fetch one pending job (printed=0)."""
    with engine.connect() as c:
        row = c.execute(
            select(print_jobs)
            .where(print_jobs.c.printed == 0)
            .order_by(print_jobs.c.id.asc())
            .limit(1)
        ).first()
        return dict(row._mapping) if row else None

def db_mark_printed(job_id: int):
    with engine.begin() as c:
        c.execute(
            print_jobs.update()
            .where(print_jobs.c.id == job_id)
            .values(printed=1, printed_at=func.now())
        )