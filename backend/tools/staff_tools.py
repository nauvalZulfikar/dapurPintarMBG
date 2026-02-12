from backend.core.database import db_get_staff, db_get_reg, db_set_reg, db_clear_reg, db_set_staff
from typing import Dict, Any, Optional
from backend.utils.validators import canonical_division

# ---------- Agent Tools (implementations) ----------
def tool_get_staff(phone: str) -> Dict[str, Any]:
    return db_get_staff(phone) or {}

def tool_get_registration(phone: str) -> Dict[str, Any]:
    return db_get_reg(phone) or {}

def tool_set_registration(phone: str, state: str, temp_name: Optional[str] = None) -> Dict[str, Any]:
    db_set_reg(phone, state, temp_name)
    return {"ok": True}

def tool_clear_registration(phone: str) -> Dict[str, Any]:
    db_clear_reg(phone)
    return {"ok": True}

def tool_register_staff(phone: str, division_text: str, name: Optional[str] = None) -> Dict[str, Any]:
    """Name is optional; if missing, pull from registrations.temp_name."""
    if not name:
        reg = db_get_reg(phone) or {}
        name = (reg.get("temp_name") or "Staff").strip()
    div = canonical_division(division_text or "")
    if not div:
        return {"ok": False, "error": "invalid_division"}
    db_set_staff(phone, name, div)
    db_clear_reg(phone)
    return {"ok": True, "division": div, "name": name}
