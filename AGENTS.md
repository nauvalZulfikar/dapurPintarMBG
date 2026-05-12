# AGENTS.md — DPMBG (Dapur Pintar MBG)

Guide for AI coding agents working on this repo. Covers structure, commands, conventions, and hard rules. Keep this file in sync with `CLAUDE.md`.

---

## Project summary

Multi-tenant school meal kitchen management system for Indonesia's *Makan Bergizi Gratis* (MBG) program. Handles meal production, barcode scan workflow (process → pack → deliver), ZPL/TSPL label printing, weekly menu optimization via PuLP, and TKPI 2020 nutrition tracking.

**Current coverage**: ~30% of full E2E SPPG MBG flow. Roadmap = 10 babak (see Roadmap section). Active phase: **Babak 0 — Foundation Hardening**.

**Stack:** FastAPI + SQLAlchemy + Supabase Postgres (pooler eu-west-1) + JWT · React 19 + Vite 7 + Tailwind 4 + react-router-dom 7 + recharts + PWA · Docker (bare `docker run`) on Aureonforge VPS.

---

## Directory layout

```
DPMBG_Project/
├── backend/
│   ├── app.py                 # FastAPI entry — `backend.app:app` (slowapi limiter, security headers, rotating logger, SPA mount)
│   ├── api/                   # routers: auth, scans, print_queue, menu, data, sse, admin, health, nutrition, saved_menus
│   ├── core/                  # database.py (dual SQLite+Postgres + `_migrate_kitchen_id_integrity`), config, models
│   ├── services/              # business logic (menu_optimizer, printing, price scraper, delivery_optimizer)
│   └── scripts/               # 8 standalone test suites (isolation, multi_org, roles, two_orgs_realistic, wave1, wave2, ahli_gizi_*)
├── frontend/
│   ├── src/
│   │   ├── pages/             # 10 routed pages (Dashboard, Receiving, MenuPlanner, ScanErrors, VarianceReport, NutritionReport, Login, Countdown, Admin{Kitchens,Users,Overview,Orgs})
│   │   ├── components/        # shared UI (Layout, ProtectedRoute, MetricCard, DataTable, Pagination, charts)
│   │   └── main.jsx / App.jsx # entry + router + AuthProvider
│   └── vite.config.js         # proxies /api, /print-queue, /print-complete → :8001
├── docs/                      # TESTING_CHECKLIST.md, etc.
├── CLAUDE.md                  # primary project context (source of truth)
├── AGENTS.md                  # this file (mirror for agent tooling)
├── MULTI_KITCHEN.md           # multi-dapur ops guide
├── IMPROVEMENTS.md            # 30-item roadmap
├── Dockerfile                 # prod image
├── docker-compose.yml         # local dev only
├── requirements.txt           # backend deps
└── .env                       # Supabase creds (DO NOT commit edits)
```

---

## Setup & run

### Backend — port **8001** (not 8000)

```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001 --reload
```

- Module path is `backend.app`, **not** `backend.main`.
- Health check: `GET http://127.0.0.1:8001/health`.
- Requires `.env` with Supabase credentials.

### Frontend — port 5173

```bash
cd frontend && rtk npm run dev
```

### Vite proxy gotcha

`frontend/vite.config.js` proxies `/api`, `/print-queue`, `/print-complete` to the backend port. Default baseline in repo was `:8000`; we run on `:8001`. **If you change the backend port, update `vite.config.js` or login will 500.**

### Local admin credentials (dev only)

| Field | Value |
|-------|-------|
| User | `admin` |
| Pass | `admin123` |
| Role | `platform_admin` |
| Org  | `dpmbg` |
| Kitchen | `paseh` |

---

## Multi-tenant hierarchy & roles (7 total)

```
platform_admin                    ← LU (IT dev / vendor SaaS). Cross-org.
  └─ superadmin                   ← Yayasan owner. 1 org, multi-SPPG.
       └─ head_sppg               ← Kepala SPPG. Pimpinan 1 SPPG. Inherits admin powers.
            ├─ nutritionist       ← Ahli Gizi. Menu, AKG, QC bahan, sign-off Joint Inspection.
            ├─ accountant         ← Akuntan. PO, expense, LRA, sign-off Joint Inspection.
            ├─ aslap              ← Asisten Lapangan. Daily checklist, delivery confirm, sign-off Joint Inspection.
            └─ head_kitchen       ← Kepala Chef. Production batch trigger, tablet scan Processing.
```

**Why exactly 7 roles (floor minimum for BGN compliance):**
- Cross-org (2): `platform_admin`, `superadmin` — beda lingkup, beda kepentingan.
- Per-kitchen (5): structure dari BGN juknis. 3 staf inti SPPG (head_sppg, nutritionist, accountant) + 2 ops support (aslap, head_kitchen). Audit log harus role-based — gak bisa pakai permission flag generik karena BGN audit nanya "siapa yang sign menu / approve receiving".
- **Deprecated**: `admin` (merged into `head_sppg`), `kitchen_staff` (legacy fallback, no active user).

