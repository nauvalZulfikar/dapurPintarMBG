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
    Call this function when a tray barcode is scanned.
    """

    with engine.begin() as conn:

        # 1️⃣ Determine school (closest first with remaining quota)
        school_name = find_target_school(conn)

        if not school_name:
            raise Exception("All schools have fulfilled their tray quota.")

        # 2️⃣ Count how many trays already assigned to this school
        tray_count = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM deliveries
                WHERE school_name = :school_name
            """),
            {"school_name": school_name}
        ).scalar()

        tray_count = (tray_count or 0) + 1

        # 3️⃣ Insert delivery record
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

    # 4️⃣ Generate TSPL sticker
    tspl = generate_delivery_tspl(tray_id, school_name, tray_count)

    # 5️⃣ Enqueue print job
    db_create_print_job(tspl)

    return {
        "tray_id": tray_id,
        "school": school_name,
        "tray_number_for_school": tray_count
    }