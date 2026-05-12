# backend/api/health.py
import os
import time
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import text

from backend.core.database import remote_engine

router = APIRouter()

CLOUD_PRINT_KEY = os.getenv("CLOUD_PRINT_KEY", "")

def check_print_key(x_print_key: Optional[str]):
    if CLOUD_PRINT_KEY and x_print_key != CLOUD_PRINT_KEY:
        raise HTTPException(status_code=403, detail="Invalid print key")

@router.get("/kaithhealth")
async def health_main():
    return {"status": "ok"}

@router.get("/kaithhealthcheck")
@router.get("/kaithheathcheck")  # keep typo route
@router.get("/health")
@router.get("/healthz")
async def health_variants():
    return {"status": "ok"}


@router.get("/health/deep")
async def health_deep():
    """Deep health: verify DB connectivity + ping latency.

    Returns 200 with details if all components healthy, else 503.
    Use this for monitoring uptime checks (UptimeRobot, Grafana, etc.).
    """
    checks = {"app": "ok"}
    overall_ok = True

    if remote_engine:
        t0 = time.perf_counter()
        try:
            with remote_engine.connect() as c:
                c.execute(text("SELECT 1"))
            checks["db"] = "ok"
            checks["db_latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        except Exception as e:
            checks["db"] = "fail"
            checks["db_error"] = str(e)[:200]
            overall_ok = False
    else:
        checks["db"] = "skipped (no DATABASE_URL)"

    payload = {"status": "ok" if overall_ok else "degraded", **checks}
    if not overall_ok:
        raise HTTPException(status_code=503, detail=payload)
    return payload
