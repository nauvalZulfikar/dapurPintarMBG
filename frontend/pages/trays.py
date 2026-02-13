# frontend/pages/trays.py
import streamlit as st
import pandas as pd

def render_trays_tab(trays: pd.DataFrame, tray_items: pd.DataFrame):
    """Render trays tab content
    
    Args:
        trays: Trays DataFrame
        tray_items: Tray items DataFrame
    """
    st.markdown("### Trays & Tray Items")
    
    # Show raw counts first
    st.info(f"Found **{len(trays)}** trays and **{len(tray_items)}** tray items in database")
    
    col_t1, col_t2 = st.columns(2)

    with col_t1:
        st.markdown("**Trays**")
        if not trays.empty:
            # Sort by created_at descending to show newest first
            trays_sorted = trays.sort_values('created_at', ascending=False)
            st.dataframe(trays_sorted, use_container_width=True)
        else:
            st.warning("No trays in database yet.")

    with col_t2:
        st.markdown("**Tray Items**")
        if not tray_items.empty:
            # Sort by bound_at descending to show newest first
            tray_items_sorted = tray_items.sort_values('bound_at', ascending=False)
            st.dataframe(tray_items_sorted, use_container_width=True)
        else:
            st.warning("No tray_items in database yet.")
            
    # Add a detailed view showing tray items joined with tray info
    if not tray_items.empty and not trays.empty:
        st.markdown("### Detailed Tray-Item Binding")
        tray_items['tray_id'] = tray_items['tray_id'].astype(str)
        trays['id'] = trays['id'].astype(str)
        merged = tray_items.merge(
            trays[['id', 'created_at']],
            left_on='tray_id',
            right_on='id',
        )
        merged_sorted = merged.sort_values('bound_at', ascending=False)
        st.dataframe(merged_sorted, use_container_width=True)
