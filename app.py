# printer_agent.py
from fastapi import FastAPI
import win32print
import win32api

app = FastAPI()

PRINTER_NAME = "DPMBG Pasehh PB830L"  # Or whatever appears in Get-Printer

def send_raw_to_printer(data):
    h = win32print.OpenPrinter(PRINTER_NAME)
    job = win32print.StartDocPrinter(h, 1, ("RAW Job", None, "RAW"))
    win32print.StartPagePrinter(h)
    win32print.WritePrinter(h, data.encode("utf-8"))
    win32print.EndPagePrinter(h)
    win32print.EndDocPrinter(h)
    win32print.ClosePrinter(h)

@app.post("/print")
async def print_label(payload: dict):
    tspl = payload.get("tspl", "")
    if not tspl:
        return {"ok": False, "error": "no TSPL provided"}

    try:
        send_raw_to_printer(tspl)
        return {"ok": True, "message": "Printed successfully"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
