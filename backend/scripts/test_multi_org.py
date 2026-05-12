"""End-to-end multi-organization isolation test.

Builds two separate organizations (`dpmbg` + a freshly-created `org-b`), each
with their own superadmin + staff + one kitchen, then verifies:

  1. Superadmin of org A cannot see org B's kitchens / users.
  2. Superadmin of A cannot PATCH a kitchen in org B (403).
  3. Staff of A cannot request X-Kitchen-Id of a kitchen in B (403).
  4. platform_admin CAN see every kitchen in every org.
  5. Same username ("admin") coexists in both orgs without collision.
  6. login with `org_slug` disambiguates.
  7. login without `org_slug` when username is duplicated → 401.

Cleans up all test data at the end.
"""
from __future__ import annotations

import os
import secrets
import sys
import requests
from sqlalchemy import text

from backend.core.database import (
    engine,
    remote_organizations,
    remote_kitchens,
    remote_users,
    remote_user_kitchens,
)
from backend.utils.auth import hash_password, create_access_token, build_login_payload

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8001")


PASS = "[OK]  "
FAIL = "[FAIL]"
INFO = "[..]  "


def check(label: str, cond: bool, detail: str = "") -> bool:
    print(f"  {(PASS if cond else FAIL)} {label}" + (f"  ({detail})" if detail else ""))
    return cond


# ── Setup ───────────────────────────────────────────────────────────────────

def setup() -> dict:
    tag = secrets.token_hex(3)
    with engine.begin() as c:
        org_b = c.execute(
            remote_organizations.insert().values(
                slug=f"org-b-{tag}", name="Org B", active=True,
            ).returning(remote_organizations.c.id, remote_organizations.c.slug)
        ).first()

        # a kitchen in org B
        kb = c.execute(
            remote_kitchens.insert().values(
                org_id=org_b.id,
                slug=f"kit-b-{tag}", name="Kitchen B",
                printer_name="BPR", printer_lang="ZPL",
                label_title="Kitchen B",
                scanner_key=secrets.token_urlsafe(24),
                cloud_print_key=secrets.token_urlsafe(24),
                active=True,
            ).returning(remote_kitchens.c.id)
        ).scalar()

        # "admin" username in org B — tests that same username can live in two orgs
        super_b = c.execute(
            remote_users.insert().values(
                org_id=org_b.id, username="admin",
                password_hash=hash_password("adminB1234"),
                role="superadmin",
            ).returning(remote_users.c.id)
        ).scalar()

        staff_b_name = f"staffb_{tag}"
        staff_b = c.execute(
            remote_users.insert().values(
                org_id=org_b.id, username=staff_b_name,
                password_hash=hash_password("staff1234"),
                role="user",
            ).returning(remote_users.c.id)
        ).scalar()

        c.execute(
            remote_user_kitchens.insert().values(
                user_id=staff_b, kitchen_id=kb, role="staff",
            )
        )

        # a staff user in org A (DPMBG)
        staff_a_name = f"staffa_{tag}"
        staff_a = c.execute(
            remote_users.insert().values(
                org_id=1, username=staff_a_name,
                password_hash=hash_password("staff1234"),
                role="user",
            ).returning(remote_users.c.id)
        ).scalar()
        c.execute(
            remote_user_kitchens.insert().values(
                user_id=staff_a, kitchen_id=1, role="staff",
            )
        )

    print(f"{INFO} org_b id={org_b.id} slug={org_b.slug}")
    print(f"{INFO} kitchen_b id={kb}")
    print(f"{INFO} super_b id={super_b}  staff_a id={staff_a}  staff_b id={staff_b}")

    return {
        "org_b_id": org_b.id, "org_b_slug": org_b.slug,
        "kitchen_b_id": kb,
        "super_b_id": super_b,
        "staff_a_id": staff_a, "staff_a_name": staff_a_name,
        "staff_b_id": staff_b, "staff_b_name": staff_b_name,
    }


def teardown(ctx: dict):
    with engine.begin() as c:
        c.execute(text("DELETE FROM user_kitchens WHERE user_id IN (:a, :b, :s)"),
                  {"a": ctx["staff_a_id"], "b": ctx["staff_b_id"], "s": ctx["super_b_id"]})
        c.execute(text("DELETE FROM users WHERE id IN (:a, :b, :s)"),
                  {"a": ctx["staff_a_id"], "b": ctx["staff_b_id"], "s": ctx["super_b_id"]})
        c.execute(text("DELETE FROM kitchens WHERE id = :k"), {"k": ctx["kitchen_b_id"]})
        c.execute(text("DELETE FROM organizations WHERE id = :o"), {"o": ctx["org_b_id"]})
    print(f"{INFO} cleanup complete")


# ── Tokens ──────────────────────────────────────────────────────────────────

def mint_token(user_id: int, username: str, role: str, org_id: int) -> str:
    return create_access_token(build_login_payload({
        "id": user_id, "username": username, "role": role, "org_id": org_id,
    }))


