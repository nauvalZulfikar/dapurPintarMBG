# backend/api/print_queue.py
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.services.printing import db_get_next_print_job, db_mark_print_job_printed
from backend.core.models import PrintCompletePayload
from backend.api.health import CLOUD_PRINT_KEY as LEGACY_CLOUD_PRINT_KEY
from backend.core.database import db_get_kitchen_by_print_key, db_get_kitchen

logger = logging.getLogger(__name__)
router = APIRouter()

# One active printer WebSocket per kitchen.
_printer_ws: Dict[int, WebSocket] = {}

# Printers registered per kitchen (human-readable list for the admin UI).
_registered_printers: Dict[int, List[str]] = {}


def _resolve_print_kitchen(key: Optional[str]) -> Optional[dict]:
    """Resolve a printer auth key to its kitchen."""
    if not key:
        return None
    kitchen = db_get_kitchen_by_print_key(key)
    if kitchen:
        return kitchen
    if LEGACY_CLOUD_PRINT_KEY and key == LEGACY_CLOUD_PRINT_KEY:
        return db_get_kitchen(1)
    return None


async def push_job_to_agent(job_id: int, tspl: str, kitchen_id: Optional[int] = None) -> bool:
    """Push a job to the connected agent for a given kitchen.
    Returns True on successful delivery, False if no agent is connected."""
    if kitchen_id is None:
        # Broadcast-to-legacy fallback: deliver to whichever single agent is connected.
        if not _printer_ws:
            return False
        kitchen_id = next(iter(_printer_ws.keys()))

    ws = _printer_ws.get(kitchen_id)
    if ws is None:
        return False
    try:
        await ws.send_json({"id": job_id, "tspl": tspl, "kitchen_id": kitchen_id})
        return True
    except Exception as e:
        logger.warning(f"[WS] Failed to push job {job_id} to kitchen {kitchen_id}: {e}")
        _printer_ws.pop(kitchen_id, None)
        return False


class PrinterRegisterPayload(BaseModel):
    printers: List[str]


@router.websocket("/ws/printer")
async def printer_ws_endpoint(websocket: WebSocket):
    """Printer agent connects here with its kitchen's CLOUD_PRINT_KEY."""
    key = websocket.query_params.get("key", "")
    kitchen = _resolve_print_kitchen(key)
    if not kitchen:
        await websocket.close(code=4003)
        return
    kid = kitchen["id"]

    await websocket.accept()
    # If a previous connection is open for this kitchen, evict it — only one
    # agent per kitchen.
    previous = _printer_ws.get(kid)
    if previous is not None:
        try:
            await previous.close(code=4000)
        except Exception:
            pass
    _printer_ws[kid] = websocket
    logger.info(f"[WS] Printer agent connected for kitchen={kid} ({kitchen['slug']})")

    try:
        while True:
            data = await websocket.receive_json()
            job_id = data.get("id")
            ok = data.get("ok", False)
            if job_id and ok:
                try:
                    db_mark_print_job_printed(job_id)
                    logger.info(f"[WS] Job {job_id} marked printed via WS ack (kitchen={kid})")
                except Exception as e:
                    logger.error(f"[WS] Failed to mark job {job_id}: {e}")
    except WebSocketDisconnect:
        logger.info(f"[WS] Printer agent disconnected for kitchen={kid}")
    except Exception as e:
        logger.error(f"[WS] Unexpected error: {e}")
    finally:
        if _printer_ws.get(kid) is websocket:
            _printer_ws.pop(kid, None)


@router.get("/ws/printer/status")
async def printer_ws_status(x_print_key: Optional[str] = Header(None, alias="X-Print-Key")):
    """Report whether a printer agent is connected for the caller's kitchen."""
    kitchen = _resolve_print_kitchen(x_print_key)
    if not kitchen:
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    connected = _printer_ws.get(kitchen["id"]) is not None
    return {"connected": connected, "kitchen_id": kitchen["id"]}


@router.post("/api/printer/register")
async def printer_register(
    payload: PrinterRegisterPayload,
    x_print_key: Optional[str] = Header(None, alias="X-Print-Key"),
):
    kitchen = _resolve_print_kitchen(x_print_key)
    if not kitchen:
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    _registered_printers[kitchen["id"]] = payload.printers
    return {"ok": True, "kitchen_id": kitchen["id"], "registered": payload.printers}


@router.get("/api/printer/list")
async def printer_list(x_print_key: Optional[str] = Header(None, alias="X-Print-Key")):
    kitchen = _resolve_print_kitchen(x_print_key)
    if not kitchen:
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    return {"kitchen_id": kitchen["id"], "printers": _registered_printers.get(kitchen["id"], [])}


@router.get("/print-queue")
async def print_queue(x_print_key: Optional[str] = Header(None, alias="X-Print-Key")):
    """Polling fallback: returns the next job for the caller's kitchen only."""
    kitchen = _resolve_print_kitchen(x_print_key)
    if not kitchen:
        return JSONResponse({"detail": "Forbidden"}, status_code=403)

    job = db_get_next_print_job(kitchen_id=kitchen["id"])
    if not job:
        return {"jobs": []}
    return {"jobs": [{"id": job["id"], "tspl": job["tspl"]}], "kitchen_id": kitchen["id"]}


@router.post("/print-complete")
async def print_complete(
    payload: PrintCompletePayload,
    x_print_key: Optional[str] = Header(None, alias="X-Print-Key"),
):
    kitchen = _resolve_print_kitchen(x_print_key)
    if not kitchen:
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    try:
        db_mark_print_job_printed(payload.id)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)
