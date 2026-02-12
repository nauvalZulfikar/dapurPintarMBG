import re
import streamlit as st

# TRY-XXXXXXXX (8 random alphanumeric chars)
TRAY_ID_PATTERN = re.compile(r"^TRY-[A-Z0-9]{8}$")

st.set_page_config(
    page_title="Tray Status",
    page_icon="📦",
    layout="centered"
)

# Read tray_id from query params
params = st.query_params
tray_id = params.get("tray_id")

st.title("📦 Tray Portal")

# Validate tray ID
if not tray_id or not TRAY_ID_PATTERN.fullmatch(tray_id):
    st.error("Invalid or missing tray ID. Please scan the official QR code again.")
    st.stop()

# --- Coming soon screen ---
st.success(f"Tray ID verified: **{tray_id}**")
st.markdown("## 🚧 Coming soon")
st.write("This portal will display tray status and history from our database.")


# --- Later, when you want to fetch data from Supabase, you’ll do something like: ---
# @st.cache_data(ttl=10)
# def fetch_tray(_tray_id: str):
#     url = st.secrets["SUPABASE_URL"]
#     key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]  # server-side only
#     supabase: Client = create_client(url, key)
#     res = supabase.table("trays").select("*").eq("tray_id", _tray_id).single().execute()
#     return res.data
#
# tray_data = fetch_tray(tray_id)
# st.json(tray_data)
