"""
printer_poller.py
-----------------
Run this on the mini PC that is physically connected to the label printer.

It will:
- Poll the FastAPI /print-queue endpoint every few seconds for print jobs.
- Print any job it receives on the local Windows printer.
- Notify the API via /print-complete that the job has been printed.

Env vars:
    API_BASE_URL   = https://your-server.com
    CLOUD_PRINT_KEY = your-print-api-key
    PRINTER_NAME    = DPMBGPasehZP550
    POLL_INTERVAL   = 2.0
"""

import os
import time
import logging

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
API_BASE_URL    = os.getenv("API_BASE_URL", "http://localhost:8000")
CLOUD_PRINT_KEY = os.getenv("CLOUD_PRINT_KEY", "")
PRINTER_NAME    = os.getenv("PRINTER_NAME", "DPMBGPasehZP550")
POLL_INTERVAL   = float(os.getenv("POLL_INTERVAL", "2.0"))
PRINTER_LANG    = os.getenv("PRINTER_LANG", "TSPL").upper()
HTTP_TIMEOUT    = 10

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
    """Fetch one print job from API and print it."""
    headers = {}
    if CLOUD_PRINT_KEY:
        headers["X-Print-Key"] = CLOUD_PRINT_KEY

    resp = requests.get(
        f"{API_BASE_URL}/print-queue",
        headers=headers,
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    jobs = data.get("jobs", [])
    if not jobs:
        return

    job = jobs[0]
    job_id = job["id"]
    tspl = job["tspl"]

    logger.info(f"Received print job id={job_id}")

    # Print to local printer
    send_raw_to_printer(tspl, PRINTER_NAME)

    # Mark as printed via API
    resp = requests.post(
        f"{API_BASE_URL}/print-complete",
        json={"id": job_id},
        headers=headers,
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()

    logger.info(f"Marked job {job_id} as printed")


def main():
    logger.info("Starting printer poller...")
    logger.info(f"API_BASE_URL   = {API_BASE_URL}")
    logger.info(f"PRINTER_NAME   = {PRINTER_NAME}")
    logger.info(f"POLL_INTERVAL  = {POLL_INTERVAL} seconds")
    logger.info(f"PRINTER_LANG   = {PRINTER_LANG}")

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