**Scoping:**
- Users scoped by `org_id`.
- Kitchens identified by `(org_id, slug)`.
- Many-to-many via `user_kitchens` table with a per-kitchen role.
- Authorization uses `@require_permission()` decorator with `(org_id, kitchen_id)` scoping.

**Rule:** every new endpoint MUST enforce authz against this hierarchy. Cross-org data leaks are a critical bug.

---

## Testing

Eight standalone suites under `backend/scripts/` (NOT pytest-discovered yet):

| Script | Purpose |
|--------|---------|
| `test_isolation.py` | kitchen-level isolation |
| `test_multi_org.py` | cross-org boundary |
| `test_roles.py` | permission matrix |
| `test_two_orgs_realistic.py` | Yayasan 3-kitchen + PT 7-kitchen scenario |
| `test_wave1.py` | kitchen-admin scoped mgmt + accountant manual price override + range export (28 checks) |
| `test_wave2.py` | wave-2 features (24 checks) |
| `test_ahli_gizi_features.py` | substitutes, AKG report, weekly compliance, saved menus (26 checks) |
| `test_ahli_gizi_corrected.py` | corrected variant of the gizi suite |

Frontend: Vitest + jsdom (`cd frontend && npm test`).

Run a backend suite individually:

```bash
rtk python backend/scripts/test_isolation.py
```

When adding new endpoints that touch org/kitchen data, extend the relevant suite before marking work done. Backend changes should not regress these suites.

### UI verification

For UI-touching changes, verify in a real browser (e.g. Playwright) — not curl against the API alone. The Vite proxy, AuthProvider refresh flow, and PWA service worker can hide bugs that pure API calls won't surface.

---

## Conventions

- **API routes** → `backend/api/`
- **Business logic** → `backend/services/`
- **Core/shared** → `backend/core/`
- **React pages** → `frontend/src/pages/`
- **React components** → `frontend/src/components/`
- Use **Pydantic models** for all request/response shapes; do not return raw dicts.
- Use FastAPI **`Depends()`** for auth and DB-session injection.
- Keep roles, permissions, and org/kitchen scoping in dedicated decorators — never inline authz checks.
- Prefer editing existing files over creating new ones.
- No emojis in code or commits unless asked.
- No backwards-compat shims; change the code in place.

---

## Commit & git hygiene

- Always prefix shell commands with `rtk` when applicable (see `~/.claude/CLAUDE.md` for RTK reference).
- Create new commits; do not `--amend` published commits.
- Never skip hooks (`--no-verify`) or signing.
- Never force-push `master`.
- Before staging `backend/.env` or `api_keys.json`: **stop** and ask.

---

## Production deployment

Use the `dpmbg-deployer` subagent at `.claude/agents/dpmbg-deployer.md`.

- Host: `root@72.60.196.21`
- Path: `/root/projects/dpmbg/`
- Container: `dpmbg_app` (image `dpmbg-app`)
- Port: `8002` host-bound, fronted by nginx at `dapurpintarmbg.aureonforge.com`
- Restart: `docker rm -f dpmbg_app && docker run ...` — **bare docker run, NOT compose**. Env is baked at container-create time, so changing `.env` requires a rebuild+recreate.
- Health: `curl https://dapurpintarmbg.aureonforge.com/health/deep` — returns DB latency; expect ~2s from VPS to Supabase eu-west-1.

Ops runbook (deploy/restart/backup/restore/debug): `docs/OPERATIONS.md`.
Launch-readiness checklist: `docs/LAUNCH_CHECKLIST.md`.

---

## Don't touch without asking

| Path | Reason |
|------|--------|
| `Salinan dari ... FNCA ... .xlsx` | Reference nutrition dataset; not code |
| `.env` | Supabase creds |
| `printer/`, `scanner/` | Hardware integration; test on real device before refactor |
| `agent.py`, `api_keys.json`, `list_api_keys.py` | Claude/Python helper scripts, not production |
| `backend/scripts/test_*.py` | Extend, don't weaken — these guard tenant isolation |

---

## Agent build flow

For new-feature requests ("bikin fitur X", "tambah", "implement Y"), the orchestrator auto-runs `/feature`:

```
spec → architect → explore → implement → [test ↔ fix loop, max 5] → review → simplify → security → docs → (ask) deploy
```

State files:
- `tmp/feature-progress.md` — orchestrator state
- `tmp/test-report.json` — tester output / fixer input
- `docs/spec.md` — append-only feature specs
- `docs/architecture.md` — append-only design decisions

