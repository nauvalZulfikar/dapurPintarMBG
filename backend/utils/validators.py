import re, uuid
from typing import Optional
from backend.core.config import DIV_CANON

def canonical_division(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.strip().lower()
    parts = re.findall(r"[a-zA-Z_]+", t)
    for p in parts:
        if p in DIV_CANON:
            return DIV_CANON[p]
    return DIV_CANON.get(t)

def is_item_id(s: str) -> bool:
    return s.upper().startswith("BHN-")

def is_tray_id(s: str) -> bool:
    return s.upper().startswith("TRY-")

def new_item_id() -> str:
    return "BHN-" + uuid.uuid4().hex[:8].upper()
