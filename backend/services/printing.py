import requests
from typing import Optional
from backend.core.config import PRINTER_AGENT_URL
from backend.core.database import engine, print_jobs
from sqlalchemy import select, func

def db_create_print_job(tspl: str) -> int:
    """Insert a new print job and return its ID."""
    with engine.begin() as c:
        res = c.execute(
            print_jobs.insert().values(tspl=tspl, printed=0)
        )
        return res.inserted_primary_key[0]


def db_get_next_print_job() -> Optional[dict]:
    """Fetch the oldest unprinted job (printed=0)."""
    with engine.connect() as c:
        row = (
            c.execute(
                select(print_jobs)
                .where(print_jobs.c.printed == 0)
                .order_by(print_jobs.c.id.asc())
                .limit(1)
            )
            .first()
        )
        return dict(row._mapping) if row else None


def db_mark_print_job_printed(job_id: int):
    """Mark a job as printed."""
    with engine.begin() as c:
        c.execute(
            print_jobs.update()
            .where(print_jobs.c.id == job_id)
            .values(
                printed=1,
                printed_at=func.now(),
            )
        )

# ---------- Printing (TSPL Style for 4BARCODE printers) ----------

def qr_link_for_item(item_id: str) -> str:
    return f"https://wa.me/628132258085?text={item_id}"

# new
def tspl_label(item_id: str, name: str, weight_g: int) -> str:
    qr = qr_link_for_item(item_id)

    return f"""
SIZE 50 mm, 21 mm
GAP 1 mm, 0 mm
SPEED 4
DENSITY 15
DIRECTION 1
CLS

; ---- TEXT AREA ----
TEXT 15,80,"0",0,10,10,"{name}"
TEXT 15,110,"0",0,10,10,"{weight_g} g"

; ---- QR CODE (small, fits 25mm height) ----
QRCODE 230,51,L,4,A,0,"{qr}"

# ; ---- Item ID under QR ----
# TEXT 230,80,"0",0,6,6,"{item_id}"

PRINT 1,1
"""

def save_tspl_to_file(tspl_code: str, file_path: str):
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(tspl_code)

def send_to_print_agent(tspl_code: str):
    try:
        payload = {
            "tspl": tspl_code,
            "test": False
        }
        r = requests.post(f"{PRINTER_AGENT_URL}/print", json=payload, timeout=8)
        r.raise_for_status()
        print("[PRINT] sent to mini pc SUCCESS")
    except Exception as e:
        print("[PRINT ERROR]", e)