Tester routing for this stack: **`tester-pytest`** (backend is Python/FastAPI).

Skip auto-flow for: single-file bug fixes, pure refactors, exploration questions, or when the user says "tanpa agent".

---

## Roadmap: 10-Babak E2E SPPG MBG Platform

Status: ~30% E2E coverage. Target: 100% (full BGN-compliant) in ~11 weeks (1 dev) / ~7 weeks (2 dev paralel).

| Babak | Goal | Hari | Phase status |
|---|---|---|---|
| 0 | Foundation hardening: 7-role RBAC, audit log expansion, migration framework, feature flags | 2 | ✅ done |
| 1 | School master JSON→DB + supplier master | 3 | ✅ done |
| 2 | Reverse Optimizer (manual menu → auto-calc) + Approval workflow + siklus 20 hari | 6 | ✅ done |
| 3 | Joint Inspection 3-sign-off + PO checklist + container split + multi-label print | 7 | ✅ done |
| 4 | Production batch + auto-debit FIFO + tablet Kepala Chef Processing scan | 5 | ✅ done |
| 5 | Distribution layer (wave classifier + receipt confirm + aggregate) — reuse existing batching | 4 | ✅ done |
| 6 | Akuntan: price trends + spike alert + PO generator + expense + LRA biweekly | 7 | ✅ done |
| 7 | ASLAP daily ops: checklist + water quality + weekly report | 5 | ✅ done |
| **8** | Notifications + push PWA + SSE real-time | **4** | ✅ done |
| **9** | Executive dashboard 3-level (per-kitchen + yayasan + platform) + BGN compliance bundle | **4** | ✅ done |
| **10** | Hardening + offline mode + i18n (ID+Sunda) + pilot SPPG Paseh | **7+** | ⏳ next |

