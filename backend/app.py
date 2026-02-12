# DPMBG_Project\backend\app.py

from fastapi import FastAPI
from backend.api.webhooks import router as webhooks_router
import os
from backend.core.config import GRAPH, PHONE_ID
from backend.core.database import DATABASE_URL

# ---------- FastAPI ----------
app = FastAPI(title="MBG WA Agent (Fully Agentic + Single-Send + Idempotent)")
app.include_router(webhooks_router)

from backend.api.webhooks import router as webhooks_router
from backend.api.scan_terminal import router as scan_router  # ADD
...
app.include_router(webhooks_router)
app.include_router(scan_router)  # ADD
...
import backend.api.scan_terminal  # noqa: F401  # ADD


# ---------- Local run ----------
if __name__ == "__main__":
    import uvicorn
    print(f"[INFO] DB={DATABASE_URL}")
    print(f"[INFO] GRAPH={GRAPH} PHONE_ID={PHONE_ID}")
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
