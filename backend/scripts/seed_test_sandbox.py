"""Seed an isolated test sandbox: own org + kitchen + user + dummy data.

Cred:
    username: testadmin
    password: testadmin123
    org_slug: testsandbox  (only needed if username collides — usually not)

Usage:
    python -m backend.scripts.seed_test_sandbox

Idempotent: re-running upserts master rows (schools/suppliers/items) and
appends a fresh dated set of operational rows (menu/PO/inspection/batch/
distribution/aslap/expense). Safe to call daily.

The sandbox is fully isolated:
- Lives in `Test Sandbox Org` (slug=testsandbox), its own kitchen.
- Existing prod users (admin, etc.) cannot see this kitchen unless they're
  platform_admin (cross-org).
- Drop the whole sandbox: `python -m backend.scripts.seed_test_sandbox --wipe`
"""
from __future__ import annotations

import io
import json
import os
import secrets
import sys
import time
from datetime import date, datetime, timedelta

# Force UTF-8 stdout on Windows so emoji print works
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
from sqlalchemy import select, text

from backend.core.database import (
    engine,
    remote_organizations,
    remote_kitchens,
    remote_users,
    remote_user_kitchens,
    remote_schools,
    remote_suppliers,
    remote_items,
    remote_food_prices,
    remote_food_prices_history,
    remote_purchase_orders,
    remote_po_lines,
    remote_saved_menus,
)
from backend.utils.auth import hash_password

# ── Constants ──────────────────────────────────────────────────────────────
ORG_SLUG = "testsandbox"
ORG_NAME = "Test Sandbox Org"
KITCHEN_SLUG = "testkitchen"
KITCHEN_NAME = "Test Sandbox Kitchen"
USERNAME = "testadmin"
PASSWORD = "testadmin123"
BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8001")

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
DATE_TAG = TODAY.isoformat()


def log(msg: str, ok: bool = True) -> None:
    prefix = "[OK]  " if ok else "[FAIL]"
    print(f"{prefix} {msg}")


# ── 1. Org + Kitchen + User ────────────────────────────────────────────────
def ensure_org_kitchen_user() -> tuple[int, int, int, str]:
    """Returns (org_id, kitchen_id, user_id, password_for_seed)."""
    with engine.begin() as c:
        # org
        row = c.execute(
            select(remote_organizations).where(remote_organizations.c.slug == ORG_SLUG)
        ).first()
        if row:
            org_id = row.id
            log(f"Org exists: id={org_id} slug={ORG_SLUG}")
        else:
            org_id = c.execute(
                remote_organizations.insert()
                .values(slug=ORG_SLUG, name=ORG_NAME, active=True)
                .returning(remote_organizations.c.id)
            ).scalar()
            log(f"Org created: id={org_id} slug={ORG_SLUG}")

        # kitchen
        row = c.execute(
            select(remote_kitchens).where(
                (remote_kitchens.c.org_id == org_id)
                & (remote_kitchens.c.slug == KITCHEN_SLUG)
            )
        ).first()
        if row:
            kid = row.id
            log(f"Kitchen exists: id={kid} slug={KITCHEN_SLUG}")
        else:
            kid = c.execute(
                remote_kitchens.insert()
                .values(
                    org_id=org_id,
                    slug=KITCHEN_SLUG,
                    name=KITCHEN_NAME,
                    printer_name="TEST-PR1",
                    printer_lang="ZPL",
                    label_title="Test Kitchen",
                    scanner_key=secrets.token_urlsafe(24),
                    cloud_print_key=secrets.token_urlsafe(24),
                    address="Jl. Sandbox Test No. 1, Bandung",
                    timezone="Asia/Jakarta",
                    active=True,
                )
                .returning(remote_kitchens.c.id)
            ).scalar()
            log(f"Kitchen created: id={kid} slug={KITCHEN_SLUG}")

        # user
        row = c.execute(
            select(remote_users).where(
                (remote_users.c.org_id == org_id)
                & (remote_users.c.username == USERNAME)
            )
        ).first()
        if row:
            uid = row.id
            # Reset password every run so creds always work
            c.execute(
                remote_users.update()
                .where(remote_users.c.id == uid)
                .values(password_hash=hash_password(PASSWORD), role="superadmin")
            )
            log(f"User exists: id={uid} (password reset)")
        else:
            uid = c.execute(
                remote_users.insert()
                .values(
                    org_id=org_id,
                    username=USERNAME,
                    password_hash=hash_password(PASSWORD),
                    role="superadmin",
                )
                .returning(remote_users.c.id)
            ).scalar()
            log(f"User created: id={uid} username={USERNAME} role=superadmin")

        # user-kitchen link (superadmin sees all kitchens in org auto, but we
        # add an explicit link too — UI relies on it for switcher in some flows)
        link = c.execute(
            select(remote_user_kitchens).where(
                (remote_user_kitchens.c.user_id == uid)
                & (remote_user_kitchens.c.kitchen_id == kid)
            )
        ).first()
        if not link:
            c.execute(
                remote_user_kitchens.insert().values(
                    user_id=uid, kitchen_id=kid, role="kitchen_admin"
                )
            )
            log("User↔Kitchen link added")

    return org_id, kid, uid, PASSWORD


