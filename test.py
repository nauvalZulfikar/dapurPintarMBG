# receiving.py — Multi-page Scanner App
# Pages: Receiving | Processing | Packing | Delivery

import os
import sys
import json
import string
import secrets
import time
from datetime import datetime, date, timedelta
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# STREAMLIT SECRETS BRIDGE
# ============================================================
try:
    _db_url = st.secrets.get("DATABASE_URL")
    if _db_url:
        os.environ["DATABASE_URL"] = _db_url
except Exception:
    pass

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from sqlalchemy import text, select
from sqlalchemy.exc import OperationalError

from backend.core.database import (
    engine,
    local_engine,
    remote_engine,
    remote_items,
    remote_trays,
    remote_tray_items,
    local_enqueue_scan,
    local_enqueue_error,
    init_db,
    db_insert_item,
)
from backend.core.syncer import start_sync_thread
from backend.services.printing import generate_label, db_create_print_job

# ============================================================
# CONSTANTS
# ============================================================

CHECKLIST_ITEMS = [
    "Packaging OK",
    "Expiry OK",
    "Temperature OK",
    "Cleanliness OK",
]

SCHOOLS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "schools.json",
)

COUNTDOWN_BASE_URL = "https://dapurpintarmbg-countdown.streamlit.app"
BHN_PREFIX = "BHN-"
TRAY_PREFIX = "TRY-"
TRAY_LEN = 12
DB_LOCK_RETRIES = 6
DB_LOCK_SLEEP = 0.15

PAGES = ["📦 Receiving", "⚙️ Processing", "🗂️ Packing", "🚚 Delivery"]

# ============================================================
# HELPERS — shared
# ============================================================

def to_grams(value: float, unit: str) -> int:
    return int(round(value * 1000)) if unit == "kg" else int(round(value))


def generate_random_bhn_id(conn, length=6):
    alphabet = string.ascii_uppercase + string.digits
    while True:
        rand = "".join(secrets.choice(alphabet) for _ in range(length))
        new_id = f"BHN-{rand}"
        exists = conn.execute(
            text("SELECT 1 FROM items WHERE id = :id"), {"id": new_id}
        ).fetchone()
        if not exists:
            return new_id


