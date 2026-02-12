from pydantic import BaseModel
from datetime import datetime

class PrintCompletePayload(BaseModel):
    id: int


class FoodTray:
    def __init__(self, tray_id: str, prepared_time: datetime):
        self.tray_id = tray_id
        self.prepared_time = prepared_time

class School:
    def __init__(self, school_id: int, name: str, distance: float, student_count: int):
        self.school_id = school_id
        self.name = name
        self.distance = distance
        self.student_count = student_count
        self.capacity_left = student_count
        self.assigned_trays = []

    def assign_tray(self, tray: FoodTray):
        if self.capacity_left > 0:
            self.assigned_trays.append(tray.tray_id)
            self.capacity_left -= 1
            return True
        return False
