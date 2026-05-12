"""Realistic 2-organization isolation test.

Scenario:
  Org A "Yayasan Makan Sehat"  — 3 kitchens, 5 users
  Org B "PT Dapur Nusantara"   — 7 kitchens, 5 users

Each org has its own:
  - superadmin (same username "admin" in both, disambiguated by org_slug at login)
  - 2 kitchen admins (assigned to different kitchens within that org)
  - 1 ahli_gizi  assigned to 2 kitchens within that org
  - 1 accountant assigned to all kitchens within that org

Verifies:
  1. Org A superadmin sees exactly its 3 kitchens, not B's 7.
  2. Org B superadmin sees exactly its 7 kitchens, not A's 3.
  3. Org A kitchen-admin cannot touch any Org B kitchen (403).
  4. Org A ahli_gizi cannot switch to any Org B kitchen (403).
  5. Cross-org username "admin" resolves correctly via org_slug.
  6. Ambiguous login (same username, multiple orgs) → 401 when org_slug missing.
  7. platform_admin sees every kitchen across all orgs.
  8. Admin endpoints on B are 403 when hit with A's superadmin token.
  9. /admin/overview for A excludes B's kitchens.
 10. A user assigned to specific kitchens only sees those in /me.

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


# ── Setup: provision 2 orgs with realistic user+kitchen structure ───────────

def make_org(tag: str, slug: str, name: str, n_kitchens: int, super_pw: str) -> dict:
    with engine.begin() as c:
        org_id = c.execute(
            remote_organizations.insert()
            .values(slug=slug, name=name, active=True)
            .returning(remote_organizations.c.id)
        ).scalar()

        kitchen_ids = []
        for i in range(1, n_kitchens + 1):
            kid = c.execute(
                remote_kitchens.insert().values(
                    org_id=org_id,
                    slug=f"{slug}-k{i}", name=f"{name} Kitchen {i}",
                    printer_name=f"{slug.upper()}-PR{i}",
                    printer_lang="ZPL",
                    label_title=f"{name} K{i}",
                    scanner_key=secrets.token_urlsafe(24),
                    cloud_print_key=secrets.token_urlsafe(24),
                    active=True,
                ).returning(remote_kitchens.c.id)
            ).scalar()
            kitchen_ids.append(kid)

        # same username "admin" in every org — test the disambiguation claim
        super_id = c.execute(
            remote_users.insert().values(
                org_id=org_id, username="admin",
                password_hash=hash_password(super_pw),
                role="superadmin",
            ).returning(remote_users.c.id)
        ).scalar()

        # 2 kitchen-admins (assigned to kitchens 1 & 2 respectively)
        ka_ids = []
        for i in range(2):
            uname = f"kadm_{tag}_{i+1}"
            uid = c.execute(
                remote_users.insert().values(
                    org_id=org_id, username=uname,
                    password_hash=hash_password("testpw1234"),
                    role="user",
                ).returning(remote_users.c.id)
            ).scalar()
            c.execute(remote_user_kitchens.insert().values(
                user_id=uid, kitchen_id=kitchen_ids[i], role="admin",
            ))
            ka_ids.append(uid)

        # ahli_gizi assigned to first 2 kitchens
        gizi_id = c.execute(
            remote_users.insert().values(
                org_id=org_id, username=f"gizi_{tag}",
                password_hash=hash_password("testpw1234"),
                role="user",
            ).returning(remote_users.c.id)
        ).scalar()
        for kid in kitchen_ids[: min(2, len(kitchen_ids))]:
            c.execute(remote_user_kitchens.insert().values(
                user_id=gizi_id, kitchen_id=kid, role="ahli_gizi",
            ))

        # accountant assigned to ALL kitchens of the org
        acc_id = c.execute(
            remote_users.insert().values(
                org_id=org_id, username=f"acc_{tag}",
                password_hash=hash_password("testpw1234"),
                role="user",
            ).returning(remote_users.c.id)
        ).scalar()
        for kid in kitchen_ids:
            c.execute(remote_user_kitchens.insert().values(
                user_id=acc_id, kitchen_id=kid, role="accountant",
            ))

    return {
        "id": org_id, "slug": slug, "name": name,
        "kitchen_ids": kitchen_ids,
        "super_id": super_id,
        "ka_ids": ka_ids,
        "gizi_id": gizi_id,
        "acc_id": acc_id,
    }


def setup() -> dict:
    tag_a = secrets.token_hex(3)
    tag_b = secrets.token_hex(3)
    print(f"{INFO} provisioning Org A (3 kitchens) and Org B (7 kitchens)...")
    org_a = make_org(tag_a, f"yms-{tag_a}", "Yayasan Makan Sehat", 3, "adminA1234")
    org_b = make_org(tag_b, f"ptdn-{tag_b}", "PT Dapur Nusantara", 7, "adminB1234")
    print(f"{INFO} org_a={org_a['slug']} kitchens={org_a['kitchen_ids']}")
    print(f"{INFO} org_b={org_b['slug']} kitchens={org_b['kitchen_ids']}")
    return {"a": org_a, "b": org_b}


def teardown(ctx: dict):
    a, b = ctx["a"], ctx["b"]
    user_ids = [a["super_id"], *a["ka_ids"], a["gizi_id"], a["acc_id"],
                b["super_id"], *b["ka_ids"], b["gizi_id"], b["acc_id"]]
    with engine.begin() as c:
        c.execute(text("DELETE FROM user_kitchens WHERE user_id = ANY(:ids)"), {"ids": user_ids})
        c.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": user_ids})
        c.execute(text("DELETE FROM kitchens WHERE id = ANY(:ids)"),
                  {"ids": a["kitchen_ids"] + b["kitchen_ids"]})
        c.execute(text("DELETE FROM organizations WHERE id = ANY(:ids)"),
                  {"ids": [a["id"], b["id"]]})
    print(f"{INFO} cleanup complete")


# ── Tokens ──────────────────────────────────────────────────────────────────

def mint(user_id: int, username: str, role: str, org_id: int) -> str:
    return create_access_token(build_login_payload({
        "id": user_id, "username": username, "role": role, "org_id": org_id,
    }))


def H(token: str, kid: int | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if kid is not None:
        h["X-Kitchen-Id"] = str(kid)
    return h


def safe_json(r):
    """Return parsed body or None, printing status+text on error. Useful to
    make timeouts / 500s readable instead of raising."""
    try:
        return r.json()
    except Exception:
        print(f"    (non-JSON response: HTTP {r.status_code} body={r.text[:120]!r})")
        return None


# ── Tests ───────────────────────────────────────────────────────────────────

def run(ctx: dict) -> int:
    fails = 0
    a, b = ctx["a"], ctx["b"]

    # ── Mint tokens ─────────────────────────────────────────────────────────
    super_a   = mint(a["super_id"], "admin",           "superadmin", a["id"])
    super_b   = mint(b["super_id"], "admin",           "superadmin", b["id"])
    ka_a1     = mint(a["ka_ids"][0], f"kadm_a1_fake", "user",        a["id"])
    gizi_a    = mint(a["gizi_id"],  f"gizi_a",         "user",        a["id"])
    acc_b     = mint(b["acc_id"],   f"acc_b",          "user",        b["id"])

    # Platform_admin (real user 'admin' id=1 promoted in migration)
    with engine.connect() as c:
        plat_row = c.execute(text("SELECT id, username, role, org_id FROM users WHERE role='platform_admin' LIMIT 1")).first()
    plat = mint(plat_row.id, plat_row.username, plat_row.role, plat_row.org_id)

    # ── 1) Org-A superadmin scope ───────────────────────────────────────────
    r = requests.get(f"{BASE}/api/admin/kitchens", headers=H(super_a), timeout=60)
    ids = sorted(k["id"] for k in r.json().get("kitchens", []))
    fails += not check("super_A /admin/kitchens 200", r.status_code == 200)
    fails += not check("super_A sees exactly its 3 kitchens", ids == sorted(a["kitchen_ids"]), f"got {ids}")

    # ── 2) Org-B superadmin scope ───────────────────────────────────────────
    r = requests.get(f"{BASE}/api/admin/kitchens", headers=H(super_b), timeout=60)
    ids = sorted(k["id"] for k in r.json().get("kitchens", []))
    fails += not check("super_B /admin/kitchens 200", r.status_code == 200)
    fails += not check("super_B sees exactly its 7 kitchens", ids == sorted(b["kitchen_ids"]), f"got {ids}")

    # ── 3) Users list also org-scoped ───────────────────────────────────────
    r = requests.get(f"{BASE}/api/admin/users", headers=H(super_a), timeout=60)
    orgs_seen = {u["org_id"] for u in r.json().get("users", [])}
    fails += not check("super_A sees only its own users", orgs_seen == {a["id"]}, f"got {orgs_seen}")

    r = requests.get(f"{BASE}/api/admin/users", headers=H(super_b), timeout=60)
    orgs_seen = {u["org_id"] for u in r.json().get("users", [])}
    fails += not check("super_B sees only its own users", orgs_seen == {b["id"]}, f"got {orgs_seen}")

    # ── 4) super_A cannot PATCH any kitchen in Org B ────────────────────────
    for kid in b["kitchen_ids"][:3]:
        r = requests.patch(f"{BASE}/api/admin/kitchens/{kid}",
                           headers=H(super_a),
                           json={"name": "HACK"}, timeout=60)
        fails += not check(f"super_A cannot PATCH B.kitchen {kid} (403)",
                           r.status_code == 403, f"got {r.status_code}")

    # ── 5) kitchen-admin in A cannot access any B kitchen via header ───────
    for kid in b["kitchen_ids"][:3]:
        r = requests.get(f"{BASE}/api/overview", headers=H(ka_a1, kid=kid), timeout=60)
        fails += not check(f"ka_A blocked from B.kitchen {kid} (403)",
                           r.status_code == 403, f"got {r.status_code}")

    # ── 6) ahli_gizi A cannot optimize menu in B kitchen ────────────────────
    some_b_kid = b["kitchen_ids"][0]
    r = requests.post(f"{BASE}/api/menu/optimize",
                      headers=H(gizi_a, kid=some_b_kid),
                      json={"num_days": 1, "num_students": 10}, timeout=60)
    fails += not check("gizi_A menu.optimize on B.kitchen (403)",
                       r.status_code == 403, f"got {r.status_code}")

    # ── 7) accountant B can export at any B kitchen, not A ─────────────────
    r = requests.get(f"{BASE}/api/export/daily",
                     headers=H(acc_b, kid=b["kitchen_ids"][3]), timeout=60)
    fails += not check("acc_B can export at B.kitchen (200)",
                       200 <= r.status_code < 400, f"got {r.status_code}")

    r = requests.get(f"{BASE}/api/export/daily",
                     headers=H(acc_b, kid=a["kitchen_ids"][0]), timeout=60)
    fails += not check("acc_B cannot export at A.kitchen (403)",
                       r.status_code == 403, f"got {r.status_code}")

    # ── 8) Login disambiguation ─────────────────────────────────────────────
    # Three users named "admin" now: DPMBG platform_admin, org A superadmin, org B superadmin.
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"username": "admin", "password": "adminA1234", "org_slug": a["slug"]},
                      timeout=60)
    fails += not check("login admin+org_slug=A works (200)", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        fails += not check("logged-in user has org_a", r.json()["user"]["org_id"] == a["id"], str(r.json()["user"]))

    r = requests.post(f"{BASE}/api/auth/login",
                      json={"username": "admin", "password": "adminB1234", "org_slug": b["slug"]},
                      timeout=60)
    fails += not check("login admin+org_slug=B works (200)", r.status_code == 200, f"got {r.status_code}")

    # no org_slug — should be 401 because username "admin" is ambiguous
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"username": "admin", "password": "adminA1234"},
                      timeout=60)
    fails += not check("ambiguous admin login rejected (401)",
                       r.status_code == 401, f"got {r.status_code}")

    # wrong password + correct slug → 401
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"username": "admin", "password": "wrong", "org_slug": a["slug"]},
                      timeout=60)
    fails += not check("wrong password rejected (401)", r.status_code == 401, f"got {r.status_code}")

    # ── 9) platform_admin cross-org view ────────────────────────────────────
    r = requests.get(f"{BASE}/api/admin/kitchens", headers=H(plat), timeout=60)
    all_ids = {k["id"] for k in r.json().get("kitchens", [])}
    need = set(a["kitchen_ids"] + b["kitchen_ids"])
    fails += not check("platform_admin sees both orgs' kitchens", need.issubset(all_ids),
                       f"need {need}, got {sorted(all_ids)}")

    r = requests.get(f"{BASE}/api/admin/organizations", headers=H(plat), timeout=60)
    org_ids = {o["id"] for o in r.json().get("organizations", [])}
    fails += not check("platform_admin sees both orgs", {a["id"], b["id"]}.issubset(org_ids), f"got {sorted(org_ids)}")

    # super_A cannot list orgs
    r = requests.get(f"{BASE}/api/admin/organizations", headers=H(super_a), timeout=60)
    fails += not check("super_A /admin/organizations 403", r.status_code == 403, f"got {r.status_code}")

    # ── 10) /admin/overview per-org scope ──────────────────────────────────
    r = requests.get(f"{BASE}/api/admin/overview", headers=H(super_a), timeout=180)
    body = safe_json(r) or {}
    fails += not check("super_A /admin/overview 200", r.status_code == 200, f"got {r.status_code}")
    kitchens_in_overview = {k["kitchen_id"] for k in body.get("kitchens", [])}
    fails += not check(
        "super_A overview excludes B's kitchens",
        kitchens_in_overview.isdisjoint(b["kitchen_ids"]),
        f"overlap {kitchens_in_overview & set(b['kitchen_ids'])}",
    )
    fails += not check(
        "super_A overview includes ALL A's kitchens",
        set(a["kitchen_ids"]).issubset(kitchens_in_overview),
        f"got {sorted(kitchens_in_overview)}",
    )

    # ── 11) /me for a multi-kitchen user shows only their kitchens ─────────
    r = requests.get(f"{BASE}/api/auth/me", headers=H(gizi_a), timeout=60)
    gizi_kids = sorted(k["id"] for k in r.json().get("kitchens", []))
    fails += not check("gizi_A /me shows only its 2 kitchens",
                       gizi_kids == sorted(a["kitchen_ids"][:2]), f"got {gizi_kids}")

    # ── 12) accountant B /me shows all 7 B kitchens ─────────────────────────
    r = requests.get(f"{BASE}/api/auth/me", headers=H(acc_b), timeout=60)
    acc_kids = sorted(k["id"] for k in r.json().get("kitchens", []))
    fails += not check("acc_B /me shows all 7 B kitchens",
                       acc_kids == sorted(b["kitchen_ids"]), f"got {acc_kids}")

    # ── 13) Ahli_gizi permission set is correct ─────────────────────────────
    gizi_perms = set(r.json().get("permissions", []))  # from acc_b, wrong — redo
    r = requests.get(f"{BASE}/api/auth/me", headers=H(gizi_a), timeout=60)
    gizi_perms = set(r.json().get("permissions", []))
    fails += not check("gizi_A has menu.optimize", "menu.optimize" in gizi_perms, str(sorted(gizi_perms)))
    fails += not check("gizi_A lacks items.create", "items.create" not in gizi_perms, str(sorted(gizi_perms)))
    fails += not check("gizi_A lacks export.daily", "export.daily" not in gizi_perms, str(sorted(gizi_perms)))

    r = requests.get(f"{BASE}/api/auth/me", headers=H(acc_b), timeout=60)
    acc_perms = set(r.json().get("permissions", []))
    fails += not check("acc_B has export.daily", "export.daily" in acc_perms, str(sorted(acc_perms)))
    fails += not check("acc_B lacks menu.optimize", "menu.optimize" not in acc_perms, str(sorted(acc_perms)))

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
    print("\n[DONE] realistic 2-org scenario — all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