# ── 2. Login (returns auth headers) ────────────────────────────────────────
def login() -> dict:
    # Use org_slug to disambiguate in case username collides
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD, "org_slug": ORG_SLUG},
        timeout=180,
    )
    r.raise_for_status()
    payload = r.json()
    log(f"Login OK — token issued (active_kitchen_id={payload['active_kitchen_id']})")
    return {"Authorization": f"Bearer {payload['access_token']}"}


# ── 3. Schools ─────────────────────────────────────────────────────────────
SCHOOLS = [
    {"name": "TK Mawar Sandbox", "level": "TK", "age_group": "TK (4-6 tahun)",
     "student_count": 40, "distance": 800, "address": "Jl. Test 1",
     "contact": "Bu Wati 0812-0000-0001"},
    {"name": "SD Tunas Bangsa Sandbox", "level": "SD", "age_group": "SD (7-9 tahun)",
     "student_count": 120, "distance": 1500, "address": "Jl. Test 2",
     "contact": "Pak Hadi 0812-0000-0002"},
    {"name": "SMP Bina Sandbox", "level": "SMP", "age_group": "SMP (13-15 tahun)",
     "student_count": 90, "distance": 2400, "address": "Jl. Test 3",
     "contact": "Pak Joni 0812-0000-0003"},
]


def seed_schools(kid: int, h: dict) -> list[int]:
    existing = requests.get(f"{BASE}/api/admin/schools?include_inactive=false", headers=h).json()
    names_existing = {s["name"]: s["id"] for s in existing.get("schools", [])}
    ids = []
    for s in SCHOOLS:
        if s["name"] in names_existing:
            ids.append(names_existing[s["name"]])
            continue
        r = requests.post(f"{BASE}/api/admin/schools", json=s, headers=h)
        if r.status_code == 201:
            ids.append(r.json()["id"])
            log(f"School+ {s['name']} ({s['level']})")
        else:
            log(f"School fail {s['name']}: {r.status_code} {r.text[:120]}", ok=False)
    return ids


# ── 4. Suppliers ───────────────────────────────────────────────────────────
SUPPLIERS = [
    {"name": "Toko Sayur Sandbox", "kategori": "sayur", "rating": 5,
     "contact": "Bu Tini 0813-1111-0001"},
    {"name": "Pak Budi Daging Sandbox", "kategori": "daging", "rating": 5,
     "contact": "Pak Budi 0813-1111-0002"},
    {"name": "Beras Sehat Sandbox", "kategori": "beras", "rating": 4,
     "contact": "Pak Edy 0813-1111-0003"},
]


