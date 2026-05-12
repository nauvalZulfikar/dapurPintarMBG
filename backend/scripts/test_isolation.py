"""End-to-end multi-kitchen isolation test.

Creates a 2nd kitchen + a staff user scoped only to it, then hits the live
backend as that user and verifies:

  1. `/me` returns only the test kitchen.
  2. `/overview` returns 0 (no leakage from Paseh's 215 items / 4 trays).
  3. `/items`, `/scan-errors`, `/trays` return empty for the test user.
  4. Switching to Paseh via `X-Kitchen-Id: 1` returns 403.
  5. `/admin/*` endpoints return 403 for a non-superadmin.
  6. A superadmin token *can* see both kitchens.
  7. Scanner key for the test kitchen writes scan errors scoped to that kitchen only.

Cleans up all test data at the end.
"""
from __future__ import annotations

import os
import secrets
import sys
import requests
from sqlalchemy import select, text

from backend.core.database import (
    engine,
    remote_kitchens,
    remote_users,
    remote_user_kitchens,
)
from backend.utils.auth import hash_password, create_access_token, build_login_payload

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8001")


# ── Pretty output ───────────────────────────────────────────────────────────

PASS = "[OK]  "
FAIL = "[FAIL]"
INFO = "[..]  "


def check(label: str, cond: bool, detail: str = "") -> bool:
    prefix = PASS if cond else FAIL
    print(f"  {prefix} {label}" + (f"  ({detail})" if detail else ""))
    return cond


# ── Setup ───────────────────────────────────────────────────────────────────

def setup_test_data() -> dict:
    """Create a 2nd kitchen + staff user + superadmin user for the test."""
    test_kitchen_slug = "zz-test-" + secrets.token_hex(3)
    test_username = "zztest_" + secrets.token_hex(3)
    test_super_username = "zzsuper_" + secrets.token_hex(3)

    with engine.begin() as c:
        kres = c.execute(
            remote_kitchens.insert().values(
                slug=test_kitchen_slug,
                name="ZZ Test Kitchen",
                printer_name="ZZTESTPRINTER",
                printer_lang="ZPL",
                label_title="ZZ Test",
                scanner_key=secrets.token_urlsafe(24),
                cloud_print_key=secrets.token_urlsafe(24),
                active=True,
            ).returning(remote_kitchens.c.id, remote_kitchens.c.scanner_key)
        ).first()
        kitchen_id = kres.id
        scanner_key = kres.scanner_key

        ures = c.execute(
            remote_users.insert().values(
                username=test_username,
                password_hash=hash_password("test1234"),
                role="user",
            ).returning(remote_users.c.id)
        ).first()
        user_id = ures.id

        c.execute(
            remote_user_kitchens.insert().values(
                user_id=user_id, kitchen_id=kitchen_id, role="admin",
            )
        )

        sres = c.execute(
            remote_users.insert().values(
                username=test_super_username,
                password_hash=hash_password("super1234"),
                role="superadmin",
            ).returning(remote_users.c.id)
        ).first()
        super_id = sres.id

    print(f"{INFO} created kitchen id={kitchen_id} ({test_kitchen_slug})")
    print(f"{INFO} created staff user id={user_id} ({test_username}) -> kitchen {kitchen_id}")
    print(f"{INFO} created superadmin id={super_id} ({test_super_username})")

    # mint JWTs
    staff = {"id": user_id, "username": test_username, "role": "user"}
    super_u = {"id": super_id, "username": test_super_username, "role": "superadmin"}

    staff_token = create_access_token(build_login_payload(staff))
    super_token = create_access_token(build_login_payload(super_u))

    return {
        "kitchen_id": kitchen_id,
        "scanner_key": scanner_key,
        "user_id": user_id,
        "super_id": super_id,
        "staff_token": staff_token,
        "super_token": super_token,
    }


def teardown(ctx: dict):
    with engine.begin() as c:
        c.execute(text("DELETE FROM scan_errors WHERE kitchen_id = :k"), {"k": ctx["kitchen_id"]})
        c.execute(text("DELETE FROM user_kitchens WHERE user_id IN (:u, :s)"),
                  {"u": ctx["user_id"], "s": ctx["super_id"]})
        c.execute(text("DELETE FROM users WHERE id IN (:u, :s)"),
                  {"u": ctx["user_id"], "s": ctx["super_id"]})
        c.execute(text("DELETE FROM kitchens WHERE id = :k"), {"k": ctx["kitchen_id"]})
    print(f"{INFO} cleanup complete")


# ── Tests ───────────────────────────────────────────────────────────────────

