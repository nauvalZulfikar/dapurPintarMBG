# frontend/pages/items.py
import streamlit as st
import pandas as pd

def render_items_tab(items: pd.DataFrame):
    """Render items tab content
    
    Args:
        items: Items DataFrame
    """
    st.markdown("### Items")
    if not items.empty:
        item_name_filter = st.text_input(
            "Search by item name (contains)", value=""
        )
        df_items = items.copy()
        if item_name_filter:
            df_items = df_items[
                df_items["name"]
                .astype(str)
                .str.contains(item_name_filter, case=False, na=False)
            ]
        st.dataframe(df_items, width=True)
    else:
        st.info("No items in database.")