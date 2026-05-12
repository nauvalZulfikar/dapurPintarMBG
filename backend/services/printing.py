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

# Local direct-print mode (Windows host with the printer attached).
# When the backend runs on the same box as the printer we skip the WS detour.
LOCAL_PRINT = os.getenv("LOCAL_PRINT", "").lower() in ("1", "true", "yes")
PRINTER_NAME_FALLBACK = os.getenv("PRINTER_NAME", "")

try:
    import win32print
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


# ---------- DB helpers ----------

def db_create_print_job(tspl: str, kitchen_id: Optional[int] = None) -> int:
    with engine.begin() as c:
        res = c.execute(
            remote_print_jobs.insert().values(tspl=tspl, printed=0, kitchen_id=kitchen_id)
        )
        return res.inserted_primary_key[0]


def db_get_next_print_job(kitchen_id: Optional[int] = None) -> Optional[dict]:
    with engine.connect() as c:
        q = select(remote_print_jobs).where(remote_print_jobs.c.printed == 0)
        if kitchen_id is not None:
            q = q.where(remote_print_jobs.c.kitchen_id == kitchen_id)
        row = c.execute(q.order_by(remote_print_jobs.c.id.asc()).limit(1)).first()
        return dict(row._mapping) if row else None


def db_mark_print_job_printed(job_id: int):
    with engine.begin() as c:
        c.execute(
            remote_print_jobs.update()
            .where(remote_print_jobs.c.id == job_id)
            .values(printed=1, printed_at=func.now())
        )


def _send_raw_to_printer(data: str, printer_name: Optional[str] = None):
    """Send raw ZPL/TSPL to a Windows printer. `printer_name` falls back to
    the legacy single-printer env var when not given."""
    if not HAS_WIN32:
        raise RuntimeError("win32print not available")
    target = printer_name or PRINTER_NAME_FALLBACK
    if not target:
        raise RuntimeError("No printer_name configured for this kitchen")
    if not data.endswith("\n"):
        data += "\n"
    hPrinter = None
    try:
        hPrinter = win32print.OpenPrinter(target)
        win32print.StartDocPrinter(hPrinter, 1, ("RAW JOB", None, "RAW"))
        win32print.StartPagePrinter(hPrinter)
        win32print.WritePrinter(hPrinter, data.encode("utf-8"))
        win32print.EndPagePrinter(hPrinter)
        win32print.EndDocPrinter(hPrinter)
        logger.info(f"[PRINT] Sent directly to '{target}'")
    finally:
        if hPrinter:
            win32print.ClosePrinter(hPrinter)


def _sync_to_db(tspl: str, kitchen_id: Optional[int]):
    try:
        job_id = db_create_print_job(tspl, kitchen_id=kitchen_id)
        db_mark_print_job_printed(job_id)
        logger.info(f"[PRINT] Synced job {job_id} to DB (kitchen={kitchen_id})")
    except Exception as e:
        logger.error(f"[PRINT] DB sync failed: {e}")


async def create_and_push_job(tspl: str, kitchen_id: Optional[int] = None,
                              printer_name: Optional[str] = None) -> int:
    """
    LOCAL_PRINT=true  → print via win32print to `printer_name` (per-kitchen), sync DB async.
    LOCAL_PRINT=false → insert job with kitchen_id, push via WS to the agent bound to that kitchen.
    """
    if LOCAL_PRINT and HAS_WIN32:
        try:
            _send_raw_to_printer(tspl, printer_name=printer_name)
        except Exception as e:
            logger.error(f"[PRINT] Direct print failed: {e}")
        threading.Thread(target=_sync_to_db, args=(tspl, kitchen_id), daemon=True).start()
        return -1

    from backend.api.print_queue import push_job_to_agent

    job_id = db_create_print_job(tspl, kitchen_id=kitchen_id)
    pushed = await push_job_to_agent(job_id, tspl, kitchen_id=kitchen_id)
    if pushed:
        logger.info(f"[PRINT] Job {job_id} pushed via WebSocket to kitchen={kitchen_id}")
    else:
        logger.info(f"[PRINT] Job {job_id} queued for polling (kitchen={kitchen_id}, agent offline)")
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


def generate_label(item_id, name, weight_g, kitchen: Optional[dict] = None):
    """Pick the label dialect based on the kitchen's printer_lang column,
    falling back to PRINTER_LANG env for the legacy single-kitchen setup."""
    lang = None
    if kitchen:
        lang = (kitchen.get("printer_lang") or "").upper() or None
    if not lang:
        lang = os.getenv("PRINTER_LANG", "TSPL").upper()

    if lang == "ZPL":
        return generate_zpl(item_id, name, weight_g)
    return generate_tspl(item_id, name, weight_g)
