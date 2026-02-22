# scanner/delivery.py

import os
import json
from datetime import datetime
from sqlalchemy import text

from backend.core.database import engine
from backend.services.printing import db_create_print_job


# ============================================================
# CONFIG
# ============================================================

SCHOOLS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "schools.json"
)

COUNTDOWN_BASE_URL = "https://dapurpintarmbg-countdown.streamlit.app"


# ============================================================
# LOAD & SORT SCHOOLS (closest first)
# ============================================================

def load_schools():
    with open(SCHOOLS_FILE, "r", encoding="utf-8") as f:
        schools = json.load(f)

    # sort from closest to furthest
    schools_sorted = sorted(schools, key=lambda s: s["distance_km"])
    return schools_sorted


# ============================================================
# FIND NEXT SCHOOL THAT STILL NEEDS TRAYS
# ============================================================

def find_target_school(conn):
    schools = load_schools()

    for school in schools:
        school_name = school["name"]
        quota = school["tray_quota"]

        # count already assigned trays
        result = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM deliveries
                WHERE school_name = :school_name
            """),
            {"school_name": school_name}
        ).scalar()

        assigned = result or 0

        if assigned < quota:
            return school_name

    return None


# ============================================================
# GENERATE TSPL STICKER
# ============================================================

def generate_delivery_tspl(tray_id, school_name, tray_count):
    qr_link = f"{COUNTDOWN_BASE_URL}/?tray_id={tray_id}"

    return f"""
SIZE 50 mm, 30 mm
GAP 1 mm, 0 mm
SPEED 4
DENSITY 15
DIRECTION 1
CLS

QRCODE 40,40,L,5,A,0,"{qr_link}"

TEXT 40,200,"0",0,8,8,"{school_name}"
TEXT 40,230,"0",0,8,8,"Tray: {tray_count}"

PRINT 1,1
"""


# ============================================================
# MAIN DELIVERY SCAN FUNCTION
# ============================================================

def process_delivery_scan(tray_id: str):
    """
    1 scan = 10 trays.
    Distribute trays from closest school first.
    If remaining quota < 10, spill over to next closest school.
    Print ONE sticker summarizing allocations.
    """

    TOTAL_TRAYS = 10

    with engine.begin() as conn:

        schools = load_schools()
        allocations = []
        remaining = TOTAL_TRAYS

        # Allocate trays from closest to furthest
        for school in schools:
            school_name = school["name"]
            quota = school["tray_quota"]

            assigned = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM deliveries
                    WHERE school_name = :school_name
                """),
                {"school_name": school_name}
            ).scalar() or 0

            available = quota - assigned

            if available <= 0:
                continue

            take = min(available, remaining)

            allocations.append({
                "school": school_name,
                "n_trays": take
            })

            # Insert rows into deliveries table
            for _ in range(take):
                conn.execute(
                    text("""
                        INSERT INTO deliveries (tray_id, school_name, created_at)
                        VALUES (:tray_id, :school_name, :created_at)
                    """),
                    {
                        "tray_id": tray_id,
                        "school_name": school_name,
                        "created_at": datetime.utcnow()
                    }
                )

            remaining -= take

            if remaining == 0:
                break

        if remaining > 0:
            raise Exception("Not enough remaining tray quota across schools.")

        # ---------- Generate TSPL Sticker (50x21mm) ----------

    qr_link = f"https://dapurpintarmbg-countdown.streamlit.app/?tray_id={tray_id}"

    y_position = 20
    text_lines = ""

    for alloc in allocations:
        text_lines += (
            f'TEXT 10,{y_position},"0",0,6,6,'
            f'"{alloc["school"]} {alloc["n_trays"]}"\n'
        )
        y_position += 20

    tspl = f"""
SIZE 50 mm, 21 mm
GAP 1 mm, 0 mm
SPEED 4
DENSITY 15
DIRECTION 1
CLS

{text_lines}

QRCODE 300,10,L,3,A,0,"{qr_link}"

PRINT 1,1
"""

    # Enqueue print job
    db_create_print_job(tspl)

    return {
        "tray_id": tray_id,
        "allocations": allocations
    }
