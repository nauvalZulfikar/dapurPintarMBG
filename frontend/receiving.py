# frontend/receiving.py

import os
import sys
import json
import string
import secrets
from datetime import datetime

import streamlit as st
from sqlalchemy import text

# Ensure project root is importable (so "backend" can be found)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.core.database import engine

# ============================================================
# SETTINGS
# ============================================================

CHECKLIST_ITEMS = [
    "Packaging OK",
    "Expiry OK",
    "Temperature OK",
    "Cleanliness OK",
]

# ============================================================
# HELPERS
# ============================================================

def to_grams(value: float, unit: str) -> int:
    """Normalize weight to grams (int)."""
    if unit == "kg":
        return int(round(value * 1000))
    return int(round(value))

def generate_random_bhn_id(conn, length=6):
    alphabet = string.ascii_uppercase + string.digits

    while True:
        random_part = ''.join(secrets.choice(alphabet) for _ in range(length))
        new_id = f"BHN-{random_part}"

        exists = conn.execute(
            text("SELECT 1 FROM items WHERE id = :id"),
            {"id": new_id}
        ).fetchone()

        if not exists:
            return new_id

# ============================================================
# UI
# ============================================================

st.set_page_config(page_title="Receiving", layout="centered")
st.title("Receiving – New Container")

if "name" not in st.session_state:
    st.session_state.name = ""
if "weight_value" not in st.session_state:
    st.session_state.weight_value = 0.0
if "weight_unit" not in st.session_state:
    st.session_state.weight_unit = "g"
if "notes" not in st.session_state:
    st.session_state.notes = ""

with st.form("receiving_form"):
    st.subheader("Bahan")

    name = st.text_input("Nama Bahan (e.g. Ayam, Jeruk)", key='nama')
    weight_value = st.number_input("Berat", min_value=0.0, step=0.1, key='berat')
    weight_unit = st.selectbox("Unit", ["g", "kg"], key='satuan')

    st.subheader("QC Checklist")
    checklist = {item: st.checkbox(item, value=False) for item in CHECKLIST_ITEMS}

    notes = st.text_area("Catatan (optional)", key='catatan')
    submitted = st.form_submit_button("Submit & Print Sticker")

# ============================================================
# SAVE
# ============================================================

if submitted:
    if not name.strip():
        st.error("Ingredient name is required.")
        st.stop()

    if weight_value <= 0:
        st.error("Weight must be > 0.")
        st.stop()

    weight_g = to_grams(weight_value, weight_unit)

    qc_payload = {
        "checklist": checklist,
        "notes": notes.strip() or None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    now_iso = datetime.now().isoformat(timespec="seconds")
    today_str = datetime.now().strftime("%Y-%m-%d")

    try:
        with engine.begin() as conn:
            # 1. Generate unique BHN ID
            bhn_id = generate_random_bhn_id(conn)

            # 2. Insert into items table (pure ingredient registry — no label/status here)
            conn.execute(
                text("""
                    INSERT INTO items (id, name, weight_grams, unit)
                    VALUES (:id, :name, :wg, :unit)
                """),
                {
                    "id": bhn_id,
                    "name": name.strip(),
                    "wg": weight_g,
                    "unit": "g",
                }
            )

            # 3. Log the receiving scan event into trays table (pipeline state tracker)
            #    This is what Processing step will validate against (latest label == "received").
            conn.execute(
                text("""
                    INSERT INTO trays (tray_id, status, label, created_at, created_date, reason)
                    VALUES (:tray_id, :status, :label, :created_at, :created_date, :reason)
                """),
                {
                    "tray_id": bhn_id,
                    "status": "SUKSES",
                    "label": "received",
                    "created_at": now_iso,
                    "created_date": today_str,
                    "reason": json.dumps(qc_payload, ensure_ascii=False),
                }
            )

        st.success(f"✅ Saved: **{bhn_id}** — {name.strip()} ({weight_g}g)")
        st.info("Print sticker with this ID and attach to the container.")

        # TODO: enqueue print job here via db_enqueue_print() if needed

    except Exception as e:
        st.error(f"Error saving data: {e}")