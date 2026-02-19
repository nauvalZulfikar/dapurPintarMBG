# DPMBG_Project/backend/core/database.py
import os
from datetime import date
from typing import Optional

from backend.utils.datetime_helpers import now_local_iso

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Text, DateTime,
    Index, select, func, UniqueConstraint, insert, update
)

# ============================================================
# ENGINE
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

# --- Ingredient table (BHN-xxxxx)
# Stores what the ingredient IS and where it is in the ingredient pipeline.
#
# label progression: "received" → "processed"
# status: "SUKSES" / "GAGAL"
items = Table(
    "items", metadata,
    Column("id", String, primary_key=True),              # BHN-xxxxx
    Column("name", String, nullable=False),
    Column("weight_grams", Integer, nullable=False),
    Column("unit", String, nullable=False),
    Column("label", String, nullable=False, server_default="received"),   # "received" / "processed"
    Column("status", String, nullable=False, server_default="SUKSES"),    # "SUKSES" / "GAGAL"
    Column("reason", Text, nullable=True),                                # QC payload or error
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
)

# --- Tray registry + pipeline table (TRY-xxxxx)
# Stores which trays exist and where they are in the tray pipeline.
#
# label progression: "packed" → "delivered"
# status: "SUKSES" / "GAGAL"
trays = Table(
    "trays", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tray_id", String, nullable=False, unique=True),              # TRY-xxxxx
    Column("label", String, nullable=True),                              # "packed" / "delivered" / None if not yet packed
    Column("status", String, nullable=True),                             # "SUKSES" / "GAGAL"
    Column("reason", Text, nullable=True),
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
)
Index("ix_trays_tray_id", trays.c.tray_id)

# --- Scan error log (failed scans from all steps)
scan_errors = Table(
    "scan_errors", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", Text),                    # BHN-xxxxx or TRY-xxxxx
    Column("step", Text, nullable=False),    # "Processing" / "Packing" / "Delivery"
    Column("created_at", Text, nullable=False),
    Column("reason", Text, nullable=False),
)
Index("ix_scan_errors_code", scan_errors.c.code)

# --- Print jobs (queue for mini PC polling)
print_jobs = Table(
    "print_jobs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tspl", Text, nullable=False),
    Column("created_at", DateTime, server_default=func.now()),
    Column("printed", Integer, server_default=func.cast(0, Integer)),
    Column("printed_at", DateTime, nullable=True),
)

# Create all tables
metadata.create_all(engine)

# ============================================================
# HELPERS
# ============================================================

def _iso_now() -> str:
    return now_local_iso()

def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")

# ---------- Items (BHN) ----------

def db_insert_item(item_id: str, name: str, weight_g: int, unit: str = "g", reason: Optional[str] = None) -> None:
    """Insert a new ingredient into items with label='received'."""
    with engine.begin() as c:
        c.execute(items.insert().values(
            id=item_id,
            name=name,
            weight_grams=weight_g,
            unit=unit,
            label="received",
            status="SUKSES",
            reason=reason,
        ))

def db_item_exists(item_id: str) -> bool:
    with engine.connect() as c:
        return c.execute(select(items.c.id).where(items.c.id == item_id)).first() is not None

def db_get_item_label(item_id: str) -> Optional[str]:
    """Return current label for a BHN ingredient."""
    with engine.connect() as c:
        row = c.execute(select(items.c.label).where(items.c.id == item_id)).first()
        return row[0] if row else None

def db_update_item_label(item_id: str, label: str, status: str = "SUKSES", reason: Optional[str] = None) -> None:
    """Update the pipeline label of an ingredient."""
    with engine.begin() as c:
        c.execute(
            items.update()
            .where(items.c.id == item_id)
            .values(label=label, status=status, reason=reason)
        )

# ---------- Trays (TRY) ----------

def db_register_tray(tray_id: str) -> None:
    """Register a new tray (no label yet — not yet packed)."""
    with engine.begin() as c:
        if not c.execute(select(trays.c.tray_id).where(trays.c.tray_id == tray_id)).first():
            c.execute(trays.insert().values(tray_id=tray_id))

def db_is_tray_registered(tray_id: str) -> bool:
    with engine.connect() as c:
        return c.execute(select(trays.c.tray_id).where(trays.c.tray_id == tray_id)).first() is not None

def db_get_tray_label(tray_id: str) -> Optional[str]:
    """Return current label for a TRY tray."""
    with engine.connect() as c:
        row = c.execute(select(trays.c.label).where(trays.c.tray_id == tray_id)).first()
        return row[0] if row else None

def db_update_tray_label(tray_id: str, label: str, status: str = "SUKSES", reason: Optional[str] = None) -> None:
    """Update the pipeline label of a tray."""
    with engine.begin() as c:
        c.execute(
            trays.update()
            .where(trays.c.tray_id == tray_id)
            .values(label=label, status=status, reason=reason)
        )

# ---------- Scan errors ----------

def db_log_scan_error(code: str, step: str, reason: str) -> None:
    """Log a failed scan attempt."""
    with engine.begin() as c:
        c.execute(scan_errors.insert().values(
            code=code,
            step=step,
            created_at=_iso_now(),
            reason=reason,
        ))

# ---------- Print jobs ----------

def db_enqueue_print(tspl: str) -> int:
    with engine.begin() as c:
        res = c.execute(print_jobs.insert().values(tspl=tspl))
        pk = res.inserted_primary_key
        return int(pk[0]) if pk and pk[0] is not None else -1

def db_fetch_next_print_job() -> Optional[dict]:
    with engine.connect() as c:
        row = c.execute(
            select(print_jobs)
            .where(print_jobs.c.printed == 0)
            .order_by(print_jobs.c.id.asc())
            .limit(1)
        ).first()
        return dict(row._mapping) if row else None

def db_mark_printed(job_id: int) -> None:
    with engine.begin() as c:
        c.execute(
            print_jobs.update()
            .where(print_jobs.c.id == job_id)
            .values(printed=1, printed_at=func.now())
        )