"""Smoke test for Wave 1 features.

F1: Kitchen admin scoped management (invite + reset + edit kitchen + rotate keys)
F2a: Accountant manual price override
F2b: Weekly/monthly export
"""
from __future__ import annotations
import secrets
import sys
import requests
from sqlalchemy import text

from backend.core.database import engine, remote_users, remote_user_kitchens
from backend.utils.auth import hash_password, create_access_token, build_login_payload

BASE = "http://127.0.0.1:8001"
KID = 1
PASS = "[OK]  "
FAIL = "[FAIL]"

created_ids: list[int] = []


def check(label: str, ok: bool, extra: str = "") -> int:
    print(f"  {(PASS if ok else FAIL)} {label}" + (f"  ({extra})" if extra else ""))
    return 0 if ok else 1


def token_for(uid: int, username: str, role: str) -> str:
    return create_access_token(build_login_payload({
        "id": uid, "username": username, "role": role, "org_id": 1,
    }))


def setup() -> dict:
    """Provision users: one kitchen admin + one staff user (ahli_gizi) + one accountant."""
    tag = secrets.token_hex(3)
    users = {}
    with engine.begin() as c:
        for role in ("admin", "ahli_gizi", "accountant"):
            name = f"wave1_{role}_{tag}"
            uid = c.execute(
                remote_users.insert().values(
                    org_id=1, username=name,
                    password_hash=hash_password("x"),
                    role="user",
                ).returning(remote_users.c.id)
            ).scalar()
            c.execute(remote_user_kitchens.insert().values(
                user_id=uid, kitchen_id=KID, role=role,
            ))
            users[role] = {"id": uid, "username": name}
            created_ids.append(uid)
    return users


def teardown():
    if not created_ids:
        return
    with engine.begin() as c:
        c.execute(text("DELETE FROM user_kitchens WHERE user_id = ANY(:ids)"),
                  {"ids": created_ids})
        c.execute(text("DELETE FROM users WHERE id = ANY(:ids)"),
                  {"ids": created_ids})
        c.execute(text(
            "DELETE FROM food_prices WHERE food_code = 'WAVE1TEST'"
        ))


def hit(method, path, token=None, body=None, params=None):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.request(method, f"{BASE}{path}", headers=h, json=body, params=params, timeout=30)
    return r


