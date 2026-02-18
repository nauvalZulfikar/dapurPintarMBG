# frontend/utils/data_loader.py
import os
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from pathlib import Path

# Import from backend (delivery optimizer logic)
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
from backend.services.delivery_optimizer import (
    load_schools_from_json, 
    fetch_trays_packed_times, 
    assign_trays_to_schools
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, '../../scans.db')}")

# Get project root (2 levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHOOLS_JSON_PATH = os.getenv(
    "SCHOOLS_JSON_PATH", 
    str(PROJECT_ROOT / "data" / "schools.json")
)

# Create engine
engine_kwargs = {"future": True, "pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite:///"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)

def load_table(table_name: str) -> pd.DataFrame:
    """Load table from database without caching to ensure fresh data"""
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", engine)
    return df

def prepare_data():
    """Load and prepare all data for the dashboard
    
    Returns:
        tuple: (items, events, staffs, trays, tray_items) DataFrames
    """
    items = load_table("items")
    events = load_table("events")
    staffs = load_table("staffs")
    trays = load_table("trays")
    tray_items = load_table("tray_items")

    # Parse datetimes
    for df, col in [(items, "created_at"),
                    (events, "created_at"),
                    (staffs, "created_at"),
                    (trays, "created_at"),
                    (tray_items, "bound_at")]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "ts_local" in events.columns:
        events["ts_local_dt"] = pd.to_datetime(events["ts_local"], errors="coerce")
    else:
        events["ts_local_dt"] = events["created_at"]

    # Rename to avoid collision
    if "division" in events.columns:
        events = events.rename(columns={"division": "event_division"})
    if "division" in staffs.columns:
        staffs = staffs.rename(columns={"division": "staff_division"})

    # Merge staff info into events (left join on phone)
    events = events.merge(
        staffs[["phone", "name", "staff_division"]],
        how="left",
        left_on="from_number",
        right_on="phone",
    )

    # Convenience cols
    events["event_date"] = events["ts_local_dt"].dt.date

    return items, events, staffs, trays, tray_items

def optimize_delivery():
    """Run delivery optimization algorithm
    
    Returns:
        dict: School assignments
    """
    schools = load_schools_from_json(SCHOOLS_JSON_PATH)
    with Session(bind=engine) as db:
        trays = fetch_trays_packed_times(db)
        assignments = assign_trays_to_schools(trays, schools, db)
    return assignments
