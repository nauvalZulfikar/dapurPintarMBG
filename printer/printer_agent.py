"""
printer_agent.py
----------------
Connects to the backend via WebSocket for instant print jobs.
Falls back to HTTP polling when WebSocket is unavailable.

Run:  python printer_agent.py   (from project root)
"""

import os
import time
import logging
import threading
import json

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("printer_agent")

API_BASE_URL    = os.getenv("API_BASE_URL", "http://localhost:8000")
CLOUD_PRINT_KEY = os.getenv("CLOUD_PRINT_KEY", "")
PRINTER_NAME    = os.getenv("PRINTER_NAME", "")
POLL_INTERVAL   = float(os.getenv("POLL_INTERVAL", "3.0"))
HTTP_TIMEOUT    = 35

try:
    import win32print
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    logger.error("pywin32 not installed — cannot print")

try:
    import websocket  # websocket-client
    HAS_WS = True
except ImportError:
    HAS_WS = False
    logger.warning("websocket-client not installed — falling back to polling only")


# ---------- Print ----------

def send_raw_to_printer(data: str):
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
        logger.info(f"[PRINT] Sent to '{PRINTER_NAME}'")
    finally:
        if hPrinter:
            win32print.ClosePrinter(hPrinter)


# ---------- WebSocket mode ----------

def _ws_url():
    base = API_BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
    return f"{base}/ws/printer?key={CLOUD_PRINT_KEY}"


def on_ws_message(ws, message):
    try:
        job = json.loads(message)
        job_id = job.get("id")
        tspl = job.get("tspl", "")
        logger.info(f"[WS] Received job id={job_id}")
        send_raw_to_printer(tspl)
        ws.send(json.dumps({"id": job_id, "ok": True}))
        logger.info(f"[WS] Ack sent for job {job_id}")
    except Exception as e:
        logger.error(f"[WS] Error processing job: {e}")


def on_ws_error(ws, error):
    logger.error(f"[WS] Error: {error}")


def on_ws_close(ws, close_status_code, close_msg):
    logger.info(f"[WS] Disconnected ({close_status_code})")


def on_ws_open(ws):
    logger.info("[WS] Connected to backend")
    _register_printers()


def run_ws():
    """Run WebSocket with auto-reconnect."""
    while True:
        try:
            ws = websocket.WebSocketApp(
                _ws_url(),
                on_open=on_ws_open,
                on_message=on_ws_message,
                on_error=on_ws_error,
                on_close=on_ws_close,
            )
            ws.run_forever(ping_interval=30, ping_timeout=10, reconnect=5)
        except Exception as e:
            logger.error(f"[WS] Fatal: {e}")
        logger.info("[WS] Reconnecting in 5s...")
        time.sleep(5)


# ---------- HTTP polling fallback ----------

def poll_once():
    headers = {}
    if CLOUD_PRINT_KEY:
        headers["X-Print-Key"] = CLOUD_PRINT_KEY
    resp = requests.get(
        f"{API_BASE_URL}/print-queue",
        headers=headers,
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    jobs = resp.json().get("jobs", [])
    if not jobs:
        return
    job = jobs[0]
    job_id, tspl = job["id"], job["tspl"]
    logger.info(f"[POLL] Received job id={job_id}")
    send_raw_to_printer(tspl)
    requests.post(
        f"{API_BASE_URL}/print-complete",
        json={"id": job_id},
        headers=headers,
        timeout=HTTP_TIMEOUT,
    ).raise_for_status()
    logger.info(f"[POLL] Job {job_id} done")


def run_polling():
    """HTTP polling loop — runs as fallback alongside WS."""
    while True:
        try:
            poll_once()
        except requests.exceptions.RequestException as e:
            logger.error(f"[POLL] Network: {e}")
        except Exception as e:
            logger.error(f"[POLL] Error: {e}")
        time.sleep(POLL_INTERVAL)


# ---------- Register printers ----------

def _register_printers():
    if not HAS_WIN32:
        return
    try:
        printers = [p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )]
        headers = {"X-Print-Key": CLOUD_PRINT_KEY} if CLOUD_PRINT_KEY else {}
        requests.post(
            f"{API_BASE_URL}/api/printer/register",
            json={"printers": printers},
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
        logger.info(f"Registered {len(printers)} printer(s): {printers}")
    except Exception as e:
        logger.warning(f"Could not register printers: {e}")


# ---------- Main ----------

def main():
    logger.info("=== Printer Agent Starting ===")
    logger.info(f"API_BASE_URL  = {API_BASE_URL}")
    logger.info(f"PRINTER_NAME  = {PRINTER_NAME}")
    logger.info(f"POLL_INTERVAL = {POLL_INTERVAL}s (fallback polling)")

    _register_printers()

    if HAS_WS:
        # WS in background thread, polling as safety net
        ws_thread = threading.Thread(target=run_ws, daemon=True)
        ws_thread.start()
        logger.info("[WS] WebSocket thread started — instant print active")
    else:
        logger.info("[POLL] WebSocket unavailable — polling only")

    # Polling loop runs in main thread as fallback
    run_polling()


if __name__ == "__main__":
    main()