def extract_code(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    lower = s.lower()
    if any(k in lower for k in ("tray_id=", "ingredient_id=", "id=", "barcode=")):
        for part in s.replace("?", "&").split("&"):
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k.strip().lower() in {"tray_id", "ingredient_id", "id", "barcode"} and v.strip():
                return v.strip()
    for prefix in (TRAY_PREFIX, BHN_PREFIX):
        idx = s.find(prefix)
        if idx != -1:
            chunk = s[idx : idx + 64].split()[0]
            for delim in ["&", "?", "#", "/", "\\", '"', "'", ",", ";", ")", "(", "]", "[", "}", "{"]:
                chunk = chunk.split(delim)[0]
            return chunk
    return s


def _exec_retry(fn):
    last_err = None
    for _ in range(DB_LOCK_RETRIES):
        try:
            return fn()
        except OperationalError as e:
            last_err = e
            if any(kw in str(e).lower() for kw in ("locked", "busy")):
                time.sleep(DB_LOCK_SLEEP)
                continue
            raise
    raise last_err


# ============================================================
# HELPERS — remote DB validators
# ============================================================

def _get_remote_item(code: str):
    if not remote_engine:
        return None
    with remote_engine.connect() as c:
        return c.execute(
            select(remote_items.c.receiving, remote_items.c.processing).where(
                remote_items.c.id == code
            )
        ).first()


def _get_remote_tray(tray_id: str):
    if not remote_engine:
        return None
    with remote_engine.connect() as c:
        return c.execute(
            select(
                remote_trays.c.packing,
                remote_trays.c.delivery,
                remote_trays.c.created_date_packing,
                remote_trays.c.created_date_delivery,
            ).where(remote_trays.c.tray_id == tray_id)
        ).first()


def _is_remote_tray_registered(tray_id: str) -> bool:
    if not remote_engine:
        return False
    with remote_engine.connect() as c:
        return (
            c.execute(
                select(remote_tray_items.c.tray_id).where(
                    remote_tray_items.c.tray_id == tray_id
                )
            ).first()
            is not None
        )


def validate_processing(code: str) -> tuple[bool, str]:
    if not code:
        return False, "EMPTY_SCAN"
    if not code.startswith(BHN_PREFIX):
        return False, f"NOT_AN_INGREDIENT_CODE (expected BHN-, got: {code[:8]})"
    try:
        row = _get_remote_item(code)
    except Exception as e:
        return False, f"SUPABASE_UNREACHABLE: {e}"
    if row is None:
        return False, "INGREDIENT_NOT_FOUND"
    if not row.receiving:
        return False, "NOT_RECEIVED"
    if row.processing:
        return False, "ALREADY_PROCESSED"
    return True, ""


def validate_packing(code: str) -> tuple[bool, str]:
    if not code:
        return False, "EMPTY_SCAN"
    if not code.startswith(TRAY_PREFIX):
        return False, f"NOT_A_TRAY_CODE (expected TRY-, got: {code[:8]})"
    if len(code) != TRAY_LEN:
        return False, f"INVALID_TRAY_ID_LENGTH (expected {TRAY_LEN}, got {len(code)})"
    try:
        registered = _is_remote_tray_registered(code)
        row = _get_remote_tray(code)
    except Exception as e:
        return False, f"SUPABASE_UNREACHABLE: {e}"
    if not registered:
        return False, "TRAY_NOT_REGISTERED"
    if row and row.packing:
        if row.created_date_packing == date.today():
            return False, "ALREADY_PACKED_TODAY"
    return True, ""


def validate_delivery(code: str) -> tuple[bool, str]:
    if not code:
        return False, "EMPTY_SCAN"
    if not code.startswith(TRAY_PREFIX):
        return False, f"NOT_A_TRAY_CODE (expected TRY-, got: {code[:8]})"
    if len(code) != TRAY_LEN:
        return False, f"INVALID_TRAY_ID_LENGTH (expected {TRAY_LEN}, got {len(code)})"
    try:
        registered = _is_remote_tray_registered(code)
        row = _get_remote_tray(code)
    except Exception as e:
        return False, f"SUPABASE_UNREACHABLE: {e}"
    if not registered:
        return False, "TRAY_NOT_REGISTERED"
    if not row or not row.packing:
        return False, "NOT_PACKED"
    if row.delivery:
        if row.created_date_delivery == date.today():
            return False, "ALREADY_DELIVERED_TODAY"
    return True, ""


# ============================================================
# HELPERS — delivery label & processing
# ============================================================

def load_schools():
    with open(SCHOOLS_FILE, "r", encoding="utf-8") as f:
        schools = json.load(f)
    return sorted(schools, key=lambda s: s["distance"])


def generate_delivery_tspl(tray_id: str, allocations: list[dict]):
    qr_link = f"{COUNTDOWN_BASE_URL}/?tray_id={tray_id}"
    y = 15
    lines = ""
    for alloc in allocations:
        lines += f'TEXT 10,{y},"0",0,6,6,"{alloc["school"]} {alloc["n_trays"]}"\n'
        y += 12
    return f"""
SIZE 50 mm, 21 mm
GAP 1 mm, 0 mm
SPEED 4
DENSITY 15
CLS
{lines}
QRCODE 300,5,L,3,A,0,"{qr_link}"
PRINT 1,1
"""


def process_delivery_scan(tray_id: str):
    TOTAL_TRAYS = 10
    schools = load_schools()
    allocations = []
    remaining = TOTAL_TRAYS
    for school in schools:
        if school["student_count"] <= 0:
            continue
        take = min(school["student_count"], remaining)
        allocations.append({"school": school["name"], "n_trays": take})
        remaining -= take
        if remaining == 0:
            break
    if remaining > 0:
        raise Exception("Not enough total student_count across schools.")
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE trays
                SET delivery = TRUE,
                    created_at_delivery = :now,
                    created_date_delivery = :today
                WHERE tray_id = :tray_id
            """),
            {"tray_id": tray_id, "now": datetime.utcnow(), "today": date.today()},
        )
    tspl = generate_delivery_tspl(tray_id, allocations)
    db_create_print_job(tspl)
    return {"tray_id": tray_id, "allocations": allocations}


# ============================================================
# SCANNER WIDGET — reusable for Processing / Packing / Delivery
# ============================================================

def scanner_widget(mode: str):
    """
    Streamlit UI for a barcode-scanner step.
    Uses a text_input as the scan target (barcode scanners act like keyboards).
    On submit, validates and enqueues the scan.
    """
    write_label = {"Processing": "processed", "Packing": "packed", "Delivery": "delivered"}[mode]
    validators  = {"Processing": validate_processing, "Packing": validate_packing, "Delivery": validate_delivery}

    st.markdown(f"Point your barcode scanner at the input field below and scan.")

    # Session state for result history
    history_key = f"scan_history_{mode}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []  # list of (code, ok, reason, when)

    with st.form(key=f"scan_form_{mode}", clear_on_submit=True):
        raw = st.text_input(
            "🔍 Scan barcode",
            placeholder=f"Scan {'BHN-XXXXXX' if mode == 'Processing' else 'TRY-XXXXXXXXX'} here…",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("✅ Submit", use_container_width=True)

    if submitted and raw.strip():
        code = extract_code(raw.strip())
        when = datetime.now().strftime("%H:%M:%S")

        try:
            ok, reason = validators[mode](code)

            if ok:
                _exec_retry(lambda: local_enqueue_scan(code, mode, write_label))
                if mode == "Delivery":
                    result = process_delivery_scan(code)
                    alloc_str = ", ".join(
                        f"{a['school']} ×{a['n_trays']}" for a in result["allocations"]
                    )
                    reason = f"Label dicetak → {alloc_str}"
                st.session_state[history_key].insert(0, (code, True, reason, when))
            else:
                _exec_retry(lambda: local_enqueue_error(code or raw, mode, reason))
                st.session_state[history_key].insert(0, (code, False, reason, when))

        except Exception as e:
            err = f"EXCEPTION: {type(e).__name__}: {e}"
            try:
                local_enqueue_error(code or raw, mode, err)
            except Exception:
                pass
            st.session_state[history_key].insert(0, (code, False, err, when))

        # Keep only last 20
        st.session_state[history_key] = st.session_state[history_key][:20]

    # ---- Result history ----
    history = st.session_state[history_key]
    if history:
        st.markdown("---")
        st.caption("Riwayat scan (sesi ini)")
        for code, ok, reason, when in history:
            if ok:
                st.success(f"**{when}** — ✅ SUKSES &nbsp; `{code}`" + (f"  \n{reason}" if reason else ""))
            else:
                st.error(f"**{when}** — ❌ GAGAL &nbsp; `{code}`  \n{reason}")


# ============================================================
# PAGE — Receiving
# ============================================================

def page_receiving():
    st.title("📦 Receiving — New Container")

    with st.form("receiving_form"):
        st.subheader("Bahan")
        name         = st.text_input("Nama Bahan (e.g. Ayam, Jeruk)")
        weight_value = st.number_input("Berat", min_value=0.0, step=0.1)
        weight_unit  = st.selectbox("Unit", ["g", "kg"])

        st.subheader("QC Checklist")
        checklist = {item: st.checkbox(item, value=False) for item in CHECKLIST_ITEMS}

        notes     = st.text_area("Catatan (optional)")
        submitted = st.form_submit_button("Submit & Print Sticker", use_container_width=True)

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

            db_insert_item(
                item_id=bhn_id,
                name=name.strip(),
                weight_g=weight_g,
                unit="g",
                reason=json.dumps(qc_payload, ensure_ascii=False),
            )

            tspl = generate_label(bhn_id, name, weight_g)
            db_create_print_job(tspl)

            st.success(f"✅ Saved: **{bhn_id}** — {name.strip()} ({weight_g}g)")
            st.info("Print sticker with this ID and attach to the container.")

        except Exception as e:
            st.error(f"Error saving data: {e}")


# ============================================================
# PAGE — Processing
# ============================================================

def page_processing():
    st.title("⚙️ Processing — Scan Bahan")
    st.caption("Scan ingredient barcode (BHN-XXXXXX) to mark as processed.")
    scanner_widget("Processing")


# ============================================================
# PAGE — Packing
# ============================================================

def page_packing():
    st.title("🗂️ Packing — Scan Tray")
    st.caption("Scan tray barcode (TRY-XXXXXXXXX) to mark as packed.")
    scanner_widget("Packing")


# ============================================================
# PAGE — Delivery
# ============================================================

def page_delivery():
    st.title("🚚 Delivery — Scan Tray")
    st.caption("Scan tray barcode (TRY-XXXXXXXXX) to mark as delivered and print allocation label.")
    scanner_widget("Delivery")


# ============================================================
# APP SHELL
# ============================================================

def main():
    st.set_page_config(page_title="Dapur Pintar Scanner", layout="centered", page_icon="🍱")

    # Init local DB + sync thread once per session
    if "initialized" not in st.session_state:
        try:
            init_db()
            start_sync_thread()
        except Exception:
            pass
        st.session_state["initialized"] = True

    # Sidebar navigation
    with st.sidebar:
        st.markdown("## 🍱 Dapur Pintar")
        st.markdown("---")
        page = st.radio("Pilih halaman", PAGES, label_visibility="collapsed")
        st.markdown("---")
        st.caption(f"📅 {date.today().strftime('%d %B %Y')}")

    # Route
    if page == "📦 Receiving":
        page_receiving()
    elif page == "⚙️ Processing":
        page_processing()
    elif page == "🗂️ Packing":
        page_packing()
    elif page == "🚚 Delivery":
        page_delivery()


if __name__ == "__main__":
    main()