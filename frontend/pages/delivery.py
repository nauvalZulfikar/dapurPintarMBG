# frontend/pages/delivery.py
import streamlit as st
import pandas as pd
from utils.data_loader import optimize_delivery

def render_delivery_assignments():
    """Render tray assignments to schools section"""
    st.subheader("Tray Assignments to Schools")
    
    # Fetch assignments
    try:
        assignments = optimize_delivery()
        
        # Check if assignments are available
        if assignments:
            # Convert the assignments dictionary into a DataFrame for easier visualization
            assignments_list = []
            for school_id, school_data in assignments.items():
                school_name = school_data["school_name"]
                student_count = school_data["student_count"]
                # Get the length of the assigned_trays list
                assigned_trays_count = len(school_data["assigned_trays"])
                
                assignments_list.append({
                    "School Name": school_name,
                    "Student Count": student_count,
                    "Assigned Trays Count": assigned_trays_count
                })
            
            assignments_df = pd.DataFrame(assignments_list)
            st.dataframe(assignments_df, use_container_width=True)
        else:
            st.info("No assignments available.")
    except Exception as e:
        st.error(f"Error loading assignments: {e}")