def H(token: str, kid: int | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if kid is not None:
        h["X-Kitchen-Id"] = str(kid)
    return h


# ── Tests ───────────────────────────────────────────────────────────────────

def run(ctx: dict) -> int:
    fails = 0

    # Fetch existing platform_admin user from DB (promoted by migration)
    with engine.connect() as c:
        plat = c.execute(text("SELECT id, username, role, org_id FROM users WHERE role='platform_admin' LIMIT 1")).first()
    if not plat:
        print(f"{FAIL} no platform_admin user exists — run migrate_multi_org --promote-admin")
        return 1

    plat_token = mint_token(plat.id, plat.username, plat.role, plat.org_id)
    super_b_token = mint_token(ctx["super_b_id"], "admin", "superadmin", ctx["org_b_id"])
    staff_a_token = mint_token(ctx["staff_a_id"], ctx["staff_a_name"], "user", 1)

    # 1. superadmin of org B sees only its own org's kitchens
    r = requests.get(f"{BASE}/api/admin/kitchens", headers=H(super_b_token), timeout=60)
    data = r.json()
    b_ids = [k["id"] for k in data.get("kitchens", [])]
    fails += not check("super_b /admin/kitchens 200", r.status_code == 200)
    fails += not check("super_b sees only its own kitchen", b_ids == [ctx["kitchen_b_id"]], f"got {b_ids}")

    # 2. super_b cannot PATCH kitchen 1 (belongs to org A)
    r = requests.patch(f"{BASE}/api/admin/kitchens/1",
                       headers=H(super_b_token),
                       json={"name": "HACK"}, timeout=60)
    fails += not check("super_b cannot PATCH kitchen in org A (403)", r.status_code == 403, f"got {r.status_code}")

    # 3. super_b /admin/users lists only org_b users
    r = requests.get(f"{BASE}/api/admin/users", headers=H(super_b_token), timeout=60)
    orgs_seen = {u.get("org_id") for u in r.json().get("users", [])}
    fails += not check("super_b /admin/users 200", r.status_code == 200)
    fails += not check("super_b sees only org_b users", orgs_seen == {ctx["org_b_id"]}, f"got {orgs_seen}")

    # 4. staff_a cannot act on kitchen_b via X-Kitchen-Id
    r = requests.get(f"{BASE}/api/overview", headers=H(staff_a_token, kid=ctx["kitchen_b_id"]), timeout=60)
    fails += not check("staff_a blocked from kitchen_b (403)", r.status_code == 403, f"got {r.status_code}")

    # 5. platform_admin sees every org's kitchen
    r = requests.get(f"{BASE}/api/admin/kitchens", headers=H(plat_token), timeout=60)
    p_ids = sorted(k["id"] for k in r.json().get("kitchens", []))
    fails += not check("platform_admin sees all kitchens", 1 in p_ids and ctx["kitchen_b_id"] in p_ids, f"got {p_ids}")

    # 5b. platform_admin can list orgs
    r = requests.get(f"{BASE}/api/admin/organizations", headers=H(plat_token), timeout=60)
    org_ids = sorted(o["id"] for o in r.json().get("organizations", []))
    fails += not check("platform_admin /admin/organizations 200", r.status_code == 200)
    fails += not check("platform_admin sees both orgs", 1 in org_ids and ctx["org_b_id"] in org_ids, f"got {org_ids}")

    # 5c. super_b cannot list organizations
    r = requests.get(f"{BASE}/api/admin/organizations", headers=H(super_b_token), timeout=60)
    fails += not check("super_b /admin/organizations 403", r.status_code == 403, f"got {r.status_code}")

    # 6. Login disambiguation — "admin" exists in both orgs. Must pass org_slug.
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"username": "admin", "password": "adminB1234", "org_slug": ctx["org_b_slug"]},
                      timeout=60)
    fails += not check("login admin+org_slug=B works", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        fails += not check("logged-in user is org_b superadmin", d["user"]["org_id"] == ctx["org_b_id"], f"got {d.get('user')}")

    # 7. Without org_slug, ambiguous login rejected
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"username": "admin", "password": "adminB1234"},
                      timeout=60)
    fails += not check("ambiguous admin login rejected (401)", r.status_code == 401, f"got {r.status_code}")

    return fails


def main() -> int:
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        if r.status_code != 200:
            print(f"{FAIL} backend not responding")
            return 2
    except Exception as e:
        print(f"{FAIL} backend unreachable: {e}")
        return 2

    print(f"{INFO} backend: {BASE}")
    ctx = setup()
    try:
        fails = run(ctx)
    finally:
        teardown(ctx)

    if fails:
        print(f"\n{FAIL} {fails} check(s) failed")
        return 1
    print("\n[DONE] all multi-org checks passed — cross-organization isolation works")
    return 0


if __name__ == "__main__":
    sys.exit(main())
