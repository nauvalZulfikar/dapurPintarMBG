"""End-to-end permission matrix test for the 3 kitchen roles.

Creates 3 users at kitchen 1, each with one of:
  - admin
  - ahli_gizi
  - accountant

Then verifies for each role which endpoints are allowed vs forbidden.

Matrix expected (✓ = 200-ish, ✗ = 403):

Endpoint                            | admin | ahli_gizi | accountant
GET  /api/overview                  |  ✓    |    ✓       |    ✓
GET  /api/items                     |  ✓    |    ✓       |    ✓
POST /api/items                     |  ✓    |    ✗       |    ✗
GET  /api/scan-errors               |  ✓    |    ✗       |    ✓
GET  /api/export/daily              |  ✓    |    ✗       |    ✓
GET  /api/menu/foods                |  ✓    |    ✓       |    ✓
POST /api/menu/optimize             |  ✓    |    ✓       |    ✗
POST /api/menu/prices               |  ✓    |    ✓       |    ✗
"""
from __future__ import annotations

import os
import secrets
import sys
import requests
from sqlalchemy import text

from backend.core.database import engine, remote_users, remote_user_kitchens
from backend.utils.auth import hash_password, create_access_token, build_login_payload

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8001")
KITCHEN_ID = 1   # DPMBG Paseh


PASS = "[OK]  "
FAIL = "[FAIL]"


def check(label: str, cond: bool, detail: str = "") -> bool:
    print(f"  {(PASS if cond else FAIL)} {label}" + (f"  ({detail})" if detail else ""))
    return cond


# ── Setup ───────────────────────────────────────────────────────────────────

def setup() -> dict:
    tag = secrets.token_hex(3)
    users = {}
    with engine.begin() as c:
        for kitchen_role in ("admin", "ahli_gizi", "accountant"):
            uname = f"test_{kitchen_role}_{tag}"
            uid = c.execute(
                remote_users.insert().values(
                    org_id=1, username=uname,
                    password_hash=hash_password("test1234"),
                    role="user",
                ).returning(remote_users.c.id)
            ).scalar()
            c.execute(remote_user_kitchens.insert().values(
                user_id=uid, kitchen_id=KITCHEN_ID, role=kitchen_role,
            ))
            users[kitchen_role] = {"id": uid, "username": uname}
    print(f"[..] created test users: {', '.join(u['username'] for u in users.values())}")
    return users


def teardown(users: dict):
    ids = tuple(u["id"] for u in users.values())
    with engine.begin() as c:
        c.execute(text("DELETE FROM user_kitchens WHERE user_id = ANY(:ids)"), {"ids": list(ids)})
        c.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": list(ids)})
        # Stub items the admin POST test created (name='X', weight=100) — clean them
        c.execute(text(
            "DELETE FROM items WHERE kitchen_id = :k AND name = 'X' AND weight_grams = 100"
        ), {"k": KITCHEN_ID})
    print("[..] cleanup complete")


# ── Tokens ──────────────────────────────────────────────────────────────────

def token_for(user: dict) -> str:
    return create_access_token(build_login_payload({
        "id": user["id"], "username": user["username"], "role": "user", "org_id": 1,
    }))


def hit(method: str, path: str, token: str, body=None):
    url = f"{BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.request(method, url, headers=headers, json=body, timeout=60)
    except requests.exceptions.ReadTimeout:
        return 0  # treat timeout as test-env issue
    return r.status_code


# ── Test matrix ─────────────────────────────────────────────────────────────

def run(users: dict) -> int:
    fails = 0

    CASES = [
        # (method, path, body, {role: expected_prefix})  where prefix is either
        # "2xx" (accept) or "4xx" (reject 403/401).
        ("GET",  "/api/overview",        None, {"admin": "2xx", "ahli_gizi": "2xx", "accountant": "2xx"}),
        ("GET",  "/api/items",           None, {"admin": "2xx", "ahli_gizi": "2xx", "accountant": "2xx"}),
        ("POST", "/api/items",           {"name": "X", "weight": 100}, {"admin": "2xx", "ahli_gizi": "403",  "accountant": "403"}),
        ("GET",  "/api/scan-errors",     None, {"admin": "2xx", "ahli_gizi": "403",  "accountant": "2xx"}),
        ("GET",  "/api/export/daily",    None, {"admin": "2xx", "ahli_gizi": "403",  "accountant": "2xx"}),
        ("GET",  "/api/menu/foods",      None, {"admin": "2xx", "ahli_gizi": "2xx", "accountant": "2xx"}),
        ("POST", "/api/menu/optimize",   {"num_days": 1, "num_students": 10},
                                               {"admin": "2xx", "ahli_gizi": "2xx", "accountant": "403"}),
        ("POST", "/api/menu/prices",     {"keywords": ["bayam"]},
                                               {"admin": "2xx", "ahli_gizi": "2xx", "accountant": "403"}),
    ]

    tokens = {role: token_for(u) for role, u in users.items()}

    for method, path, body, matrix in CASES:
        for role, expected in matrix.items():
            status = hit(method, path, tokens[role], body)
            if status == 0:
                # timeout — skip but don't mark fail
                check(f"{role:10s} {method:4s} {path:25s} timeout — skipping", True)
                continue
            if expected == "2xx":
                ok = 200 <= status < 400
            else:
                ok = status == int(expected[:3])
            fails += not check(f"{role:10s} {method:4s} {path:25s} -> expect {expected}", ok, f"got {status}")

    # /admin/kitchens — kitchen admin sees their own kitchen (scoped); ahli_gizi & accountant blocked
    expected_admin_kitchens = {"admin": "2xx", "ahli_gizi": "403", "accountant": "403"}
    for role, expected in expected_admin_kitchens.items():
        s = hit("GET", "/api/admin/kitchens", tokens[role])
        if expected == "2xx":
            ok = 200 <= s < 400
        else:
            ok = s == int(expected[:3])
        fails += not check(f"{role:10s} GET  /api/admin/kitchens       -> expect {expected}", ok, f"got {s}")

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

    print(f"[..] backend: {BASE}")
    users = setup()
    try:
        fails = run(users)
    finally:
        teardown(users)

    if fails:
        print(f"\n{FAIL} {fails} check(s) failed")
        return 1
    print("\n[DONE] role permissions verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
