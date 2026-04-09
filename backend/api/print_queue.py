# backend/api/print_queue.py
import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.services.printing import db_get_next_print_job, db_mark_print_job_printed
from backend.core.models import PrintCompletePayload
from backend.api.health import CLOUD_PRINT_KEY

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory store for registered printers
_registered_printers: List[str] = []

# Active WebSocket printer agent connection
_printer_ws: Optional[WebSocket] = None


async def push_job_to_agent(job_id: int, tspl: str) -> bool:
    """Push a print job to the connected agent. Returns True if delivered."""
    global _printer_ws
    if _printer_ws is None:
        return False
    try:
        await _printer_ws.send_json({"id": job_id, "tspl": tspl})
        return True
    except Exception as e:
        logger.warning(f"[WS] Failed to push job {job_id}: {e}")
        _printer_ws = None
        return False


class PrinterRegisterPayload(BaseModel):
    printers: List[str]


@router.websocket("/ws/printer")
async def printer_ws_endpoint(websocket: WebSocket):
    """Printer agent connects here to receive jobs instantly."""
    global _printer_ws

    # Authenticate via query param
    key = websocket.query_params.get("key", "")
    if CLOUD_PRINT_KEY and key != CLOUD_PRINT_KEY:
        await websocket.close(code=4003)
        return

    await websocket.accept()
    _printer_ws = websocket
    logger.info("[WS] Printer agent connected")

    try:
        while True:
            # Agent sends ack: {"id": job_id, "ok": true}
            data = await websocket.receive_json()
            job_id = data.get("id")
            ok = data.get("ok", False)
            if job_id and ok:
                try:
                    db_mark_print_job_printed(job_id)
                    logger.info(f"[WS] Job {job_id} marked printed via WS ack")
                except Exception as e:
                    logger.error(f"[WS] Failed to mark job {job_id}: {e}")
    except WebSocketDisconnect:
        logger.info("[WS] Printer agent disconnected")
        _printer_ws = None
    except Exception as e:
        logger.error(f"[WS] Unexpected error: {e}")
        _printer_ws = None


@router.get("/ws/printer/status")
async def printer_ws_status():
    """Check if printer agent is connected."""
    return {"connected": _printer_ws is not None}


@router.post("/api/printer/register")
async def printer_register(
    payload: PrinterRegisterPayload,
    x_print_key: Optional[str] = Header(None, alias="X-Print-Key"),
):
    if CLOUD_PRINT_KEY and (not x_print_key or x_print_key != CLOUD_PRINT_KEY):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    global _registered_printers
    _registered_printers = payload.printers
    return {"ok": True, "registered": _registered_printers}


@router.get("/api/printer/list")
async def printer_list(x_print_key: Optional[str] = Header(None, alias="X-Print-Key")):
    if CLOUD_PRINT_KEY and (not x_print_key or x_print_key != CLOUD_PRINT_KEY):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    return {"printers": _registered_printers}


@router.get("/print-queue")
async def print_queue(x_print_key: Optional[str] = Header(None, alias="X-Print-Key")):
    """Fallback polling endpoint for when WS agent is offline."""
    if CLOUD_PRINT_KEY and (not x_print_key or x_print_key != CLOUD_PRINT_KEY):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)

    job = db_get_next_print_job()
    if not job:
        return {"jobs": []}

    return {"jobs": [{"id": job["id"], "tspl": job["tspl"]}]}


@router.post("/print-complete")
async def print_complete(
    payload: PrintCompletePayload,
    x_print_key: Optional[str] = Header(None, alias="X-Print-Key"),
):
    if CLOUD_PRINT_KEY and (not x_print_key or x_print_key != CLOUD_PRINT_KEY):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    try:
        db_mark_print_job_printed(payload.id)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)