def seed_suppliers(kid: int, h: dict) -> list[int]:
    existing = requests.get(f"{BASE}/api/suppliers", headers=h).json()
    names_existing = {s["name"]: s["id"] for s in existing.get("suppliers", [])}
    ids = []
    for s in SUPPLIERS:
        if s["name"] in names_existing:
            ids.append(names_existing[s["name"]])
            continue
        r = requests.post(f"{BASE}/api/suppliers", json=s, headers=h)
        if r.status_code == 201:
            ids.append(r.json()["id"])
            log(f"Supplier+ {s['name']} ({s['kategori']})")
        else:
            log(f"Supplier fail {s['name']}: {r.status_code} {r.text[:120]}", ok=False)
    return ids


# ── 5. Food prices (so menu calc has prices) ───────────────────────────────
PRICES = [
    # food_code, name, price_per_100g (IDR)
    ("BRS001", "Beras Putih", 1500),
    ("AYM001", "Ayam Fillet", 4500),
    ("TLR001", "Telur Ayam", 2800),
    ("BAY001", "Bayam", 1200),
    ("WTL001", "Wortel", 1100),
    ("TMT001", "Tomat", 1300),
    ("TPE001", "Tempe", 1800),
    ("THU001", "Tahu Putih", 1500),
]


def seed_prices(kid: int) -> None:
    with engine.begin() as c:
        for code, name, price in PRICES:
            row = c.execute(
                select(remote_food_prices).where(
                    (remote_food_prices.c.kitchen_id == kid)
                    & (remote_food_prices.c.food_code == code)
                )
            ).first()
            if row:
                continue
            c.execute(
                remote_food_prices.insert().values(
                    kitchen_id=kid,
                    food_code=code,
                    food_name=name,
                    price_per_100g=price,
                    source="seed",
                    scraped_at=datetime.utcnow(),
                )
            )
    log(f"Prices seeded ({len(PRICES)} items)")


# ── 6. Menu (saved + submitted + approved) ─────────────────────────────────
def seed_menu(kid: int, uid: int, h: dict) -> int | None:
    """Build a menu manually via POST, submit for review, approve."""
    # Compose a menu using items that have prices
    payload_items = [
        {"code": "BRS001", "name": "Beras Putih", "grams": 120,
         "energy": 1.3 * 120, "protein": 0.07 * 120, "fat": 0.005 * 120, "carbs": 0.28 * 120},
        {"code": "AYM001", "name": "Ayam Fillet", "grams": 80,
         "energy": 1.6 * 80, "protein": 0.31 * 80, "fat": 0.04 * 80, "carbs": 0},
        {"code": "BAY001", "name": "Bayam", "grams": 50,
         "energy": 0.23 * 50, "protein": 0.02 * 50, "fat": 0.003 * 50, "carbs": 0.04 * 50},
    ]
    totals = {
        "energy": sum(i["energy"] for i in payload_items),
        "protein": sum(i["protein"] for i in payload_items),
        "fat": sum(i["fat"] for i in payload_items),
        "carbs": sum(i["carbs"] for i in payload_items),
    }
    menu_name = f"Sandbox Menu {DATE_TAG} — Nasi Ayam Bayam"
    body = {
        "name": menu_name,
        "payload": {"items": payload_items, "totals": totals,
                    "cost_per_serving": 5500},
        "source": "manual",
        "target_date": TOMORROW.isoformat(),
    }
    r = requests.post(f"{BASE}/api/menu/saved", json=body, headers=h)
    if r.status_code not in (200, 201):
        log(f"Menu save fail: {r.status_code} {r.text[:200]}", ok=False)
        return None
    menu_id = r.json()["id"]
    log(f"Menu saved id={menu_id} status=draft")

    # submit for review
    rs = requests.post(f"{BASE}/api/menu/saved/{menu_id}/submit", json={}, headers=h)
    if rs.status_code == 200:
        log(f"Menu submitted (id={menu_id} → pending_review)")
    # approve
    ra = requests.post(
        f"{BASE}/api/menu/saved/{menu_id}/approve",
        json={"notes": "Sandbox auto-approve"},
        headers=h,
    )
    if ra.status_code == 200:
        log(f"Menu approved (id={menu_id})")
    return menu_id


