# DPMBG (Dapur Pintar MBG) — Project Context

Multi-tenant school meal kitchen management system. FastAPI backend + React 19 frontend.

## Stack
- **Backend**: FastAPI + SQLAlchemy + Supabase Postgres (pooler eu-west-1) + JWT auth
- **Frontend**: React 19 + Vite 7 + Tailwind 4 + react-router-dom 7 + recharts + PWA
- **Tests**: Pytest (backend), no E2E yet
- **Deploy**: Docker (bare `docker run`, NOT compose) on Aureonforge VPS

## Local development

### Backend (port 8001 — NOT 8000, that's often occupied)
```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001 --reload
```
- Module path is `backend.app`, NOT `backend.main`
- Health check: `GET http://127.0.0.1:8001/health`

### Frontend (port 5173)
```bash
cd frontend && rtk npm run dev
```

### Vite proxy gotcha
`frontend/vite.config.js` proxies `/api`, `/print-queue`, `/print-complete` → backend port. Default in repo was `:8000`; we run on `:8001`. **If you flip backend port, update vite.config.js or login will 500.**

### Admin credentials (local dev only)
- User: `admin`
- Pass: `admin123`
- Role: `platform_admin`, org: `dpmbg`, kitchen: `paseh`

## Multi-tenant hierarchy
```
platform_admin
  └─ superadmin (org-level)
       └─ admin / ahli_gizi / accountant (per-kitchen)
```
- Users scoped by `org_id`
- Kitchens scoped by `(org_id, slug)`
- M2M via `user_kitchens` table with per-kitchen role

When adding new endpoints, ALWAYS check authz against this hierarchy. Cross-org access is a critical bug.

## Test suites (`backend/scripts/test_*.py`)
96 checks across 4 suites:
- `test_isolation.py` — kitchen isolation
- `test_multi_org.py` — cross-org boundary
- `test_roles.py` — permission matrix
- `test_two_orgs_realistic.py` — Yayasan 3-kitchen + PT 7-kitchen scenario

Run via:
```bash
rtk python backend/scripts/test_isolation.py
# (each is a standalone script, NOT pytest-discovered yet)
```

## Production deployment
Use the `dpmbg-deployer` subagent (`.claude/agents/dpmbg-deployer.md`).

Prod runs on `root@72.60.196.21` at `/root/projects/dpmbg/`:
- Container: `dpmbg_app` (image `dpmbg-app`)
- Port: 8002 (host-bound, behind nginx for `dpmbg.aureonforge.com`)
- Restart pattern: `docker rm -f dpmbg_app && docker run ...` (NOT compose; env baked at create time)

## Project conventions
- API routes in `backend/api/`
- Business logic in `backend/services/`
- Core/shared in `backend/core/`
- React pages in `frontend/src/pages/`, components in `frontend/src/components/`
- Use Pydantic models for request/response shapes (don't pass raw dicts)
- Use FastAPI `Depends()` for auth/db session injection

## Don't touch
- `Salinan dari ... FNCA ... .xlsx` — reference data, not code
- `.env` — Supabase creds; ask before editing
- `printer/`, `scanner/` — hardware integration code; don't refactor without testing on actual device
- `agent.py`, `api_keys.json`, `list_api_keys.py` — Claude/Python agent helpers, not production code
