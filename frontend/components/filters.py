# frontend/components/filters.py
import streamlit as st
import pandas as pd
import time

def render_auto_refresh(engine):
    """Render auto-refresh controls and handle refresh logic"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔄 Auto-Refresh")
    
    # Initialize session state for auto-refresh
    if "auto_refresh_enabled" not in st.session_state:
        st.session_state.auto_refresh_enabled = False
    if "last_refresh_time" not in st.session_state:
        st.session_state.last_refresh_time = time.time()
    
    auto_refresh = st.sidebar.checkbox(
        "Enable Auto-Refresh", 
        value=st.session_state.auto_refresh_enabled,
        help="Automatically refresh data at regular intervals"
    )
    st.session_state.auto_refresh_enabled = auto_refresh
    
    refresh_interval = st.sidebar.slider(
        "Fallback Refresh Interval (seconds)",
        min_value=10,
        max_value=300,
        value=60,
        step=5,
        disabled=not auto_refresh,
        help="Maximum time between refreshes (will update sooner if new data is detected)"
    )
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Now", type="primary"):
        st.session_state.last_refresh_time = time.time()
        st.rerun()
    
    # Auto-refresh logic
    if auto_refresh:
        current_time = time.time()
        time_since_refresh = current_time - st.session_state.last_refresh_time
        
        # Check for new data every 3 seconds (lightweight query)
        if "last_data_check" not in st.session_state:
            st.session_state.last_data_check = 0
        
        if current_time - st.session_state.last_data_check >= 3:
            st.session_state.last_data_check = current_time
            
            # Quick check: get latest timestamps from each table
            try:
                latest_timestamps = {}
                for table in ["items", "events", "trays", "tray_items"]:
                    result = pd.read_sql_query(
                        f"SELECT MAX(created_at) as latest FROM {table}",
                        engine
                    )
                    latest_timestamps[table] = result['latest'].iloc[0] if not result.empty else None
                
                # Store latest timestamps if not exists
                if "known_timestamps" not in st.session_state:
                    st.session_state.known_timestamps = latest_timestamps
                    st.session_state.last_refresh_time = current_time
                    st.rerun()
                
                # Check if any timestamp has changed (new data!)
                for table, timestamp in latest_timestamps.items():
                    if timestamp != st.session_state.known_timestamps.get(table):
                        st.sidebar.success(f"🆕 New {table} detected!")
                        st.session_state.known_timestamps = latest_timestamps
                        st.session_state.last_refresh_time = current_time
                        time.sleep(0.5)  # Brief pause to show the notification
                        st.rerun()
                        break
            except Exception as e:
                st.sidebar.error(f"Check failed: {e}")
        
        # Regular interval refresh (fallback)
        if time_since_refresh >= refresh_interval:
            st.session_state.last_refresh_time = current_time
            st.rerun()
        else:
            # Show countdown
            time_until_refresh = refresh_interval - int(time_since_refresh)
            st.sidebar.info(f"⏱️ Next refresh in {time_until_refresh}s")
            time.sleep(1)  # Small sleep to avoid too frequent reruns
            st.rerun()
    
    st.sidebar.markdown("---")

def render_date_filter(events: pd.DataFrame) -> tuple:
    """Render date range filter in sidebar
    
    Args:
        events: Events DataFrame with event_date column
        
    Returns:
        tuple: (start_date, end_date) or empty tuple
    """
    if not events.empty:
        min_date = events["event_date"].min()
        max_date = events["event_date"].max()
    else:
        min_date = max_date = None

    date_range = st.sidebar.date_input(
        "Event date range",
        value=(min_date, max_date) if min_date and max_date else [],
        help="Filter events by date (based on ts_local).",
    )
    
    return date_range

def render_division_filter(events: pd.DataFrame) -> list:
    """Render division filter in sidebar
    
    Args:
        events: Events DataFrame with event_division column
        
    Returns:
        list: Selected division names
    """
    divisions = sorted(
        set(events["event_division"].dropna().unique().tolist())
    )
    selected_divisions = st.sidebar.multiselect(
        "Division (from events)",
        options=divisions,
        default=divisions,
    )
    
    return selected_divisions

def render_staff_filter(staffs: pd.DataFrame) -> list:
    """Render staff filter in sidebar
    
    Args:
        staffs: Staffs DataFrame with name and phone columns
        
    Returns:
        list: Selected staff phone numbers as strings
    """
    # Staff filter by name/phone
    staff_options = (
        staffs.assign(label=lambda df: df["name"] + " (" + df["phone"].astype(str) + ")")
        if not staffs.empty
        else pd.DataFrame(columns=["phone", "label"])
    )

    selected_staff_labels = st.sidebar.multiselect(
        "Staff",
        options=staff_options["label"].tolist(),
        default=staff_options["label"].tolist(),
    )

    # Map labels back to phones
    selected_staff_phones = (
        staff_options[staff_options["label"].isin(selected_staff_labels)]["phone"]
        .astype(str)
        .tolist()
        if not staff_options.empty
        else []
    )
    
    return selected_staff_phones

def apply_event_filters(
    events: pd.DataFrame,
    date_range: tuple,
    selected_divisions: list,
    selected_staff_phones: list
) -> pd.DataFrame:
    """Apply all filters to events DataFrame
    
    Args:
        events: Original events DataFrame
        date_range: Tuple of (start_date, end_date)
        selected_divisions: List of division names
        selected_staff_phones: List of phone numbers
        
    Returns:
        pd.DataFrame: Filtered events
    """
    events_filtered = events.copy()

    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range
        if start_date and end_date:
            events_filtered = events_filtered[
                (events_filtered["event_date"] >= start_date)
                & (events_filtered["event_date"] <= end_date)
            ]

    if selected_divisions:
        events_filtered = events_filtered[
            events_filtered["event_division"].isin(selected_divisions)
        ]

    if selected_staff_phones:
        events_filtered = events_filtered[
            events_filtered["from_number"].astype(str).isin(selected_staff_phones)
        ]
    
    return events_filtered