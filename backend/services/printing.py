# backend/services/printing.py

import os
import logging
from typing import Optional
from sqlalchemy import select, func
from dotenv import load_dotenv

from backend.core.database import engine, remote_print_jobs

load_dotenv()
logger = logging.getLogger(__name__)


# ---------- DB helpers ----------

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
        row = c.execute(
            select(remote_print_jobs)
            .where(remote_print_jobs.c.printed == 0)
            .order_by(remote_print_jobs.c.id.asc())
            .limit(1)
        ).first()
        return dict(row._mapping) if row else None


def db_mark_print_job_printed(job_id: int):
    """Mark a job as printed."""
    with engine.begin() as c:
        c.execute(
            remote_print_jobs.update()
            .where(remote_print_jobs.c.id == job_id)
            .values(printed=1, printed_at=func.now())
        )


async def create_and_push_job(tspl: str) -> int:
    """
    Save job to DB, then instantly push to WS agent if connected.
    Falls back to polling automatically (poller picks up printed=0 jobs).
    Returns job_id.
    """
    from backend.api.print_queue import push_job_to_agent

    job_id = db_create_print_job(tspl)
    pushed = await push_job_to_agent(job_id, tspl)
    if pushed:
        logger.info(f"[PRINT] Job {job_id} pushed via WebSocket")
    else:
        logger.info(f"[PRINT] Job {job_id} queued for polling (agent offline)")
    return job_id


# ---------- Label generation ----------

def generate_tspl(item_id, name, weight_g):
    return f"""SIZE 50 mm, 21 mm
GAP 1 mm, 0 mm
SPEED 4
DENSITY 15
DIRECTION 1
CLS
BARCODE 50,40,"128",80,1,0,2,2,"{item_id}"
PRINT 1,1
"""


def generate_zpl(item_id, name, weight_g):
    return (
        f"^XA"
        f"^PON^LT0^PW400^LL168^CI28"
        f"^BY2,2,60"
        f"^FO30,20^BCN,60,Y,N,N^FD{item_id}^FS"
        f"^XZ"
    )


def generate_label(item_id, name, weight_g):
    printer_lang = os.getenv("PRINTER_LANG", "TSPL").upper()
    if printer_lang == "ZPL":
        return generate_zpl(item_id, name, weight_g)
    return generate_tspl(item_id, name, weight_g)