# ── 7. Purchase Order ──────────────────────────────────────────────────────
def seed_po(kid: int, sup_id: int, h: dict) -> int | None:
    body = {
        "supplier_id": sup_id,
        "expected_delivery_date": TOMORROW.isoformat(),
        "notes": f"Sandbox PO {DATE_TAG}",
        "lines": [
            {"item_name": "Ayam Fillet", "item_code": "AYM001",
             "total_weight_grams": 8000, "unit": "kg",
             "expected_containers": 4, "unit_price_idr": 45000,
             "line_total_idr": 360000},
            {"item_name": "Bayam", "item_code": "BAY001",
             "total_weight_grams": 5000, "unit": "kg",
             "expected_containers": 5, "unit_price_idr": 12000,
             "line_total_idr": 60000},
            {"item_name": "Beras Putih", "item_code": "BRS001",
             "total_weight_grams": 12000, "unit": "kg",
             "expected_containers": 1, "unit_price_idr": 15000,
             "line_total_idr": 180000},
        ],
    }
    r = requests.post(f"{BASE}/api/purchase-orders", json=body, headers=h)
    if r.status_code != 201:
        log(f"PO fail: {r.status_code} {r.text[:200]}", ok=False)
        return None
    po_id = r.json()["id"]
    # mark sent
    rp = requests.patch(f"{BASE}/api/purchase-orders/{po_id}",
                        json={"status": "sent"}, headers=h)
    log(f"PO created id={po_id} status={rp.json().get('status')}")
    return po_id


# ── 8. Inspection (3 sign-offs) ────────────────────────────────────────────
def seed_inspection(po_id: int, h: dict) -> int | None:
    r = requests.post(f"{BASE}/api/inspections",
                      json={"po_id": po_id, "notes": f"Sandbox inspection {DATE_TAG}"},
                      headers=h)
    if r.status_code != 201:
        log(f"Inspection fail: {r.status_code} {r.text[:200]}", ok=False)
        return None
    insp = r.json()
    insp_id = insp["id"]
    log(f"Inspection created id={insp_id} lines={len(insp['lines'])}")
    # 3 sign-offs (testadmin acts as superadmin → can do all roles)
    for role in ("quality", "quantity", "physical"):
        rs = requests.post(
            f"{BASE}/api/inspections/{insp_id}/signoff",
            json={"role": role, "status": "approved", "notes": f"sandbox {role} ok"},
            headers=h,
        )
        if rs.status_code != 200:
            log(f"Sign-off {role} fail: {rs.status_code}", ok=False)
    log("Inspection 3 sign-offs done")
    # Accept ALL lines so production has full stock
    accepted = 0
    for line in insp["lines"]:
        ra = requests.post(
            f"{BASE}/api/inspections/{insp_id}/lines/{line['id']}/accept",
            json={
                "containers": [{"weight_grams": line["expected_weight_grams"]}],
                "storage_routing": "refrigerate",
                "notes": "Sandbox accept",
            },
            headers=h,
        )
        if ra.status_code == 200:
            accepted += 1
    log(f"Inspection lines accepted ({accepted}/{len(insp['lines'])})")
    # finalize
    rf = requests.post(f"{BASE}/api/inspections/{insp_id}/finalize", headers=h)
    if rf.status_code == 200:
        log(f"Inspection finalized (status={rf.json().get('status')})")
    return insp_id


