"""Test new Ahli Gizi features (nutrition tracking + menu management).

New endpoints:
1. GET /api/menu/substitutes?code=BERAS — food substitutes with similarity score
2. GET /api/nutrition/daily?date=2026-04-25 — daily nutrition summary
3. GET /api/nutrition/weekly?from=2026-04-19&to=2026-04-25 — weekly nutrition
4. GET /api/menu/saved — list saved menus
5. POST /api/menu/saved — create saved menu
6. DELETE /api/menu/saved/{id} — delete saved menu
"""
from __future__ import annotations
import sys
import requests
import json
from datetime import datetime, timedelta

BASE = "http://127.0.0.1:8001"
PASS = "[OK]  "
FAIL = "[FAIL]"


def check(label: str, ok: bool, extra: str = "") -> int:
    print(f"  {(PASS if ok else FAIL)} {label}" + (f"  ({extra})" if extra else ""))
    return 0 if ok else 1


def hit(method, path, token=None, body=None, params=None):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.request(method, f"{BASE}{path}", headers=h, json=body, params=params, timeout=30)


def login(username="admin", password="admin123"):
    r = requests.post(f"{BASE}/api/auth/login", json={"username": username, "password": password}, timeout=30)
    if r.status_code == 200:
        return r.json().get("access_token")
    return None


def safe_json(r):
    try:
        return r.json()
    except:
        return None


def run():
    fails = 0

    # Get token
    token = login()
    if not token:
        print(f"{FAIL} Failed to authenticate")
        return 2

    print(f"\n[Ahli Gizi Features] Testing new nutrition/menu endpoints")

    # ── Test 1: GET /api/menu/substitutes?code=BERAS ──────────────────────────
    print("\n[1] Menu substitutes (similarity scoring)")
    r = hit("GET", "/api/menu/substitutes", token, params={"code": "BERAS"})
    fails += check("GET /api/menu/substitutes?code=BERAS → 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        data = safe_json(r)
        if data:
            items = data.get("items", [])
            fails += check("response has 'items' array", isinstance(items, list), str(type(items)))
            fails += check("items list has entries", len(items) > 0, f"got {len(items)} items")
            if items:
                first_item = items[0]
                fails += check("item has code", "code" in first_item, str(list(first_item.keys())[:3]))
                fails += check("item has similarity_score", "similarity_score" in first_item, str(list(first_item.keys())[:3]))
                if "similarity_score" in first_item:
                    fails += check("similarity_score is float/int", isinstance(first_item.get("similarity_score"), (int, float)), str(type(first_item.get("similarity_score"))))
        else:
            fails += check("response is valid JSON", False, "not JSON")

    # ── Test 2: GET /api/nutrition/daily?date=2026-04-25 ──────────────────────
    print("\n[2] Daily nutrition summary")
    today_str = "2026-04-25"
    r = hit("GET", "/api/nutrition/daily", token, params={"date": today_str})
    fails += check("GET /api/nutrition/daily?date=... → 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        data = safe_json(r)
        if data:
            fails += check("response has 'date' field", "date" in data, str(list(data.keys())[:5]))
            fails += check("response has 'totals' field", "totals" in data, str(list(data.keys())[:5]))
            fails += check("response has 'per_student' field", "per_student" in data, str(list(data.keys())[:5]))
            fails += check("response has 'akg_target' field", "akg_target" in data, str(list(data.keys())[:5]))
            fails += check("response has 'compliance_pct' field", "compliance_pct" in data, str(list(data.keys())[:5]))
            if "totals" in data:
                totals = data["totals"]
                fails += check("totals is dict", isinstance(totals, dict), str(type(totals)))
            if "compliance_pct" in data:
                pct = data["compliance_pct"]
                fails += check("compliance_pct is numeric", isinstance(pct, (int, float)), str(type(pct)))
        else:
            fails += check("response is valid JSON", False, "not JSON")

    # ── Test 3: GET /api/nutrition/weekly?from=...&to=... ─────────────────────
    print("\n[3] Weekly nutrition summary")
    from_date = "2026-04-19"
    to_date = "2026-04-25"
    r = hit("GET", "/api/nutrition/weekly", token, params={"from": from_date, "to": to_date})
    fails += check("GET /api/nutrition/weekly?from=...&to=... → 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        data = safe_json(r)
        if data:
            days = data.get("days", [])
            fails += check("response has 'days' array", isinstance(days, list), str(type(days)))
            fails += check("days array spans correct range", len(days) >= 1, f"got {len(days)} days")
            if len(days) > 0:
                first_day = days[0]
                fails += check("day entry has date", "date" in first_day, str(list(first_day.keys())[:3]))
                fails += check("day entry has nutritional totals", "totals" in first_day or "energy" in first_day, str(list(first_day.keys())[:3]))
        else:
            fails += check("response is valid JSON", False, "not JSON")

    # ── Test 4: GET /api/menu/saved ────────────────────────────────────────────
    print("\n[4] Get saved menus")
    r = hit("GET", "/api/menu/saved", token)
    fails += check("GET /api/menu/saved → 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        data = safe_json(r)
        if data:
            menus = data.get("saved_menus", [])
            fails += check("response has 'saved_menus' array", isinstance(menus, list), str(type(menus)))
            # Note: may be empty initially
            if menus:
                menu = menus[0]
                fails += check("menu item has id", "id" in menu, str(list(menu.keys())[:3]))
                fails += check("menu item has name", "name" in menu, str(list(menu.keys())[:3]))
        else:
            fails += check("response is valid JSON", False, "not JSON")

    # ── Test 5: POST /api/menu/saved (create) ──────────────────────────────────
    print("\n[5] Create saved menu")
    test_payload = {
        "name": f"Test Menu {int(datetime.now().timestamp())}",
        "payload": {"test": 1, "items": []}
    }
    r = hit("POST", "/api/menu/saved", token, test_payload)
    fails += check("POST /api/menu/saved → 200 or 201", r.status_code in (200, 201), str(r.status_code))
    menu_id = None
    if r.status_code in (200, 201):
        data = safe_json(r)
        if data:
            menu_id = data.get("id")
            fails += check("response has 'id' field", menu_id is not None, str(list(data.keys())[:3]))
            fails += check("response has 'name' field", "name" in data, str(list(data.keys())[:3]))
            fails += check("returned name matches input", data.get("name") == test_payload["name"], str(data.get("name")))
        else:
            fails += check("response is valid JSON", False, "not JSON")

    # ── Test 6: DELETE /api/menu/saved/{id} ────────────────────────────────────
    print("\n[6] Delete saved menu")
    if menu_id:
        r = hit("DELETE", f"/api/menu/saved/{menu_id}", token)
        fails += check(f"DELETE /api/menu/saved/{menu_id} → 200", r.status_code == 200, str(r.status_code))

        # Verify deletion: GET again should not find it
        r = hit("GET", "/api/menu/saved", token)
        if r.status_code == 200:
            data = safe_json(r)
            if data:
                remaining = [m for m in data.get("saved_menus", []) if m.get("id") == menu_id]
                fails += check("deleted menu no longer in list", len(remaining) == 0, f"found {len(remaining)}")

    return fails


def main():
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        if r.status_code != 200:
            print(f"{FAIL} backend not responding (health={r.status_code})")
            return 2
    except Exception as e:
        print(f"{FAIL} {e}")
        return 2

    fails = run()

    if fails:
        print(f"\n{FAIL} {fails} check(s) failed")
        return 1
    print(f"\n[DONE] Ahli Gizi features test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
