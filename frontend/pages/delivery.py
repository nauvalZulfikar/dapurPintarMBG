# frontend/pages/delivery.py
import streamlit as st
import pandas as pd
from utils.data_loader import optimize_delivery

# frontend/pages/delivery.py
def render_delivery_assignments():
    """Render tray assignments to schools section"""
    st.subheader("Tray Assignments to Schools")
    
    # Debug info
    from frontend.utils.data_loader import SCHOOLS_JSON_PATH
    import os
    
    st.write(f"**Debug Info:**")
    st.write(f"- Schools JSON Path: `{SCHOOLS_JSON_PATH}`")
    st.write(f"- File exists: {os.path.exists(SCHOOLS_JSON_PATH)}")
    
    if os.path.exists(SCHOOLS_JSON_PATH):
        with open(SCHOOLS_JSON_PATH, 'r') as f:
            import json
            schools_data = json.load(f)
            st.write(f"- Schools in JSON: {len(schools_data)}")
    
    # Fetch assignments
    try:
        assignments = optimize_delivery()
        
        st.write(f"**Assignments received:** {type(assignments)}")
        st.write(f"**Number of schools assigned:** {len(assignments) if assignments else 0}")
        
        # Check if assignments are available
        if assignments:
            assignments_list = []
            for school_id, school_data in assignments.items():
                school_name = school_data["school_name"]
                student_count = school_data["student_count"]
                assigned_trays_count = len(school_data["assigned_trays"])
                
                assignments_list.append({
                    "School Name": school_name,
                    "Student Count": student_count,
                    "Assigned Trays Count": assigned_trays_count
                })
            
            if assignments_list:
                assignments_df = pd.DataFrame(assignments_list)
                st.dataframe(assignments_df, use_container_width=True)
            else:
                st.warning("Assignments dictionary is not empty, but no schools were processed.")
        else:
            st.info("No assignments available (empty result from optimize_delivery).")
            
    except Exception as e:
        st.error(f"**Error loading assignments:** {e}")
        import traceback
        st.code(traceback.format_exc())        
