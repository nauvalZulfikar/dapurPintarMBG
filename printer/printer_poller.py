"""
printer_poller.py
-----------------
Run this on the mini PC that is physically connected to the label printer.

It will:
- Poll your cloud bot (Render) every few seconds for print jobs.
- Print any job it receives on the local Windows printer.
- Notify cloud that the job has been printed.

Run:
    set CLOUD_BASE_URL=https://dapurpintarmbg.onrender.com
    set CLOUD_PRINT_KEY=supersecret-mbg-key
    set PRINTER_NAME=DPMBG_Paseh_PB830L
    python printer_poller.py
"""

import os
import time
import logging
from backend.core.database import engine, remote_print_jobs
from sqlalchemy import select, update, func

import requests

from dotenv import load_dotenv
load_dotenv()

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("printer_poller")

# --- Config from env ---
CLOUD_BASE_URL = os.getenv("DATABASE_URL")#, "https://dapurpintarmbg.onrender.com")
PRINTER_NAME = os.getenv("PRINTER_NAME")#, "DPMBGPasehZP550")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "2.0"))  # seconds
PRINTER_LANG = os.getenv("PRINTER_LANG")#, "TSPL").upper()

# --- Windows printing ---
try:
    import win32print
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    win32print = None
    logger.error("pywin32 not installed. Install with: pip install pywin32")

def send_raw_to_printer(data: str, printer_name: str):
    if not HAS_WIN32:
        raise RuntimeError("win32print not available (not on Windows or pywin32 missing).")

    # Ensure newline at end
    if not data.endswith("\n"):
        data = data + "\n"

    logger.info(f"[PRINT] Opening printer '{printer_name}'...")
    hPrinter = None
    try:
        hPrinter = win32print.OpenPrinter(printer_name)
        job = win32print.StartDocPrinter(hPrinter, 1, ("RAW PRINT JOB", None, "RAW"))
        win32print.StartPagePrinter(hPrinter)
        win32print.WritePrinter(hPrinter, data.encode("utf-8"))
        win32print.EndPagePrinter(hPrinter)
        win32print.EndDocPrinter(hPrinter)
        logger.info("[PRINT] Label sent successfully to printer")
    finally:
        if hPrinter:
            win32print.ClosePrinter(hPrinter)

def poll_once():
    with engine.begin() as conn:
        row = conn.execute(
            select(remote_print_jobs)
            .where(remote_print_jobs.c.printed == 0)
            .order_by(remote_print_jobs.c.id.asc())
            .limit(1)
        ).first()

        if not row:
            return

        job = dict(row._mapping)
        job_id = job["id"]
        tspl = job["tspl"]

        logger.info(f"Received print job id={job_id}")

        # Print
        send_raw_to_printer(tspl, PRINTER_NAME)

        # Mark printed
        conn.execute(
            update(remote_print_jobs)
            .where(remote_print_jobs.c.id == job_id)
            .values(
                printed=1,
                printed_at=func.now()
            )
        )

        logger.info(f"Marked job {job_id} as printed")
def main():
    logger.info("Starting printer poller...")
    logger.info(f"CLOUD_BASE_URL = {CLOUD_BASE_URL}")
    logger.info(f"PRINTER_NAME   = {PRINTER_NAME}")
    logger.info(f"POLL_INTERVAL  = {POLL_INTERVAL} seconds")
    logger.info(f"PRINTER_LANG  = {PRINTER_LANG}")

    while True:
        try:
            poll_once()
        except requests.exceptions.RequestException as e:
            logger.error(f"[NETWORK ERROR] {e}")
        except Exception as e:
            logger.error(f"[PRINT ERROR] {e}")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()