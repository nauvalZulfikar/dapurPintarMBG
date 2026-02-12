# DPMBG_Project\backend\core\config.py

import os
from dotenv import load_dotenv

# ---------- ENV ----------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))#, ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

TOKEN     = (os.getenv("WHATSAPP_TOKEN", "") or "").strip()
PHONE_ID  = (os.getenv("WABA_PHONE_ID", os.getenv("WHATSAPP_PHONE_ID", "")) or "").strip()
VERIFY    = (os.getenv("WHATSAPP_VERIFY_TOKEN", os.getenv("VERIFY_TOKEN", "verify_me")) or "").strip()
GRAPH     = (os.getenv("GRAPH_BASE", "https://graph.facebook.com/v20.0") or "").strip()
TZ_REGION = (os.getenv("TZ_REGION", "Asia/Jakarta") or "").strip()
PRINTER_AGENT_URL = (os.getenv("PRINTER_AGENT_URL", "") or "").strip()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    print("[WARN] OPENAI_API_KEY missing. This file requires it for agent control.")

PRINTER_TYPE    = os.getenv("PRINTER_TYPE", "none")  # not used for now, kept for future
PRINTER_ADDRESS = os.getenv("PRINTER_ADDRESS", "")   # not used for now, kept for future
LABEL_TITLE     = os.getenv("LABEL_TITLE", "MBG Kitchen")
PRINTER_NAME    = os.getenv("PRINTER_NAME", "4BARCODE 4B-2054TB")  # Windows printer name

# ---------- Helpers ----------
DIV_CANON = {
    "receiving": "receiving", "penerimaan": "receiving",
    "processing": "processing", "pemrosesan": "processing", "proses": "processing",
    "packing": "packing", "pengemasan": "packing",
    "delivery": "delivery", "pengiriman": "delivery",
    "school_receipt": "school_receipt", "penerima manfaat": "school_receipt",
    "penerima": "school_receipt", "sekolah": "school_receipt",
}

print("[CONFIG] VERIFY repr =", repr(VERIFY))
