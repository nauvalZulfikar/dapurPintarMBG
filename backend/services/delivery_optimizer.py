# DPMBG_Project\backend\services\delivery_optimizer.py
import json
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.core.models import FoodTray, School
from backend.core.database import engine
from sqlalchemy import text

def load_schools_from_json(file_path: str) -> List[School]:
    with open(file_path, 'r') as f:
        schools_data = json.load(f)

    return [
        School(
            school_id=s["school_id"],
            name=s["name"],
            distance=s["distance"],
            student_count=s["student_count"],
        )
        for s in schools_data
    ]

def fetch_trays_packed_times(db_session: Session) -> List[FoodTray]:
    today = datetime.now().date()
    rows = db_session.execute(
        text("""
            SELECT tray_id, created_at
            FROM trays
            WHERE label = 'packed'
            AND created_date = :today
            ORDER BY created_at ASC
        """),
        {"today": str(today)}
    ).fetchall()

    food_trays: List[FoodTray] = []
    for tray_id, created_at_str in rows:
        prepared_time = datetime.fromisoformat(created_at_str)
        food_trays.append(FoodTray(tray_id=tray_id, prepared_time=prepared_time))

    return food_trays

# Global variable to track the last reset date (you can also store this in the database for persistence)
last_reset_date = None

# Assign trays to schools function
def assign_trays_to_schools(food_trays: List[FoodTray], schools: List[School], db_session: Session) -> Dict[int, Dict[str, Any]]:
    # # Reset assignments if it's a new day
    # reset_assignments_if_new_day()

    # Ensure trays are in prepared order (earliest packed first)
    food_trays = sorted(food_trays, key=lambda t: t.prepared_time)

    # Nearest schools first
    sorted_schools = sorted(schools, key=lambda s: s.distance)

    assignments: Dict[int, Dict[str, Any]] = {}

    for tray in food_trays:
        for school in sorted_schools:
            if school.assign_tray(tray):  # Check if the school can accept the tray
                assignments.setdefault(school.school_id, {
                    "school_name": school.name,
                    "student_count": school.student_count,
                    "assigned_trays": []
                })["assigned_trays"].append(tray.tray_id)
                break

    return assignments
