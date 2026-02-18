# DPMBG_Project/backend/core/config.py

import os
from dotenv import load_dotenv

# ---------- ENV ----------
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

# ---------- CORE SETTINGS ----------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
TZ_REGION = (os.getenv("TZ_REGION", "Asia/Jakarta") or "").strip()

# ---------- PRINTER SETTINGS ----------
PRINTER_AGENT_URL = (os.getenv("PRINTER_AGENT_URL", "") or "").strip()
PRINTER_TYPE = os.getenv("PRINTER_TYPE", "none")
PRINTER_ADDRESS = os.getenv("PRINTER_ADDRESS", "")
PRINTER_NAME = os.getenv("PRINTER_NAME", "4BARCODE 4B-2054TB")
LABEL_TITLE = os.getenv("LABEL_TITLE", "MBG Kitchen")

# ---------- Helpers ----------
DIV_CANON = {
    "receiving": "receiving",
    "penerimaan": "receiving",

    "processing": "processing",
    "pemrosesan": "processing",
    "proses": "processing",

    "packing": "packing",
    "pengemasan": "packing",

    "delivery": "delivery",
    "pengiriman": "delivery",

    "school_receipt": "school_receipt",
    "penerima manfaat": "school_receipt",
    "penerima": "school_receipt",
    "sekolah": "school_receipt",
}

print("[CONFIG] Loaded successfully.")
