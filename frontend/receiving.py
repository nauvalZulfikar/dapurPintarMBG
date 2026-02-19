# frontend/receiving.py

import os
import sys
import json
import string
import secrets
from datetime import datetime

import streamlit as st
from sqlalchemy import text
import backend.core.database as _db
import inspect
st.write("PATH:", _db.__file__)
st.write("SIGNATURE:", str(inspect.signature(_db.db_insert_item)))

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.core.database import engine, db_insert_item

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
    if unit == "kg":
        return int(round(value * 1000))
    return int(round(value))

def generate_random_bhn_id(conn, length=6):
    alphabet = string.ascii_uppercase + string.digits
    while True:
        rand = ''.join(secrets.choice(alphabet) for _ in range(length))
        new_id = f"BHN-{rand}"
        exists = conn.execute(
            text("SELECT 1 FROM items WHERE id = :id"), {"id": new_id}
        ).fetchone()
        if not exists:
            return new_id

# ============================================================
# UI
# ============================================================

st.set_page_config(page_title="Receiving", layout="centered")
st.title("Receiving – New Container")

with st.form("receiving_form"):
    st.subheader("Bahan")
    name         = st.text_input("Nama Bahan (e.g. Ayam, Jeruk)")
    weight_value = st.number_input("Berat", min_value=0.0, step=0.1)
    weight_unit  = st.selectbox("Unit", ["g", "kg"])

    st.subheader("QC Checklist")
    checklist = {item: st.checkbox(item, value=False) for item in CHECKLIST_ITEMS}

    notes     = st.text_area("Catatan (optional)")
    submitted = st.form_submit_button("Submit & Print Sticker")

# ============================================================
# SAVE — ingredients go into items table only
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

    try:
        with engine.begin() as conn:
            bhn_id = generate_random_bhn_id(conn)

        # Insert into items with label="received"
        # reason stores the QC checklist payload
        db_insert_item(
            item_id=bhn_id,
            name=name.strip(),
            weight_g=weight_g,
            unit="g",
            reason=json.dumps(qc_payload, ensure_ascii=False),
        )

        st.success(f"✅ Saved: **{bhn_id}** — {name.strip()} ({weight_g}g)")
        st.info("Print sticker with this ID and attach to the container.")

        # TODO: enqueue print job via db_enqueue_print() if needed

    except Exception as e:
        st.error(f"Error saving data: {e}")