# ── 9. Production batch (start + qc + end) ─────────────────────────────────
def seed_batch(menu_id: int, h: dict) -> int | None:
    r = requests.post(f"{BASE}/api/production/batches",
                      json={"menu_plan_id": menu_id, "target_porsi": 5,
                            "dry_run": False},
                      headers=h)
    if r.status_code != 201:
        log(f"Batch start: {r.status_code} {r.text[:160]}", ok=False)
        return None
    bid = r.json()["id"]
    log(f"Batch started id={bid}")
    rq = requests.post(f"{BASE}/api/production/batches/{bid}/qc",
                       json={"sample_location": "Kulkas Sandbox",
                             "notes": "Sandbox QC"}, headers=h)
    if rq.status_code == 200:
        log(f"Batch qc_passed (sample retained)")
    re_ = requests.post(f"{BASE}/api/production/batches/{bid}/end",
                        json={}, headers=h)
    if re_.status_code == 200:
        log(f"Batch ended")
    return bid


# ── 10. Distribution (waves + leftover) ────────────────────────────────────
def seed_distribution(h: dict) -> None:
    r = requests.get(f"{BASE}/api/distributions/today", headers=h)
    if r.status_code == 200:
        log(f"Distribution aggregate available (schools={len(r.json().get('schools', []))})")
    # Add a leftover for the day
    rl = requests.post(f"{BASE}/api/distributions/leftovers",
                       json={"target_date": DATE_TAG,
                             "porsi_leftover": 4,
                             "notes": "Sandbox leftover — sisa 4 ompreng",
                             "reason": "absent"},
                       headers=h)
    if rl.status_code == 201:
        log(f"Leftover logged (4 porsi)")


# ── 11. ASLAP daily ops ────────────────────────────────────────────────────
def seed_aslap(h: dict) -> None:
    # Today's checklist
    rc = requests.get(f"{BASE}/api/aslap/checklists/today", headers=h)
    if rc.status_code == 200:
        items = rc.json().get("items", [])
        # submit checklist all-pass
        rs = requests.post(f"{BASE}/api/aslap/checklists/submit",
                           json={"target_date": DATE_TAG,
                                 "results": [{"key": it["key"], "checked": True,
                                              "notes": ""} for it in items]},
                           headers=h)
        log(f"Checklist submitted ({len(items)} items)")
    # Water quality
    requests.post(f"{BASE}/api/aslap/water-quality",
                  json={"source": "kran_dapur", "ph": 7.2, "tds": 180,
                        "notes": "Sandbox baseline"}, headers=h)
    log("Water quality logged (ph=7.2 tds=180)")
    # Observation
    requests.post(f"{BASE}/api/aslap/observations",
                  json={"category": "kebersihan", "severity": "low",
                        "description": "Sandbox obs — dapur bersih, suhu OK"},
                  headers=h)
    log("Observation logged")
    # Comm log
    requests.post(f"{BASE}/api/aslap/comm-logs",
                  json={"school_name": "SD Tunas Bangsa Sandbox",
                        "channel": "wa",
                        "summary": "Konfirmasi jadwal kirim besok 10:00"},
                  headers=h)
    log("Comm log added")


# ── 12. Finance — expense + volunteer + LRA ────────────────────────────────
def seed_finance(h: dict) -> None:
    requests.post(f"{BASE}/api/finance/expenses",
                  json={"date": DATE_TAG, "category": "utility",
                        "amount_idr": 250_000,
                        "description": f"Sandbox PLN {DATE_TAG}"},
                  headers=h)
    requests.post(f"{BASE}/api/finance/expenses",
                  json={"date": DATE_TAG, "category": "transport",
                        "amount_idr": 120_000,
                        "description": f"Sandbox transport {DATE_TAG}"},
                  headers=h)
    log("Expenses logged (2 rows)")
    requests.post(f"{BASE}/api/finance/volunteers",
                  json={"name": "Bu Yani Sandbox", "role": "ibu_dapur",
                        "honor_idr": 75_000, "date": DATE_TAG},
                  headers=h)
    log("Volunteer payment logged")


