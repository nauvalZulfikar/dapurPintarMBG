import os, json
from datetime import datetime
from fastapi import APIRouter, Header
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from backend.core.database import (
    db_insert_tray_if_needed,
    db_insert_event,
    db_last_event,
)

router = APIRouter()

# Map device tokens -> division (DB uses english keys)
TOKENS = {
    os.getenv("SCAN_DEVICE_PROCESSING_TOKEN", ""): "processing",
    os.getenv("SCAN_DEVICE_PACKING_TOKEN", ""): "packing",
    os.getenv("SCAN_DEVICE_DELIVERY_TOKEN", ""): "delivery",
}
TOKENS = {k: v for k, v in TOKENS.items() if k}

# Hard-coded chain to reduce mistakes
PREV_REQUIRED = {
    "processing": None,          # can start here (or later you can require "receiving")
    "packing": "processing",
    "delivery": "packing",
}

class ScanIn(BaseModel):
    code: str
    ts_client: str | None = None

def _now_iso():
    return datetime.now().isoformat(timespec="seconds")

def _dedupe(tray_id: str, division: str, seconds: int = 2) -> bool:
    last = db_last_event("tray", tray_id)
    if not last:
        return False
    if last.get("division") != division:
        return False
    try:
        t_last = datetime.fromisoformat(last["ts_local"])
        t_now = datetime.fromisoformat(_now_iso())
        return (t_now - t_last).total_seconds() <= seconds
    except Exception:
        return False

def _validate_chain(tray_id: str, division: str):
    required = PREV_REQUIRED.get(division)
    if required is None:
        return True, "OK"
    last = db_last_event("tray", tray_id)
    if not last:
        return False, f"Urutan salah: harus '{required}' dulu."
    if last.get("division") != required:
        return False, f"Urutan salah: terakhir '{last.get('division')}', harus '{required}' sebelum '{division}'."
    return True, "OK"

@router.post("/api/scan")
def api_scan(payload: ScanIn, x_device_token: str = Header(default="")):
    division = TOKENS.get(x_device_token)
    if not division:
        return JSONResponse({"ok": False, "message": "Unauthorized device"}, status_code=401)

    code = (payload.code or "").strip()
    if not code:
        return JSONResponse({"ok": False, "message": "Empty code"}, status_code=400)

    tray_id = code  # your tray QR should be TRY-xxxxx etc.

    # Dedupe double scan / retries
    if _dedupe(tray_id, division):
        return {"ok": True, "message": "✅ Duplicate ignored", "division": division, "tray_id": tray_id}

    ok, msg = _validate_chain(tray_id, division)
    if not ok:
        return JSONResponse({"ok": False, "message": msg}, status_code=409)

    db_insert_tray_if_needed(tray_id)
    ts_local = _now_iso()

    db_insert_event(
        ts_local=ts_local,
        phone="DEVICE",                 # you currently store phone here; keep non-null
        division=division,
        subject_type="tray",
        subject_id=tray_id,
        message_text=code,
        duration_hms="00:00:00",
        duration_sec=0,
        extra={"source": "android_scanner", "ts_client": payload.ts_client},
    )

    return {"ok": True, "message": "✅ Success", "division": division, "tray_id": tray_id, "ts_local": ts_local}


def _page(title: str, token: str) -> str:
    # No storage. Shows only last scan info.
    # Scanner must send ENTER suffix.
    return f"""<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{ font-family: Arial; padding: 16px; }}
    h2 {{ margin: 0 0 12px; }}
    .big {{ font-size: 22px; margin: 10px 0; }}
    .ok {{ color: green; font-weight: 700; }}
    .bad {{ color: red; font-weight: 700; }}
    input {{ position: absolute; left: -9999px; }}
  </style>
</head>
<body>
  <h2>{title}</h2>
  <div class="big">Barcode: <span id="barcode">-</span></div>
  <div class="big">Time: <span id="time">-</span></div>
  <div class="big">Latency: <span id="latency">-</span> ms</div>
  <div class="big">Status: <span id="status">Waiting...</span></div>

  <input id="scanInput" autocomplete="off" />

  <script>
    const DEVICE_TOKEN = "{token}";
    const input = document.getElementById("scanInput");
    const elBarcode = document.getElementById("barcode");
    const elLatency = document.getElementById("latency");
    const elStatus  = document.getElementById("status");
    const elTime    = document.getElementById("time");

    function focusInput() {{ input.focus(); }}
    setInterval(focusInput, 400);

    function nowStr() {{
      const d = new Date();
      return d.toLocaleTimeString();
    }}

    async function submit(code) {{
      elBarcode.textContent = code;
      elTime.textContent = nowStr();
      elStatus.textContent = "Sending...";
      elStatus.className = "";

      const t0 = performance.now();
      try {{
        const res = await fetch("/api/scan", {{
          method: "POST",
          headers: {{
            "Content-Type": "application/json",
            "X-DEVICE-TOKEN": DEVICE_TOKEN,
          }},
          body: JSON.stringify({{
            code,
            ts_client: new Date().toISOString()
          }})
        }});

        const t1 = performance.now();
        elLatency.textContent = Math.round(t1 - t0);

        const data = await res.json().catch(() => ({{}}));
        if (!res.ok || data.ok === false) {{
          elStatus.textContent = data.message || ("Failed HTTP " + res.status);
          elStatus.className = "bad";
          return;
        }}
        elStatus.textContent = data.message || "✅ Success";
        elStatus.className = "ok";
      }} catch (e) {{
        const t1 = performance.now();
        elLatency.textContent = Math.round(t1 - t0);
        elStatus.textContent = "❌ Network error";
        elStatus.className = "bad";
      }}
    }}

    let buffer = "";
    input.addEventListener("keydown", (e) => {{
      if (e.key === "Enter") {{
        const code = buffer.trim();
        buffer = "";
        input.value = "";
        if (code) submit(code);
        e.preventDefault();
        return;
      }}
      if (e.key.length === 1) buffer += e.key;
    }});

    window.addEventListener("click", focusInput);
    focusInput();
  </script>
</body>
</html>"""

@router.get("/scan/processing", response_class=HTMLResponse)
def ui_processing():
    return _page("PEMROSESAN SCAN", os.getenv("SCAN_DEVICE_PROCESSING_TOKEN", ""))

@router.get("/scan/packing", response_class=HTMLResponse)
def ui_packing():
    return _page("PACKING SCAN", os.getenv("SCAN_DEVICE_PACKING_TOKEN", ""))

@router.get("/scan/delivery", response_class=HTMLResponse)
def ui_delivery():
    return _page("DELIVERY SCAN", os.getenv("SCAN_DEVICE_DELIVERY_TOKEN", ""))