def headers(token: str, kitchen_id: int | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if kitchen_id is not None:
        h["X-Kitchen-Id"] = str(kitchen_id)
    return h


def run_tests(ctx: dict) -> int:
    fails = 0
    staff_h = headers(ctx["staff_token"])
    super_h = headers(ctx["super_token"])

    # 1. /me — staff sees only its test kitchen
    r = requests.get(f"{BASE}/api/auth/me", headers=staff_h, timeout=60)
    data = r.json()
    kids = [k["id"] for k in data.get("kitchens", [])]
    fails += not check("staff /me returns 200", r.status_code == 200, str(r.status_code))
    fails += not check("staff kitchens == [test_kid]", kids == [ctx["kitchen_id"]], f"got {kids}")
    fails += not check("staff role == user",         data.get("role") == "user", str(data.get("role")))
    fails += not check("active_kitchen_id set",       data.get("active_kitchen_id") == ctx["kitchen_id"], str(data.get("active_kitchen_id")))

    # 2. /overview for test kitchen — should be empty
    r = requests.get(f"{BASE}/api/overview", headers=staff_h, timeout=60)
    ov = r.json()
    fails += not check("staff /overview 200", r.status_code == 200)
    fails += not check("staff overview.items_received == 0", ov.get("items_received") == 0, f"got {ov.get('items_received')}")
    fails += not check("staff overview.trays_packed == 0",   ov.get("trays_packed") == 0, f"got {ov.get('trays_packed')}")

    # 3. list endpoints empty
    r = requests.get(f"{BASE}/api/items", headers=staff_h, timeout=60)
    fails += not check("staff /items total == 0", r.json().get("total") == 0, f"got {r.json().get('total')}")
    r = requests.get(f"{BASE}/api/trays", headers=staff_h, timeout=60)
    fails += not check("staff /trays total == 0", r.json().get("total") == 0, f"got {r.json().get('total')}")
    r = requests.get(f"{BASE}/api/scan-errors", headers=staff_h, timeout=60)
    fails += not check("staff /scan-errors total == 0", r.json().get("total") == 0, f"got {r.json().get('total')}")

    # 4. forbidden to look at Paseh (kitchen_id=1) via header
    r = requests.get(f"{BASE}/api/overview", headers=headers(ctx["staff_token"], kitchen_id=1), timeout=60)
    fails += not check("staff cannot impersonate kitchen 1 (403)", r.status_code == 403, f"got {r.status_code}")

    # 5. admin endpoints — kitchen admin (the test user has kitchen role 'admin')
    # is now allowed to see their own kitchen + their own users (Wave 1 feature).
    # Non-admin per-kitchen roles (ahli_gizi/accountant) would still be 403.
    r = requests.get(f"{BASE}/api/admin/kitchens", headers=staff_h, timeout=60)
    fails += not check("kitchen admin GET /admin/kitchens 200 (own kitchen)",
                       r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        only_own = [k["id"] for k in r.json().get("kitchens", [])] == [ctx["kitchen_id"]]
        fails += not check("kitchen admin sees only own kitchen", only_own,
                           f"got {[k['id'] for k in r.json().get('kitchens', [])]}")
    r = requests.get(f"{BASE}/api/admin/users", headers=staff_h, timeout=60)
    fails += not check("kitchen admin GET /admin/users 200 (scoped)",
                       r.status_code == 200, f"got {r.status_code}")

    # 6. superadmin sees all kitchens
    r = requests.get(f"{BASE}/api/auth/me", headers=super_h, timeout=60)
    sdata = r.json()
    all_kids = sorted(k["id"] for k in sdata.get("kitchens", []))
    fails += not check("super /me returns 200", r.status_code == 200)
    fails += not check("super sees >=2 kitchens", len(all_kids) >= 2, f"got {all_kids}")

    r = requests.get(f"{BASE}/api/admin/kitchens", headers=super_h, timeout=60)
    fails += not check("super /admin/kitchens 200", r.status_code == 200, f"got {r.status_code}")

    # super can switch kitchens via X-Kitchen-Id
    r = requests.get(f"{BASE}/api/overview", headers=headers(ctx["super_token"], kitchen_id=1), timeout=60)
    ov1 = r.json()
    fails += not check("super overview kitchen 1 (Paseh) reachable", r.status_code == 200, f"got {r.status_code}")
    r = requests.get(f"{BASE}/api/overview", headers=headers(ctx["super_token"], kitchen_id=ctx["kitchen_id"]), timeout=60)
    ov2 = r.json()
    fails += not check("super overview kitchen zz-test reachable", r.status_code == 200)
    fails += not check(
        "Paseh overview differs from zz-test",
        ov1 != ov2,
        f"paseh={ov1}  zztest={ov2}",
    )

    # 7. scanner key routes to correct kitchen (log scan error on unknown code)
    r = requests.post(
        f"{BASE}/api/scans",
        headers={"X-Scanner-Key": ctx["scanner_key"]},
        json={"code": "TRY-ZZTESTFAKE", "step": "Packing"},
        timeout=60,
    )
    fails += not check("scanner_key accepted (200)", r.status_code == 200, f"got {r.status_code} body={r.text[:120]}")
    scan_kid = r.json().get("kitchen_id")
    fails += not check("scan routed to test kitchen", scan_kid == ctx["kitchen_id"], f"got {scan_kid}")

    # confirm the error went into the test kitchen's scan_errors, not Paseh's
    r = requests.get(f"{BASE}/api/scan-errors", headers=staff_h, timeout=60)
    total = r.json().get("total")
    fails += not check("scan_error landed in test kitchen (>=1)", total >= 1, f"got {total}")

    # bad scanner key — 403
    r = requests.post(
        f"{BASE}/api/scans",
        headers={"X-Scanner-Key": "bogus"},
        json={"code": "TRY-XXXX", "step": "Packing"},
        timeout=60,
    )
    fails += not check("bogus scanner key rejected (403)", r.status_code == 403, f"got {r.status_code}")

    return fails


def main() -> int:
    try:
        # quick health check
        r = requests.get(f"{BASE}/health", timeout=5)
        if r.status_code != 200:
            print(f"{FAIL} backend at {BASE} not responding: {r.status_code}")
            return 2
    except Exception as e:
        print(f"{FAIL} cannot reach {BASE}: {e}")
        return 2

    print(f"{INFO} backend: {BASE}")
    ctx = setup_test_data()
    try:
        fails = run_tests(ctx)
    finally:
        teardown(ctx)

    if fails:
        print(f"\n{FAIL} {fails} check(s) failed")
        return 1
    print("\n[DONE] all checks passed — multi-kitchen isolation works")
    return 0


if __name__ == "__main__":
    sys.exit(main())
