# frontend/dashboard.py
import streamlit as st
from datetime import datetime

from components.auth import login, render_logout_button, check_session_from_url
from components.filters import (
    render_auto_refresh, render_date_filter, 
    render_division_filter, render_staff_filter, apply_event_filters
)
from components.charts import render_activity_charts, render_items_summary
from pages.overview import render_overview
from pages.items import render_items_tab
from pages.events import render_events_tab
from pages.staff import render_staff_tab
from pages.trays import render_trays_tab
from pages.delivery import render_delivery_assignments
from utils.data_loader import prepare_data, engine

def main():
    """Main dashboard orchestrator"""
    # Check for session token in URL
    check_session_from_url()
    
    if st.session_state.logged_in:
        st.set_page_config(
            page_title="MBG Kitchen – WhatsApp Ops Dashboard",
            layout="wide",
        )
        st.title("📊 MBG Kitchen – WhatsApp Ops Dashboard")
        
        # Sidebar
        st.sidebar.header("Filters")
        render_logout_button()
        render_auto_refresh(engine)
        
        # Load data
        try:
            items, events, staffs, trays, tray_items = prepare_data()
        except FileNotFoundError as e:
            st.error(str(e))
            st.stop()
        
        # Data counts expander
        with st.sidebar.expander("📊 Data Counts", expanded=False):
            st.write(f"**Items:** {len(items)}")
            st.write(f"**Events:** {len(events)}")
            st.write(f"**Staffs:** {len(staffs)}")
            st.write(f"**Trays:** {len(trays)}")
            st.write(f"**Tray Items:** {len(tray_items)}")
            st.caption(f"Last loaded: {datetime.now().strftime('%H:%M:%S')}")
        
        # Filters
        date_range = render_date_filter(events)
        selected_divisions = render_division_filter(events)
        selected_staff_phones = render_staff_filter(staffs)
        events_filtered = apply_event_filters(
            events, date_range, selected_divisions, selected_staff_phones
        )
        
        # Main content
        render_overview(items, events, staffs, trays)
        render_activity_charts(events_filtered)
        render_items_summary(items)
        render_delivery_assignments()
        
        # Tabs
        tab1, tab2, tab3, tab4 = st.tabs(
            ["📦 Items", "📝 Events Log", "👤 Staff", "🧺 Trays"]
        )
        with tab1:
            render_items_tab(items)
        with tab2:
            render_events_tab(events_filtered)
        with tab3:
            render_staff_tab(staffs)
        with tab4:
            render_trays_tab(trays, tray_items)
    else:
        login()

if __name__ == "__main__":
    main()