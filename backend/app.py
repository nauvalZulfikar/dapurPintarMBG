# backend/app.py
import os
from fastapi import FastAPI
from backend.core.database import REMOTE_DB_URL

from backend.api.health import router as health_router
from backend.api.print_queue import router as print_router

app = FastAPI(title="DPMBG Backend (Scanner + Print)", version="0.1.0")

app.include_router(health_router)
app.include_router(print_router)

if __name__ == "__main__":
    import uvicorn
    print(f"[INFO] DB={REMOTE_DB_URL}")
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
