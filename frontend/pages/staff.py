# frontend/pages/staff.py
import streamlit as st
import pandas as pd

def render_staff_tab(staffs: pd.DataFrame):
    """Render staff tab content
    
    Args:
        staffs: Staffs DataFrame
    """
    st.markdown("### Staff")
    if not staffs.empty:
        st.dataframe(
            staffs.rename(
                columns={
                    "phone": "phone",
                    "name": "name",
                    "staff_division": "division",
                }
            ),
            use_container_width=True,
        )
    else:
        st.info("No staff registered.")