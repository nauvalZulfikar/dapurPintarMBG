import streamlit as st
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

st.set_page_config(
    page_title="DPMBG System",
    layout="wide"
)

st.title("Dapur Pintar MBG")

st.markdown("""
Select a module from the sidebar:

- Receiving
- Processing
- Packing
- Delivery
""")