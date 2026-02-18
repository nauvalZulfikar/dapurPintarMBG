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
from typing import Optional

import requests

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("printer_poller")

# --- Config from env ---
CLOUD_BASE_URL = os.getenv("CLOUD_BASE_URL", "https://dapurpintarmbg.onrender.com")
CLOUD_PRINT_KEY = os.getenv("CLOUD_PRINT_KEY", "")    # must match Render
PRINTER_NAME = os.getenv("PRINTER_NAME", "DPMBG_Paseh_PB830L")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "2.0"))  # seconds

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
        job = win32print.StartDocPrinter(hPrinter, 1, ("RAW TSPL Job", None, "RAW"))
        win32print.StartPagePrinter(hPrinter)
        win32print.WritePrinter(hPrinter, data.encode("utf-8"))
        win32print.EndPagePrinter(hPrinter)
        win32print.EndDocPrinter(hPrinter)
        logger.info("[PRINT] Label sent successfully to printer")
    finally:
        if hPrinter:
            win32print.ClosePrinter(hPrinter)


def poll_once():
    """One poll cycle: fetch job, print if exists, ack."""
    headers = {}
    if CLOUD_PRINT_KEY:
        headers["X-Print-Key"] = CLOUD_PRINT_KEY

    # 1. Ask cloud for a job
    url = f"{CLOUD_BASE_URL.rstrip('/')}/print-queue"
    logger.debug(f"Polling {url}")
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    jobs = data.get("jobs", [])
    if not jobs:
        logger.debug("No pending jobs.")
        return

    job = jobs[0]
    job_id = job["id"]
    tspl = job["tspl"]

    logger.info(f"Received print job id={job_id}")

    # 2. Print locally
    send_raw_to_printer(tspl, PRINTER_NAME)

    # 3. Notify cloud
    url_done = f"{CLOUD_BASE_URL.rstrip('/')}/print-complete"
    done_payload = {"id": job_id}
    resp2 = requests.post(url_done, headers=headers, json=done_payload, timeout=10)
    resp2.raise_for_status()
    logger.info(f"Acked print-complete for job id={job_id}")


def main():
    logger.info("Starting printer poller...")
    logger.info(f"CLOUD_BASE_URL = {CLOUD_BASE_URL}")
    logger.info(f"PRINTER_NAME   = {PRINTER_NAME}")
    logger.info(f"POLL_INTERVAL  = {POLL_INTERVAL} seconds")

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