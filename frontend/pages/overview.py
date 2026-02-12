# frontend/pages/overview.py
import streamlit as st
import pandas as pd

def render_overview(
    items: pd.DataFrame,
    events: pd.DataFrame,
    staffs: pd.DataFrame,
    trays: pd.DataFrame
):
    """Render overview metrics section
    
    Args:
        items: Items DataFrame
        events: Events DataFrame
        staffs: Staffs DataFrame
        trays: Trays DataFrame
    """
    st.subheader("Overview")

    col1, col2, col3, col4 = st.columns(4)

    total_items = len(items)
    total_events = len(events)
    total_staffs = len(staffs)
    total_trays = len(trays)

    with col1:
        st.metric("Total Items", total_items)
    with col2:
        st.metric("Total Events", total_events)
    with col3:
        st.metric("Total Staff", total_staffs)
    with col4:
        st.metric("Total Trays", total_trays)

    # Date range display
    if not events.empty:
        st.caption(
            f"Events from **{events['event_date'].min()}** "
            f"to **{events['event_date'].max()}** "
            f"(based on local timestamps)."
        )