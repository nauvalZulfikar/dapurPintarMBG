import streamlit as st

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