# DPMBG_Project\backend\api\health.py

from fastapi import Request, Query, Header
from backend.core.database import BASE_DIR, DATABASE_URL
from backend.core.config import VERIFY, GRAPH, PHONE_ID, OPENAI_API_KEY
from typing import Optional
from fastapi.responses import JSONResponse, PlainTextResponse
from backend.services.printing import db_get_next_print_job, db_mark_print_job_printed
from backend.core.models import PrintCompletePayload
from backend.services.agent import _jsonable
from backend.core.database import mark_inbound_seen
from backend.utils.datetime_helpers import now_local_iso
from backend.services.agent import run_agent
from backend.services.whatsapp import wa_send_text
from backend.app import app
import json
import os

@app.get("/")
def root():
    return {"status": "ok"}

SCHOOLS_JSON_PATH = os.getenv("SCHOOLS_JSON_PATH", os.path.join(BASE_DIR, "schools.json"))

@app.get("/kaithhealth")
async def health_main():
    return {"status": "ok"}

@app.get("/kaithhealthcheck")
@app.get("/kaithheathcheck")   # typo that appears in logs
@app.get("/health")
@app.get("/healthz")
async def health_variants():
    return {"status": "ok"}

CLOUD_PRINT_KEY = os.getenv("CLOUD_PRINT_KEY", "")

def _check_print_key(x_print_key: Optional[str]):
    if CLOUD_PRINT_KEY:
        if not x_print_key or x_print_key != CLOUD_PRINT_KEY:
            raise JSONResponse(
                status_code=403,
                content={"detail": "Invalid print key"},
            )

# ---------- Debug ----------
@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return f"OK GRAPH={GRAPH} PHONE_ID={PHONE_ID} DB={DATABASE_URL} OPENAI={'yes' if OPENAI_API_KEY else 'no'}"

@app.get("/debug/ping", response_class=PlainTextResponse)
def debug_ping(to: str, text: str = "hello from agentic bot"):
    ok, resp = wa_send_text(to, text)
    return f"ok={ok}\nresp={resp}"
