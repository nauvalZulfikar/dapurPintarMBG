# DPMBG_Project/backend/core/database.py
import os
from datetime import date, datetime
from typing import Optional

from backend.utils.datetime_helpers import now_local_iso

from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Text,
    DateTime, Date, Boolean, Index, select, func, insert, update, NullPool
)
from dotenv import load_dotenv
load_dotenv()

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
    remote_engine = create_engine(
        REMOTE_DB_URL, 
        future=True, 
        pool_pre_ping=True,
        pool_recycle=180,
        poolclass=NullPool
        )

# engine = remote if available, else local
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
# REMOTE TABLE REFERENCES (PostgreSQL)
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
    Column("kitchen_id",              String, nullable=True),   # multi-dapur support
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
    Column("kitchen_id",            String, nullable=True),   # multi-dapur support
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

# --- Users (JWT auth)
remote_users = Table(
    "users", remote_metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("username",      String(50), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("role",          String(20), server_default="admin"),
    Column("created_at",    DateTime, server_default=func.now()),
)

# --- Food prices (scraped market prices per ingredient code)
remote_food_prices = Table(
    "food_prices", remote_metadata,
    Column("id",             Integer, primary_key=True, autoincrement=True),
    Column("food_code",      String(20), nullable=False, unique=True),  # TKPI KODE
    Column("food_name",      String(255), nullable=False),
    Column("price_per_100g", Integer, nullable=False, server_default="0"),  # IDR per 100g
    Column("source",         String(50), nullable=True),   # e.g. "sayurbox"
    Column("scraped_at",     DateTime, nullable=True),
    Column("updated_at",     DateTime, server_default=func.now()),
)

# ============================================================
# INIT
# ============================================================

def init_db():
    """Create local SQLite tables. Call once on scanner startup."""
    local_metadata.create_all(local_engine)


def init_remote_db():
    """Create remote PostgreSQL tables (food_prices etc). Safe to call on startup."""
    if remote_engine:
        remote_metadata.create_all(remote_engine)

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

# ---------- Remote helpers ----------

def db_insert_item(item_id: str, name: str, weight_g: int, unit: str = "g",
                   reason: Optional[str] = None) -> None:
    """Insert a new ingredient with receiving=True."""
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
    """Register a new tray if not exists."""
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

# ---------- Food prices ----------

def db_upsert_food_price(food_code: str, food_name: str, price_per_100g: int, source: str = "sayurbox") -> None:
    """Insert or update a food price by TKPI code."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    with engine.begin() as c:
        stmt = pg_insert(remote_food_prices).values(
            food_code=food_code,
            food_name=food_name,
            price_per_100g=price_per_100g,
            source=source,
            scraped_at=datetime.now(),
            updated_at=datetime.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["food_code"],
            set_={
                "food_name": stmt.excluded.food_name,
                "price_per_100g": stmt.excluded.price_per_100g,
                "source": stmt.excluded.source,
                "scraped_at": stmt.excluded.scraped_at,
                "updated_at": stmt.excluded.updated_at,
            }
        )
        c.execute(stmt)


def db_get_food_prices() -> dict[str, int]:
    """Return all food prices as {food_code: price_per_100g}."""
    with engine.connect() as c:
        rows = c.execute(select(remote_food_prices.c.food_code, remote_food_prices.c.price_per_100g)).all()
        return {r.food_code: r.price_per_100g for r in rows}


def db_get_price_scrape_status() -> list[dict]:
    """Return all food_prices rows for status display."""
    with engine.connect() as c:
        rows = c.execute(
            select(remote_food_prices)
            .order_by(remote_food_prices.c.scraped_at.desc())
        ).all()
        return [dict(r._mapping) for r in rows]