**Key reuse (don't rebuild)**: existing `MEALS_PER_SCAN=10` batching + `_scan_allocations()` + TSPL print + QR countdown (Babak 5), `categorize_food()` + TKPI loader + AKG presets + price scrape (Babak 2/6), schools JSON migrate (Babak 1), scan flow per stage (Babak 4 — Processing only swap to JWT/tablet).

---

## Babak 0 — Foundation Hardening (NEXT)

**Goal:** Setup teknis sebelum nambah modul besar. Zero new feature visible. Siap nampung 5 role baru tanpa breaking existing.

### Scope

#### 1. 7-Role RBAC migration (existing → final)

Drop 2, keep 7 (lihat section "Multi-tenant hierarchy & roles" di atas).

| Action | Detail |
|---|---|
| **Add 4 new per-kitchen roles** | `head_sppg`, `nutritionist`, `accountant`, `aslap`, `head_kitchen` (catatan: `accountant` mungkin sudah ada — verify; kalau ada keep, kalau gak buat baru) |
| **Deprecate `kitchen_staff`** | Mark legacy in `permissions.py`, no new assignment. Existing users (kalau ada) auto-migrate ke `aslap` (closest match) atau ke `head_sppg` (kalau primary user dapur kecil) |
| **Merge `admin` → `head_sppg`** | Kasih `head_sppg` semua permission yang sebelumnya di `admin`. Existing `admin` users kept as alias (backward compat) tapi UI label switch ke "Kepala SPPG" |
| **Permission matrix** | Single source of truth di `docs/permissions.md`. Mapping setiap route × setiap role. |

#### 2. Audit log expansion

Sekarang `audit_log` cuma nyatet `action` + `actor_id` + `kitchen_id` + `timestamp`. Tambah:

| Field baru | Purpose |
|---|---|
| `target_id` | ID record yang diubah (e.g., `menu_plan_id`, `item_id`, `inspection_id`) |
| `before_value` | JSON snapshot before change (untuk update/delete events) |
| `after_value` | JSON snapshot after change |
| `event_category` | Enum: `auth`, `menu`, `receiving`, `production`, `distribution`, `finance`, `compliance` |

Migration script idempotent — alter table add column nullable, backfill `event_category` dari `action` string parsing.

#### 3. Migration framework

Pisah `_online_migrate()` di `database.py` jadi versioned:

```
backend/core/migrations/
  001_initial.py               # baseline (schema saat ini)
  002_kitchen_id_integrity.py  # existing _migrate_kitchen_id_integrity logic
  003_audit_log_expansion.py   # Babak 0
  004_seven_role_rbac.py       # Babak 0
  ...
```

Masing-masing punya `up()` + `down()` (kalau memungkinkan). Track applied versions di table `schema_migrations`.

#### 4. Feature flags

Env-based toggle per phase:

```bash
FEATURE_PHASE_1_SCHOOL_MIGRATE=false
FEATURE_PHASE_2_APPROVAL=false
FEATURE_PHASE_3_JOINT_INSPECTION=false
...
```

Default semua `false`. Setelah phase X selesai + tested, flip ke `true` di prod via env update (no redeploy needed kalau pakai env reload).

#### 5. Progress tracking

Convention dari project: `tmp/feature-progress.md`. Orchestrator agent baca/update file ini.

### Files yang akan di-touch (Babak 0)

| File | Action |
|---|---|
| `backend/utils/permissions.py` | Add 4 new role enum, update permission matrix dict, deprecate `kitchen_staff` |
| `backend/core/database.py` | Extend `audit_log` table schema, add `schema_migrations` table |
| `backend/core/migrations/` | New directory + initial migration files |
| `backend/api/admin.py` | Update role enum + UI label mapping |
| `frontend/src/hooks/useAuth.js` | Update role list + permission checks |
| `frontend/src/pages/AdminUsers.jsx` | Update role dropdown options |
| `docs/permissions.md` | NEW — single source of truth permission matrix |
| `tmp/feature-progress.md` | NEW — orchestrator state |
| `.env.example` | Add FEATURE_PHASE_X flags |

### Acceptance criteria

- [ ] Login sebagai 4 role baru works (test: assign 1 user per role, login, hit kitchen-scoped endpoint)
- [ ] Existing users dengan role `admin` masih jalan (backward compat)
- [ ] `audit_log` baru nyatet `target_id`, `before_value`, `after_value` untuk **minimal 1 event** (e.g., login)
- [ ] `schema_migrations` table ke-populate setelah app startup
- [ ] All 8 backend test suites still pass (no regression)
- [ ] Permission matrix `docs/permissions.md` lengkap untuk **existing** routes (Babak 0 gak nambah route baru)

### NOT in scope of Babak 0

- New feature pages — itu Babak 1+
- School migration — Babak 1
- Joint Inspection — Babak 3
- Notifications — Babak 8

**After Babak 0 done**: orchestrator pivot ke Babak 1 (school migrate JSON → DB).

---

## What's already built (don't re-implement)

- **Rate limiting** — `slowapi` wired in `backend/app.py`; `/api/auth/login` 10/min, global 200/min.
- **Security headers** — X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, HSTS over HTTPS (middleware in `backend/app.py`).
- **Audit log** — `audit_log` table + `db_audit_log()` helper. Login success/fail, user lifecycle, price overrides recorded.
- **Manual price override** — accountant/admin via `PATCH /api/menu/prices/{food_code}` with `manual_price` + `manual_source`.
- **Saved menus library** — `/api/menu/saved` CRUD; UI lives as a modal inside Menu Planner (NOT a separate route).
- **Daily nutrition + weekly AKG compliance** — `/api/nutrition/{daily,weekly-compliance}` + `NutritionReport.jsx` page.
- **Substitutes** — cosine-similarity ingredient swap via `/api/menu/substitutes/{food_code}` (includes partial-match fallback).
- **Range / weekly / monthly export** — `/api/export/range` accountant+admin only, returns `.xlsx` per-day breakdown.
- **Variance & waste report** — `/api/reports/variance` + `VarianceReport.jsx`.
- **Health endpoints** — `/health` (basic) + `/health/deep` (DB ping + latency, 503 on failure).
- **Rotating file logger** — `logs/dpmbg.log`, 10MB × 5 backups (RotatingFileHandler in `backend/app.py`).
- **Per-school AKG presets** — TK/SD/SMP/SMA via `data/schools.json:age_group`.
- **kitchen_id integrity migration** — `_migrate_kitchen_id_integrity()` in `database.py` backfills NULLs (only when single active kitchen) + applies `NOT NULL` to `items`, `trays`, `tray_items`, `print_jobs`, `scan_errors`. Idempotent. Tables that legitimately allow NULL (`food_prices`, `food_prices_history`, `audit_log`) are excluded.
- **Test print** — `POST /api/items/test-print` prints a `TEST-*` label without writing to DB; button on Receiving page.

## Multi-tenant invariants (don't break)

- Kitchen-scoped tables (`items`, `trays`, `tray_items`, `print_jobs`, `scan_errors`) are `NOT NULL kitchen_id` at the DB level. Any new insert path must set `kitchen_id`, or Postgres rejects it.
- Tables that legitimately keep `kitchen_id` nullable: `food_prices` / `food_prices_history` (NULL = global TKPI default shared across kitchens), `audit_log` (login/system events without kitchen context).
- `_migrate_kitchen_id_integrity()` is multi-tenant-safe: it only backfills when exactly **one** active kitchen exists. With ≥2 kitchens it leaves NULLs alone and logs a warning — never auto-attribute to an arbitrary kitchen.
- Any external client (scanner, integration, ops script) writing direct to Supabase must include `kitchen_id`. The DB constraint is the enforcement, not application code.
