# DPMBG_Project\backend\services\printing.py

import requests
from typing import Optional
from backend.core.database import engine, remote_print_jobs
from sqlalchemy import select, func
import os

from dotenv import load_dotenv
load_dotenv()

def db_create_print_job(tspl: str) -> int:
    """Insert a new print job and return its ID."""
    with engine.begin() as c:
        res = c.execute(
            remote_print_jobs.insert().values(tspl=tspl, printed=0)
        )
        return res.inserted_primary_key[0]
    


def db_get_next_print_job() -> Optional[dict]:
    """Fetch the oldest unprinted job (printed=0)."""
    with engine.connect() as c:
        row = (
            c.execute(
                select(remote_print_jobs)
                .where(remote_print_jobs.c.printed == 0)
                .order_by(remote_print_jobs.c.id.asc())
                .limit(1)
            )
            .first()
        )
        return dict(row._mapping) if row else None


def db_mark_print_job_printed(job_id: int):
    """Mark a job as printed."""
    with engine.begin() as c:
        c.execute(
            remote_print_jobs.update()
            .where(remote_print_jobs.c.id == job_id)
            .values(
                printed=1,
                printed_at=func.now(),
            )
        )

# ---------- Printing (TSPL Style for 4BARCODE printers) ----------

def qr_link_for_item(item_id: str) -> str:
    return f"https://wa.me/628132258085?text={item_id}"

def generate_tspl(item_id, name, weight_g):
    return f"""
SIZE 50 mm, 21 mm
GAP 1 mm, 0 mm
SPEED 4
DENSITY 15
DIRECTION 1
CLS

BARCODE 50,40,"128",80,1,0,2,2,"{item_id}"

PRINT 1,1
"""

def generate_zpl(item_id, name, weight_g):
    return f"""
^XA
^PW400
^LL160
^FO30,30^A0N,40,40^FD{name}^FS
^FO30,80^A0N,35,35^FD{weight_g} g^FS
^FO200,20^BCN,80,Y,N,N
^FD{item_id}^FS
^XZ
"""

def generate_label(item_id, name, weight_g):
    printer_lang = os.getenv("PRINTER_LANG", "TSPL").upper()
    print("DEBUG printer_lang raw:", repr(printer_lang))
    printer_lang = printer_lang.upper()

    if printer_lang == "ZPL":
        return generate_zpl(item_id, name, weight_g)

    return generate_tspl(item_id, name, weight_g)

def save_tspl_to_file(tspl_code: str, file_path: str):
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(tspl_code)
