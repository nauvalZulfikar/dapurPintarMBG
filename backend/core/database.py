import os
import json
from datetime import datetime
from typing import Optional, Tuple
from backend.utils.datetime_helpers import now_local_iso
from sqlalchemy.ext.declarative import declarative_base

# ---------- DB (SQLAlchemy) ----------
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Text, DateTime,
    Index, select, func, ForeignKey
)
from sqlalchemy.exc import IntegrityError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'scans.db')}")
engine_kwargs = {"future": True, "pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite:///"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
metadata = MetaData()


# --- Master entities
items = Table(
    "items", metadata,
    Column("id", String, primary_key=True),   # BHN-xxxxx
    Column("name", String),
    Column("weight_grams", Integer),
    Column("unit", String),
    Column("created_at", DateTime, server_default=func.now()),
)
trays = Table(
    "trays", metadata,
    Column("id", String, ForeignKey("tray_items.id"), primary_key=True),   # TRY-xxxxx
    Column("created_at", DateTime, server_default=func.now()),
)
tray_items = Table(
    "tray_items", metadata,
    Column("id", Integer, primary_key=True),
    Column("tray_id", String),#, ForeignKey("trays.id")),
    # Column("item_id", String),#, ForeignKey("items.id")),
    # Column("bound_by_number", String),
    # Column("bound_at", DateTime, server_default=func.now()),
)
Index("ix_tray_items_tray", tray_items.c.tray_id)

# --- Event log
events = Table(
    "events", metadata,
    Column("id", Integer, primary_key=True),
    Column("ts_local", String, nullable=False),
    Column("from_number", String),
    Column("division", String),      # receiving/processing/packing/delivery/school_receipt
    Column("subject_type", String),  # item | tray
    Column("subject_id", String),    # BHN-xxxxx | TRY-xxxxx
    Column("message_text", Text),
    Column("duration_hms", String),  # HH:MM:SS
    Column("duration_seconds", Integer),
    Column("extra", Text),
    Column("created_at", DateTime, server_default=func.now()),
)
Index("ix_events_subject", events.c.subject_type, events.c.subject_id)

# --- Staff & onboarding
staffs = Table(
    "staffs", metadata,
    Column("phone", String, primary_key=True),  # E.164 without '+'
    Column("name", String, nullable=False),
    Column("division", String, nullable=False), # receiving/processing/packing/delivery/school_receipt
    Column("created_at", DateTime, server_default=func.now()),
)
registrations = Table(
    "registrations", metadata,
    Column("phone", String, primary_key=True),
    Column("state", String),       # ask_name | ask_division
    Column("temp_name", String),
    Column("created_at", DateTime, server_default=func.now()),
)

# --- Inbound idempotency (kill WA duplicate deliveries)
inbound_seen = Table(
    "inbound_seen", metadata,
    Column("id", String, primary_key=True),   # WhatsApp message.id
    Column("created_at", DateTime, server_default=func.now()),
)

# --- Print jobs (queue for mini PC polling) ---
print_jobs = Table(
    "print_jobs", metadata,
    Column("id", Integer, primary_key=True),
    Column("tspl", Text, nullable=False),
    Column("created_at", DateTime, server_default=func.now()),
    Column("printed", Integer, server_default="0"),  # 0 = pending, 1 = printed
    Column("printed_at", DateTime, nullable=True),
)

metadata.create_all(engine)


# ---------- DB helpers ----------
def db_get_staff(phone: str) -> Optional[dict]:
    with engine.connect() as c:
        row = c.execute(select(staffs).where(staffs.c.phone == phone).limit(1)).first()
        return dict(row._mapping) if row else None

def db_set_staff(phone: str, name: str, division: str):
    with engine.begin() as c:
        if c.execute(select(staffs.c.phone).where(staffs.c.phone == phone)).first():
            c.execute(staffs.update().where(staffs.c.phone == phone).values(name=name, division=division))
        else:
            c.execute(staffs.insert().values(phone=phone, name=name, division=division))

def db_get_reg(phone: str) -> Optional[dict]:
    with engine.connect() as c:
        row = c.execute(select(registrations).where(registrations.c.phone == phone)).first()
        return dict(row._mapping) if row else None

def db_set_reg(phone: str, state: str, temp_name: Optional[str] = None):
    with engine.begin() as c:
        if c.execute(select(registrations.c.phone).where(registrations.c.phone == phone)).first():
            c.execute(
                registrations.update()
                .where(registrations.c.phone == phone)
                .values(state=state, temp_name=temp_name)
            )
        else:
            c.execute(
                registrations.insert().values(phone=phone, state=state, temp_name=temp_name)
            )

def db_clear_reg(phone: str):
    with engine.begin() as c:
        c.execute(registrations.delete().where(registrations.c.phone == phone))

def db_insert_item(item_id: str, name: str, weight_g: int, unit: str = "g"):
    with engine.begin() as c:
        if not c.execute(select(items.c.id).where(items.c.id == item_id)).first():
            c.execute(
                items.insert().values(id=item_id, name=name, weight_grams=weight_g, unit=unit)
            )

def db_insert_tray_if_needed(tray_id: str):
    with engine.begin() as c:
        if not c.execute(select(trays.c.id).where(trays.c.id == tray_id)).first():
            c.execute(trays.insert().values(id=tray_id))

def db_last_event(subject_type: str, subject_id: str, division: Optional[str] = None):
    with engine.connect() as c:
        stmt = select(events).where(
            events.c.subject_type == subject_type,
            events.c.subject_id == subject_id,
        )
        if division:
            stmt = stmt.where(events.c.division == division)
        stmt = stmt.order_by(events.c.id.desc()).limit(1)
        row = c.execute(stmt).first()
        return dict(row._mapping) if row else None

def db_insert_event(
    ts_local: str,
    phone: str,
    division: str,
    subject_type: str,
    subject_id: str,
    message_text: str,
    duration_hms: str,
    duration_sec: int,
    extra: dict,
):
    with engine.begin() as c:
        c.execute(
            events.insert().values(
                ts_local=ts_local,
                from_number=phone,
                division=division,
                subject_type=subject_type,
                subject_id=subject_id,
                message_text=message_text,
                duration_hms=duration_hms,
                duration_seconds=duration_sec,
                extra=json.dumps(extra or {}),
            )
        )

def db_recent_processed_item(phone: str, window_min: int = 10) -> Optional[Tuple[str, str]]:
    now_iso = now_local_iso()
    with engine.connect() as c:
        ev = (
            c.execute(
                select(events.c.subject_id, events.c.ts_local)
                .where(
                    events.c.division == "processing",
                    events.c.from_number == phone,
                    events.c.subject_type == "item",
                )
                .order_by(events.c.id.desc())
                .limit(1)
            )
            .first()
        )
    if not ev:
        return None
    item_id, ts = ev
    try:
        d = datetime.fromisoformat(now_iso) - datetime.fromisoformat(ts)
        if d.total_seconds() > window_min * 60:
            return None
    except Exception:
        pass
    return (item_id, ts)

def mark_inbound_seen(mid: Optional[str]) -> bool:
    """Return True if this message-id was seen before (so caller should skip)."""
    if not mid:
        return False
    with engine.begin() as c:
        if c.execute(select(inbound_seen.c.id).where(inbound_seen.c.id == mid)).first():
            return True
        c.execute(inbound_seen.insert().values(id=mid))
        return False

Base = declarative_base()

# --- NEW: model the events table (this is where packing scans are logged) ---
class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    ts_local = Column(String)          # stored as ISO string in your app
    division = Column(String)
    subject_type = Column(String)
    subject_id = Column(String)
