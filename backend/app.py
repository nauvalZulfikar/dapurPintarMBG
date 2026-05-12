# backend/app.py
import os
import logging
import logging.handlers
from contextlib import asynccontextmanager

# ── Logging config ──────────────────────────────────────────────────────────
# Configurable via env: LOG_LEVEL (default INFO), LOG_FILE (default logs/dpmbg.log)
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_log_file = os.getenv("LOG_FILE", os.path.join(_LOG_DIR, "dpmbg.log"))
_log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

_root = logging.getLogger()
if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in _root.handlers):
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    _file_h = logging.handlers.RotatingFileHandler(_log_file, maxBytes=10_000_000, backupCount=5, encoding="utf-8")
    _file_h.setFormatter(_fmt)
    _file_h.setLevel(_log_level)
    _root.addHandler(_file_h)
    _root.setLevel(_log_level)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from backend.core.database import REMOTE_DB_URL, init_remote_db

from backend.api.health import router as health_router
from backend.api.print_queue import router as print_router
from backend.api.auth import router as auth_router
from backend.api.scans import router as scans_router
from backend.api.data import router as data_router
from backend.api.sse import router as sse_router
from backend.api.menu import router as menu_router
from backend.api.admin import router as admin_router
from backend.api.nutrition import router as nutrition_router
from backend.api.saved_menus import router as saved_menus_router
from backend.api.defects import router as defects_router
from backend.api.schools_admin import router as schools_admin_router
from backend.api.suppliers import router as suppliers_router
from backend.api.student_requests import router as student_requests_router
from backend.api.purchase_orders import router as purchase_orders_router
from backend.api.inspections import router as inspections_router
from backend.api.disputes import router as disputes_router
from backend.api.production import router as production_router
from backend.api.distributions import router as distributions_router
from backend.api.finance import router as finance_router
from backend.api.aslap import router as aslap_router
from backend.api.notifications import router as notifications_router
from backend.api.executive import router as executive_router

logger = logging.getLogger(__name__)

# ── Scheduler (module-level so it isn't GC'd) ────────────────────────────────
_scheduler = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _scheduler
    # Create DB tables that may not exist yet (food_prices etc.)
    try:
        init_remote_db()
        logger.info("Remote DB tables verified/created")
    except Exception as e:
        logger.warning("init_remote_db failed (may be local-only mode): %s", e)

    # Start daily price scraper
    try:
        from backend.services.price_scheduler import start_scheduler
        _scheduler = start_scheduler()
    except Exception as e:
        logger.warning("Scheduler startup failed: %s", e)

    yield

    # Shutdown
    try:
        from backend.services.price_scheduler import stop_scheduler
        stop_scheduler(_scheduler)
    except Exception:
        pass


app = FastAPI(title="DPMBG Backend", version="0.3.0", lifespan=lifespan)

# Rate limiting (default 200/min per IP; tighter limits applied per-route via decorator)
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security headers — sent on every response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as _StarletteRequest

class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # HSTS only when actually HTTPS (otherwise harmless on http://localhost)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(_SecurityHeadersMiddleware)

# Global exception handler — catch unhandled errors, log, return safe message
from fastapi.requests import Request as _FastAPIRequest
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as _StarletteHTTPException

@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: _FastAPIRequest, exc: Exception):
    # Pass HTTPException through (FastAPI handles it); only catch true unhandled
    if isinstance(exc, _StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Terjadi kesalahan internal. Tim kami sudah dinotifikasi."},
    )

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
app.include_router(admin_router, prefix="/api/admin")
app.include_router(nutrition_router, prefix="/api")
app.include_router(saved_menus_router, prefix="/api")
app.include_router(defects_router, prefix="/api")
app.include_router(schools_admin_router, prefix="/api")    # Phase 1 — admin CRUD for schools
app.include_router(suppliers_router, prefix="/api")         # Phase 1 — supplier master CRUD
app.include_router(student_requests_router, prefix="/api")  # Phase 2A — student menu requests
app.include_router(purchase_orders_router, prefix="/api")    # Phase 3 — Akuntan PO
app.include_router(inspections_router, prefix="/api")        # Phase 3 — Joint Inspection 3-sign-off
app.include_router(disputes_router, prefix="/api")           # Phase 3 — supplier disputes
app.include_router(production_router, prefix="/api")         # Phase 4 — production batches + samples
app.include_router(distributions_router, prefix="/api")      # Phase 5 — distribution layer (confirm receipt, leftovers, vehicles, drivers)
app.include_router(finance_router, prefix="/api")            # Phase 6 — Akuntan finance (price trends, expenses, LRA biweekly)
app.include_router(aslap_router, prefix="/api")              # Phase 7 — ASLAP daily ops (checklist, water, observations, comms, weekly reports)
app.include_router(notifications_router, prefix="/api")      # Phase 8 — notifications + push subs + preferences
app.include_router(executive_router, prefix="/api")          # Phase 9 — executive dashboard 3-level + BGN compliance bundle

# Manual price scrape trigger (admin only, runs in background thread)
import threading
from fastapi import Depends
from backend.utils.auth import get_current_user, get_current_kitchen
from backend.utils.permissions import require_permission

_scrape_thread: threading.Thread | None = None

def _run_scrape_tracked(max_items: int):
    global _scrape_thread
    from backend.services.price_scheduler import run_price_scrape
    try:
        run_price_scrape(max_items=max_items)
    finally:
        _scrape_thread = None

@app.post("/api/menu/prices/scrape")
async def trigger_price_scrape(
    max_items: int = 0,
    kitchen: dict = Depends(require_permission("menu.scrape")),
):
    global _scrape_thread
    if _scrape_thread and _scrape_thread.is_alive():
        return {"ok": False, "message": "Scrape sudah berjalan, tunggu selesai."}
    _scrape_thread = threading.Thread(target=_run_scrape_tracked, kwargs={"max_items": max_items}, daemon=True)
    _scrape_thread.start()
    return {
        "ok": True,
        "message": f"Price scrape started in background ({'all items' if max_items == 0 else f'{max_items} items'}). Check /api/menu/prices/status for progress.",
    }

@app.get("/api/menu/prices/is-running")
async def scrape_is_running(_user: dict = Depends(get_current_user)):
    # readable by anyone logged-in so progress bar works for viewers too
    return {"running": bool(_scrape_thread and _scrape_thread.is_alive())}


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
