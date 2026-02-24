import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

from backend.core.database import local_enqueue_scan, local_enqueue_error
from frontend.staffs.common import validate_packing
from backend.core.syncer import start_sync_thread
from backend.core.database import init_db
import os

from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="Packing", layout="centered")
# Start local DB + background sync thread once per session
if "sync_started" not in st.session_state:
    init_db()
    start_sync_thread()
    st.session_state.sync_started = True
    
st.title("Packing – Scan Tray")

# 🔊 SOUND FUNCTION
def play_sound(filename):
    st.components.v1.html(f"""
        <script>
        var audio = new Audio("static/{filename}");
        audio.play();
        </script>
    """, height=0)

# Initialize session state
if "message" not in st.session_state:
    st.session_state.message = None

if "sound" not in st.session_state:
    st.session_state.sound = None

# ✅ HANDLE SCAN
def handle_scan():
    scan = st.session_state.scan_input.strip()
    if not scan:
        return

    when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ok, reason = validate_packing(scan)

    if not ok:
        local_enqueue_error(scan, "Packing", reason)
        st.session_state.message = ("error", f"GAGAL\n{when}\n{reason}")
        st.session_state.sound = "failed.mp3"
    else:
        local_enqueue_scan(scan, "Packing", "packed")
        st.session_state.message = ("success", f"SUKSES\n{when}")
        st.session_state.sound = "success.mp3"

    # Clear input safely
    st.session_state.scan_input = ""

# 🔎 INPUT FIELD WITH CALLBACK
st.text_input(
    "Scan TRY Code",
    key="scan_input",
    on_change=handle_scan
)

# ✅ SHOW RESULT
if st.session_state.message:
    status, text = st.session_state.message

    if status == "error":
        st.error(text)
    else:
        st.success(text)

    if st.session_state.sound:
        play_sound(st.session_state.sound)

# 🔁 AUTO FOCUS
components.html("""
<script>
const input = window.parent.document.querySelector('input');
if (input) { input.focus(); }
</script>
""", height=0)