# ── 13. Student request ────────────────────────────────────────────────────
def seed_student_request(school_ids: list[int], h: dict) -> None:
    if not school_ids:
        return
    requests.post(f"{BASE}/api/student-requests",
                  json={"school_id": school_ids[0],
                        "kelas": "TK A",
                        "student_name": "Anak Sandbox",
                        "request_text": "Anak alergi telur, butuh menu pengganti"},
                  headers=h)
    log("Student request logged (alergi telur)")


# ── 14. WIPE (optional) ────────────────────────────────────────────────────
def wipe() -> None:
    print("⚠️  Wiping ENTIRE Test Sandbox Org (slug=testsandbox)…")
    with engine.begin() as c:
        org = c.execute(select(remote_organizations).where(
            remote_organizations.c.slug == ORG_SLUG)).first()
        if not org:
            print("Nothing to wipe — org not found.")
            return
        org_id = org.id
        # Cascade: kitchens → users will lose org link, all kitchen-scoped data
        # is FK-bound. We rely on ON DELETE for joined tables; for hard cleanup
        # delete kitchen rows after wiping their data.
        kitchen_ids = [r.id for r in c.execute(
            select(remote_kitchens.c.id).where(remote_kitchens.c.org_id == org_id)
        ).all()]
        # Delete data scoped to these kitchens
        scoped_tables = [
            "aslap_reports", "aslap_school_comm_logs", "aslap_production_observations",
            "aslap_water_quality", "aslap_checklist_results",
            "lra_periods", "expenses", "volunteer_payments",
            "distribution_leftovers", "delivery_confirmations",
            "production_samples", "production_batches",
            "supplier_disputes", "inspection_signoffs", "inspection_lines",
            "receiving_inspections", "po_lines", "purchase_orders",
            "student_requests", "saved_menus",
            "items", "tray_items", "trays", "scan_errors", "print_jobs",
            "food_prices_history", "food_prices",
            "schools", "suppliers", "user_kitchens",
        ]
        for t in scoped_tables:
            try:
                c.execute(text(f"DELETE FROM {t} WHERE kitchen_id = ANY(:kids)"),
                          {"kids": kitchen_ids})
            except Exception as e:
                # Some tables may not exist yet on this DB; ignore.
                if "does not exist" not in str(e):
                    print(f"  warn {t}: {str(e)[:120]}")
        # Users
        c.execute(text("DELETE FROM users WHERE org_id = :o"), {"o": org_id})
        # Kitchens
        c.execute(text("DELETE FROM kitchens WHERE org_id = :o"), {"o": org_id})
        # Org
        c.execute(text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
    print("✅ Sandbox wiped.")


# ── Main ───────────────────────────────────────────────────────────────────
def main() -> None:
    if "--wipe" in sys.argv:
        wipe()
        return

    print(f"\n🧪 Seeding Test Sandbox @ {BASE}\n   Date: {DATE_TAG}\n")

    org_id, kid, uid, _pw = ensure_org_kitchen_user()
    seed_prices(kid)

    h = login()

    school_ids = seed_schools(kid, h)
    sup_ids = seed_suppliers(kid, h)
    seed_student_request(school_ids, h)

    menu_id = seed_menu(kid, uid, h)
    po_id = seed_po(kid, sup_ids[1] if len(sup_ids) > 1 else sup_ids[0], h) if sup_ids else None
    if po_id:
        seed_inspection(po_id, h)
    if menu_id:
        seed_batch(menu_id, h)

    seed_distribution(h)
    seed_aslap(h)
    seed_finance(h)

    print(f"""
✨ Done. Login at http://localhost:5173/

   Username  : {USERNAME}
   Password  : {PASSWORD}
   Org slug  : {ORG_SLUG}   (only needed if username collides; usually not)
   Kitchen   : {KITCHEN_NAME} (id={kid})

   Re-run any time → master rows upsert, operational rows append (dated).
   Wipe everything: python -m backend.scripts.seed_test_sandbox --wipe
""")


if __name__ == "__main__":
    main()
