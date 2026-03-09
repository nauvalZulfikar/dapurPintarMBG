# backend/api/print_queue.py
from typing import List, Optional

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.services.printing import db_get_next_print_job, db_mark_print_job_printed
from backend.core.models import PrintCompletePayload
from backend.api.health import CLOUD_PRINT_KEY

router = APIRouter()

# In-memory store for registered printers (resets on server restart — enough for this use case)
_registered_printers: List[str] = []


class PrinterRegisterPayload(BaseModel):
    printers: List[str]

@router.post("/api/printer/register")
async def printer_register(
    payload: PrinterRegisterPayload,
    x_print_key: Optional[str] = Header(None, alias="X-Print-Key"),
):
    """Mini PC calls this on startup to register its available printers."""
    if CLOUD_PRINT_KEY and (not x_print_key or x_print_key != CLOUD_PRINT_KEY):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    global _registered_printers
    _registered_printers = payload.printers
    return {"ok": True, "registered": _registered_printers}


@router.get("/api/printer/list")
async def printer_list(x_print_key: Optional[str] = Header(None, alias="X-Print-Key")):
    """Returns the list of printers registered by the mini PC."""
    if CLOUD_PRINT_KEY and (not x_print_key or x_print_key != CLOUD_PRINT_KEY):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    return {"printers": _registered_printers}


@router.get("/print-queue")
async def print_queue(x_print_key: Optional[str] = Header(None, alias="X-Print-Key")):
    """Called by mini PC. Returns at most ONE pending print job."""
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
    """Mini PC calls this after successfully printing."""
    if CLOUD_PRINT_KEY and (not x_print_key or x_print_key != CLOUD_PRINT_KEY):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)

    try:
        db_mark_print_job_printed(payload.id)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)
