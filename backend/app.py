# backend/app.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.core.database import REMOTE_DB_URL

from backend.api.health import router as health_router
from backend.api.print_queue import router as print_router
from backend.api.auth import router as auth_router
from backend.api.scans import router as scans_router
from backend.api.data import router as data_router
from backend.api.sse import router as sse_router
from backend.api.menu import router as menu_router

app = FastAPI(title="DPMBG Backend", version="0.2.0")

# CORS — same-origin in production; configurable for dev / separate frontend
_cors_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers (must be registered before the SPA catch-all)
app.include_router(health_router)
app.include_router(print_router)
app.include_router(auth_router, prefix="/api/auth")
app.include_router(scans_router, prefix="/api")
app.include_router(data_router, prefix="/api")
app.include_router(sse_router, prefix="/api")
app.include_router(menu_router, prefix="/api")

# Serve React SPA (production build)
_SPA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
_SPA_INDEX = os.path.join(_SPA_DIR, "index.html")

if os.path.isdir(os.path.join(_SPA_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(_SPA_DIR, "assets")), name="spa-assets")

# Serve sound files and other public assets
if os.path.isfile(os.path.join(_SPA_DIR, "SUCCESS.mp3")):
    @app.get("/SUCCESS.mp3")
    async def success_sound():
        return FileResponse(os.path.join(_SPA_DIR, "SUCCESS.mp3"))

    @app.get("/FAILED.mp3")
    async def failed_sound():
        return FileResponse(os.path.join(_SPA_DIR, "FAILED.mp3"))

# SPA fallback: serve index.html for all non-API routes
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if os.path.isfile(_SPA_INDEX):
        return FileResponse(_SPA_INDEX)
    return {"detail": "Frontend not built. Run: cd frontend && npm run build"}

if __name__ == "__main__":
    import uvicorn
    print(f"[INFO] DB={REMOTE_DB_URL}")
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