def run(users):
    fails = 0
    admin_tok = token_for(users["admin"]["id"], users["admin"]["username"], "user")
    gizi_tok = token_for(users["ahli_gizi"]["id"], users["ahli_gizi"]["username"], "user")
    acct_tok = token_for(users["accountant"]["id"], users["accountant"]["username"], "user")

    # ── F1: kitchen admin management ────────────────────────────────────────
    print("\n[F1] kitchen admin scoped mgmt")

    # list kitchens: kitchen admin should see only kid=1
    r = hit("GET", "/api/admin/kitchens", admin_tok)
    fails += check("admin GET /admin/kitchens 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        ks = r.json()["kitchens"]
        fails += check("admin sees only kitchen 1", [k["id"] for k in ks] == [KID], str(ks))

    # list users: kitchen admin sees users in kitchen 1
    r = hit("GET", "/api/admin/users", admin_tok)
    fails += check("admin GET /admin/users 200", r.status_code == 200, str(r.status_code))

    # patch kitchen label: kitchen admin can
    r = hit("PATCH", f"/api/admin/kitchens/{KID}", admin_tok, {"label_title": "Wave1 Test"})
    fails += check("admin PATCH kitchen label 200", r.status_code == 200, str(r.status_code))
    # revert
    hit("PATCH", f"/api/admin/kitchens/{KID}", admin_tok, {"label_title": "MBG Kitchen"})

    # kitchen admin cannot deactivate kitchen
    r = hit("PATCH", f"/api/admin/kitchens/{KID}", admin_tok, {"active": False})
    fails += check("admin cannot set active=False → 403", r.status_code == 403, str(r.status_code))

    # rotate scanner key
    r = hit("POST", f"/api/admin/kitchens/{KID}/rotate-scanner-key", admin_tok)
    fails += check("admin rotate scanner-key 200", r.status_code == 200, str(r.status_code))
    new_sk = r.json().get("scanner_key") if r.status_code == 200 else None
    fails += check("new scanner key is non-empty", bool(new_sk) and len(new_sk or "") > 10)

    # ahli_gizi CANNOT rotate
    r = hit("POST", f"/api/admin/kitchens/{KID}/rotate-scanner-key", gizi_tok)
    fails += check("ahli_gizi rotate scanner-key 403", r.status_code == 403, str(r.status_code))

    # kitchen admin invites new user
    new_uname = f"wave1_invited_{secrets.token_hex(2)}"
    r = hit("POST", "/api/admin/users", admin_tok,
            {"username": new_uname, "password": "pw12345678", "role": "user"})
    fails += check("admin creates user 201", r.status_code == 201, str(r.status_code))
    invited_id = None
    if r.status_code == 201:
        invited_id = r.json()["id"]
        created_ids.append(invited_id)
        fails += check("invited user has org_id=1", r.json().get("org_id") == 1, str(r.json()))

    # kitchen admin assigns to own kitchen (role ahli_gizi, not admin)
    if invited_id:
        r = hit("POST", f"/api/admin/users/{invited_id}/kitchens", admin_tok,
                {"kitchen_id": KID, "role": "ahli_gizi"})
        fails += check("admin assigns invited to kitchen ahli_gizi 200", r.status_code == 200, str(r.status_code))

    # kitchen admin cannot grant kitchen-admin role to someone else
    if invited_id:
        r = hit("POST", f"/api/admin/users/{invited_id}/kitchens", admin_tok,
                {"kitchen_id": KID, "role": "admin"})
        fails += check("admin cannot grant 'admin' kitchen role → 403", r.status_code == 403, str(r.status_code))

    # kitchen admin resets password
    if invited_id:
        r = hit("PATCH", f"/api/admin/users/{invited_id}", admin_tok, {"password": "newpw12345"})
        fails += check("admin resets invited password 200", r.status_code == 200, str(r.status_code))

    # kitchen admin cannot change target's global role
    if invited_id:
        r = hit("PATCH", f"/api/admin/users/{invited_id}", admin_tok, {"role": "superadmin"})
        fails += check("admin cannot change global role → 403", r.status_code == 403, str(r.status_code))

    # kitchen admin cannot delete user (destructive)
    if invited_id:
        r = hit("DELETE", f"/api/admin/users/{invited_id}", admin_tok)
        fails += check("admin cannot delete user → 403", r.status_code == 403, str(r.status_code))

    # ahli_gizi cannot access /admin/users at all
    r = hit("GET", "/api/admin/users", gizi_tok)
    fails += check("ahli_gizi GET /admin/users → 403", r.status_code == 403, str(r.status_code))

    # ── F2a: manual price override ──────────────────────────────────────────
    print("\n[F2a] manual price override")

    # accountant CAN override
    r = hit("PATCH", "/api/menu/prices/WAVE1TEST", acct_tok,
            {"price": 12500, "manual_source": "invoice 2026-04", "food_name": "Test ingredient"})
    fails += check("accountant PATCH manual price 200", r.status_code == 200, str(r.status_code))

    # ahli_gizi CANNOT override
    r = hit("PATCH", "/api/menu/prices/WAVE1TEST", gizi_tok, {"price": 999})
    fails += check("ahli_gizi PATCH manual price → 403", r.status_code == 403, str(r.status_code))

    # admin CAN override
    r = hit("PATCH", "/api/menu/prices/WAVE1TEST", admin_tok, {"price": 13000})
    fails += check("admin PATCH manual price 200", r.status_code == 200, str(r.status_code))

    # Clear override (price=null)
    r = hit("PATCH", "/api/menu/prices/WAVE1TEST", acct_tok, {"price": None})
    fails += check("accountant clears manual price 200", r.status_code == 200, str(r.status_code))

    # verify exposed in status
    r = hit("GET", "/api/menu/prices/status", acct_tok)
    fails += check("accountant GET prices/status 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        prices = r.json().get("prices", [])
        has_eff = all("effective_price" in p for p in prices[:3]) if prices else True
        fails += check("prices/status exposes effective_price", has_eff)

    # ── F2b: weekly/monthly export ──────────────────────────────────────────
    print("\n[F2b] weekly/monthly export")

    r = hit("GET", "/api/export/range", acct_tok,
            params={"from": "2026-04-01", "to": "2026-04-20"})
    fails += check("accountant GET export/range 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        clen = int(r.headers.get("content-length", "0") or 0) or len(r.content)
        fails += check("range xlsx > 2KB", clen > 2000, f"{clen}B")

    # ahli_gizi blocked
    r = hit("GET", "/api/export/range", gizi_tok,
            params={"from": "2026-04-01", "to": "2026-04-20"})
    fails += check("ahli_gizi export/range → 403", r.status_code == 403, str(r.status_code))

    # admin allowed
    r = hit("GET", "/api/export/range", admin_tok,
            params={"from": "2026-04-01", "to": "2026-04-07"})
    fails += check("admin export/range 200", r.status_code == 200, str(r.status_code))

    # invalid range rejected
    r = hit("GET", "/api/export/range", acct_tok,
            params={"from": "2026-04-10", "to": "2026-04-01"})
    fails += check("reversed range → 400", r.status_code == 400, str(r.status_code))

    return fails


def main():
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        if r.status_code != 200:
            print(f"{FAIL} backend not responding")
            return 2
    except Exception as e:
        print(f"{FAIL} {e}")
        return 2

    users = setup()
    try:
        fails = run(users)
    finally:
        teardown()

    if fails:
        print(f"\n{FAIL} {fails} check(s) failed")
        return 1
    print(f"\n[DONE] Wave 1 smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
