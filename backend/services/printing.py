# backend/services/printing.py

import os
import logging
import threading
from typing import Optional
from sqlalchemy import select, func
from dotenv import load_dotenv

from backend.core.database import engine, remote_print_jobs

load_dotenv()
logger = logging.getLogger(__name__)

LOCAL_PRINT = os.getenv("LOCAL_PRINT", "").lower() in ("1", "true", "yes")
PRINTER_NAME = os.getenv("PRINTER_NAME", "")

try:
    import win32print
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


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


def _send_raw_to_printer(data: str):
    """Send raw ZPL/TSPL directly to the local printer via win32print."""
    if not HAS_WIN32:
        raise RuntimeError("win32print not available")
    if not data.endswith("\n"):
        data += "\n"
    hPrinter = None
    try:
        hPrinter = win32print.OpenPrinter(PRINTER_NAME)
        job = win32print.StartDocPrinter(hPrinter, 1, ("RAW JOB", None, "RAW"))
        win32print.StartPagePrinter(hPrinter)
        win32print.WritePrinter(hPrinter, data.encode("utf-8"))
        win32print.EndPagePrinter(hPrinter)
        win32print.EndDocPrinter(hPrinter)
        logger.info(f"[PRINT] Sent directly to '{PRINTER_NAME}'")
    finally:
        if hPrinter:
            win32print.ClosePrinter(hPrinter)


def _sync_to_db(tspl: str):
    """Write print job to Supabase in background (fire-and-forget)."""
    try:
        job_id = db_create_print_job(tspl)
        db_mark_print_job_printed(job_id)
        logger.info(f"[PRINT] Synced job {job_id} to DB")
    except Exception as e:
        logger.error(f"[PRINT] DB sync failed: {e}")


async def create_and_push_job(tspl: str) -> int:
    """
    LOCAL_PRINT=true  → print immediately via win32print, sync DB in background thread.
    LOCAL_PRINT=false → save job to DB, push via WS to agent (polling fallback).
    Returns job_id (or -1 if local mode).
    """
    if LOCAL_PRINT and HAS_WIN32:
        # Print instantly, sync to DB without blocking
        try:
            _send_raw_to_printer(tspl)
        except Exception as e:
            logger.error(f"[PRINT] Direct print failed: {e}")
        threading.Thread(target=_sync_to_db, args=(tspl,), daemon=True).start()
        return -1

    # Cloud mode: save to DB then push via WS
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
