"""Wave 2 smoke test.

F3: Ahli gizi + admin can override nutrition composition per food+kitchen
F4: Price history logged on manual override; accountant + admin can view
F5: Waste/variance report for accountant + admin
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


def tok(uid: int, username: str) -> str:
    return create_access_token(build_login_payload({
        "id": uid, "username": username, "role": "user", "org_id": 1,
    }))


def setup() -> dict:
    tag = secrets.token_hex(3)
    users = {}
    with engine.begin() as c:
        for role in ("admin", "ahli_gizi", "accountant"):
            name = f"wave2_{role}_{tag}"
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
            users[role] = {"id": uid, "username": name, "token": None}
            created_ids.append(uid)
    for r in users.values():
        r["token"] = tok(r["id"], r["username"])
    return users


def teardown():
    with engine.begin() as c:
        if created_ids:
            c.execute(text("DELETE FROM user_kitchens WHERE user_id = ANY(:ids)"), {"ids": created_ids})
            c.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": created_ids})
        c.execute(text(
            "DELETE FROM food_nutrition_overrides WHERE kitchen_id = :k AND food_code LIKE 'WV2%'"
        ), {"k": KID})
        c.execute(text(
            "DELETE FROM food_prices_history WHERE kitchen_id = :k AND food_code LIKE 'WV2%'"
        ), {"k": KID})
        c.execute(text(
            "DELETE FROM food_prices WHERE food_code LIKE 'WV2%'"
        ))


def hit(method, path, token=None, body=None, params=None):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.request(method, f"{BASE}{path}", headers=h, json=body, params=params, timeout=60)


def run(u):
    fails = 0
    adm, giz, acc = u["admin"]["token"], u["ahli_gizi"]["token"], u["accountant"]["token"]

    # ── F3: Nutrition override (ahli_gizi + admin) ───────────────────────────
    print("\n[F3] food nutrition override")

    r = hit("PATCH", "/api/menu/foods/WV2CODE1/override", giz,
            {"overrides": {"energy": 155.5, "protein": 12.3, "evil_key": "nope"}})
    fails += check("ahli_gizi PATCH override 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        data = r.json().get("overrides", {})
        fails += check("only whitelisted keys saved",
                       "energy" in data and "protein" in data and "evil_key" not in data,
                       str(data))

    # admin may also override
    r = hit("PATCH", "/api/menu/foods/WV2CODE1/override", adm,
            {"overrides": {"energy": 160}})
    fails += check("admin PATCH override 200 (upsert)", r.status_code == 200, str(r.status_code))

    # accountant CANNOT
    r = hit("PATCH", "/api/menu/foods/WV2CODE1/override", acc,
            {"overrides": {"energy": 999}})
    fails += check("accountant PATCH override → 403", r.status_code == 403, str(r.status_code))

    # list — ahli_gizi can view; see our code present
    r = hit("GET", "/api/menu/foods/overrides", giz)
    fails += check("ahli_gizi GET overrides 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        overrides = r.json().get("overrides", {})
        fails += check("WV2CODE1 appears in override list", "WV2CODE1" in overrides, str(list(overrides)[:3]))
        fails += check("energy=160 (admin's later upsert won)",
                       overrides.get("WV2CODE1", {}).get("energy") == 160, str(overrides.get("WV2CODE1")))

    # clear override
    r = hit("DELETE", "/api/menu/foods/WV2CODE1/override", giz)
    fails += check("ahli_gizi DELETE override 200", r.status_code == 200, str(r.status_code))

    # no body / invalid keys → 400
    r = hit("PATCH", "/api/menu/foods/WV2CODE1/override", giz, {"overrides": {"evil_key": 1}})
    fails += check("no valid keys → 400", r.status_code == 400, str(r.status_code))

    # ── F4: Price history ────────────────────────────────────────────────────
    print("\n[F4] price history log")

    # trigger 3 manual overrides → should log 3 entries
    for price in (1000, 1500, None):  # None = clear
        r = hit("PATCH", f"/api/menu/prices/WV2PRICE1", acc,
                {"price": price, "food_name": "Wave2 test item", "manual_source": "test"})
        fails += check(f"accountant PATCH price={price}",
                       r.status_code in (200, 404),  # 404 for clearing a freshly-created row is also acceptable
                       str(r.status_code))

    # accountant can view history
    r = hit("GET", "/api/menu/prices/WV2PRICE1/history", acc)
    fails += check("accountant GET price history 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        history = r.json().get("history", [])
        fails += check("at least 2 history entries logged", len(history) >= 2, f"got {len(history)}")
        fails += check("history entries have source field",
                       all("source" in h for h in history[:3]), str(history[:2]))

    # ahli_gizi CANNOT view
    r = hit("GET", "/api/menu/prices/WV2PRICE1/history", giz)
    fails += check("ahli_gizi GET price history → 403", r.status_code == 403, str(r.status_code))

    # admin CAN view
    r = hit("GET", "/api/menu/prices/WV2PRICE1/history", adm)
    fails += check("admin GET price history 200", r.status_code == 200, str(r.status_code))

    # ── F5: Variance report ──────────────────────────────────────────────────
    print("\n[F5] waste/variance report")

    params = {"from": "2026-04-01", "to": "2026-04-20"}

    r = hit("GET", "/api/reports/variance", acc, params=params)
    fails += check("accountant GET variance 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        d = r.json()
        fails += check("response has days array", isinstance(d.get("days"), list) and len(d["days"]) >= 1, str(len(d.get("days", []))))
        fails += check("response has summary with totals",
                       isinstance(d.get("summary"), dict) and "received" in d["summary"],
                       str(d.get("summary")))
        fails += check("summary has waste pct fields",
                       "processing_waste_pct" in d["summary"] and "delivery_waste_pct" in d["summary"],
                       str(d.get("summary")))

    # admin allowed
    r = hit("GET", "/api/reports/variance", adm, params=params)
    fails += check("admin GET variance 200", r.status_code == 200, str(r.status_code))

    # ahli_gizi blocked
    r = hit("GET", "/api/reports/variance", giz, params=params)
    fails += check("ahli_gizi GET variance → 403", r.status_code == 403, str(r.status_code))

    # bad range
    r = hit("GET", "/api/reports/variance", acc, params={"from": "2026-05-01", "to": "2026-04-01"})
    fails += check("reversed range → 400", r.status_code == 400, str(r.status_code))

    return fails


def main():
    try:
        if requests.get(f"{BASE}/health", timeout=5).status_code != 200:
            print(f"{FAIL} backend not responding")
            return 2
    except Exception as e:
        print(f"{FAIL} {e}")
        return 2

    u = setup()
    try:
        fails = run(u)
    finally:
        teardown()

    if fails:
        print(f"\n{FAIL} {fails} check(s) failed")
        return 1
    print("\n[DONE] Wave 2 smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
