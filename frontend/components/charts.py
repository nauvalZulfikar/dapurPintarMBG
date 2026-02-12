# frontend/components/charts.py
import streamlit as st
import pandas as pd

def render_activity_charts(events_filtered: pd.DataFrame):
    """Render activity charts section
    
    Args:
        events_filtered: Filtered events DataFrame
    """
    st.subheader("Activity Charts (Filtered)")

    chart_col1, chart_col2 = st.columns(2)

    # Events per day
    if not events_filtered.empty:
        events_per_day = (
            events_filtered.groupby("event_date")["id"]
            .count()
            .rename("events")
            .reset_index()
        )
        with chart_col1:
            st.markdown("**Events per Day**")
            st.line_chart(
                events_per_day.set_index("event_date")["events"]
            )
    else:
        with chart_col1:
            st.info("No events for current filter.")

    # Events by division
    if not events_filtered.empty:
        events_by_div = (
            events_filtered.groupby("event_division")["id"]
            .count()
            .rename("events")
            .reset_index()
        )
        with chart_col2:
            st.markdown("**Events by Division**")
            st.bar_chart(
                events_by_div.set_index("event_division")["events"]
            )
    else:
        with chart_col2:
            st.info("No events for current filter.")

def render_items_summary(items: pd.DataFrame):
    """Render items summary section
    
    Args:
        items: Items DataFrame
    """
    st.subheader("Items Summary")
    if not items.empty:
        items_by_name = (
            items.groupby("name")["id"]
            .count()
            .rename("count")
            .reset_index()
            .sort_values("count", ascending=False)
        )
        st.markdown("**Items by Name**")
        st.bar_chart(items_by_name.set_index("name")["count"])
    else:
        st.info("No items in database.")

    st.markdown("---")