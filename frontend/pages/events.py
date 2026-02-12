# frontend/pages/events.py
import streamlit as st
import pandas as pd

def render_events_tab(events_filtered: pd.DataFrame):
    """Render events tab content
    
    Args:
        events_filtered: Filtered events DataFrame
    """
    st.markdown("### Events (Filtered by sidebar)")
    if not events_filtered.empty:
        # Select columns to show
        cols_to_show = [
            "id",
            "ts_local",
            "event_division",
            "from_number",
            "name",
            "subject_type",
            "subject_id",
            "message_text",
            "duration_hms",
            "duration_seconds",
        ]
        cols_to_show = [c for c in cols_to_show if c in events_filtered.columns]
        st.dataframe(events_filtered[cols_to_show], use_container_width=True)
    else:
        st.info("No events for the current filter.")