"""Browser E2E: create a user + assign kitchen in one form submission."""
from __future__ import annotations
import secrets
import sys
from playwright.sync_api import sync_playwright
from sqlalchemy import text

from backend.core.database import engine

URL = "http://localhost:5173"
ADMIN = ("admin", "admin123")


def login(page):
    page.goto(f"{URL}/login", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector("input[type='password']", timeout=10000)
    inputs = page.query_selector_all("input")
    text_inputs = [el for el in inputs if (el.get_attribute("type") or "text") != "password"]
    pass_inputs = [el for el in inputs if el.get_attribute("type") == "password"]
    text_inputs[0].fill(ADMIN[0])
    pass_inputs[0].fill(ADMIN[1])
    btn = page.query_selector("button[type='submit'], button:has-text('Login')")
    btn.click()
    # poll page.url instead of wait_for_url — SPA route change doesn't always fire nav events
    deadline = 25000
    step = 250
    elapsed = 0
    while "/login" in page.url and elapsed < deadline:
        page.wait_for_timeout(step)
        elapsed += step
    if "/login" in page.url:
        raise RuntimeError(f"login stuck at {page.url}")


def run():
    tag = secrets.token_hex(3)
    new_username = f"zzmerge_{tag}"
    cleanup_id = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        errs = []
        page.on("console", lambda m: errs.append(f"[{m.type}] {m.text}") if m.type == "error" else None)

        print("[1] login")
        login(page)

        print("[2] navigate to /admin/users (force reload to get latest HMR)")
        page.goto(f"{URL}/admin/users", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1500)
        print(f"    -> url after goto: {page.url}")
        page.reload(wait_until="domcontentloaded")
        # wait for the Users table header to render (means listUsers finished)
        try:
            page.wait_for_selector("h1:has-text('Users')", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        print(f"    -> url after reload: {page.url}")
        page.screenshot(path="admin_users_page.png", full_page=True)
        body_sample = page.inner_text("body")[:400]
        print(f"    -> body sample: {body_sample!r}")
        # If still loading, poll up to 30s
        deadline = 30000
        elapsed = 0
        while "Loading" in page.inner_text("body") and elapsed < deadline:
            page.wait_for_timeout(500)
            elapsed += 500
        if elapsed:
            print(f"    -> waited {elapsed}ms for loading to finish")
        page.wait_for_selector("button:has-text('+ New user')", timeout=15000)

        print("[3] click + New user")
        page.click("button:has-text('+ New user')")
        page.wait_for_selector("[data-testid='create-user-form']", timeout=10000)
        page.wait_for_timeout(500)

        print("[4] fill merged form")
        form = page.locator("[data-testid='create-user-form']")
        # Inputs have no explicit type attr; use :not([type=password]) for the text one
        form.locator("input:not([type='password'])").first.fill(new_username)
        form.locator("input[type='password']").first.fill("test1234")
        # 3 selects inside form: [0]=access level (user/superadmin) [1]=kitchen [2]=kitchen_role
        selects = form.locator("select")
        print(f"    -> form has {selects.count()} select(s)")
        selects.nth(0).select_option(value="user")
        # kitchen: pick first non-empty option value
        kitchen_values = [
            o.get_attribute("value") for o in selects.nth(1).locator("option").element_handles()
        ]
        print(f"    -> kitchen select values: {kitchen_values}")
        first_kid = next(v for v in kitchen_values if v)
        selects.nth(1).select_option(value=first_kid)
        selects.nth(2).select_option(value="ahli_gizi")
        page.screenshot(path="merge_form_filled.png", full_page=True)

        print("[5] submit")
        page.click("button:has-text('Create user')")
        page.wait_for_timeout(3000)

        # check user appears in table with the kitchen+role shown
        page.wait_for_load_state("networkidle", timeout=15000)
        body = page.inner_text("body")
        created = new_username in body
        role_shown = "ahli_gizi" in body
        print(f"    -> username in page: {created}")
        print(f"    -> 'ahli_gizi' appears in page: {role_shown}")
        page.screenshot(path="merge_form_after.png", full_page=True)

        if errs:
            print(f"[console errors] {len(errs)}")
            for e in errs[:5]:
                print(f"   {e}")

        # DB-level verify
        with engine.connect() as c:
            r = c.execute(text("""
                SELECT u.id, u.username, u.role, u.org_id,
                       uk.kitchen_id, uk.role AS kitchen_role, k.name AS kitchen_name
                FROM users u
                LEFT JOIN user_kitchens uk ON uk.user_id = u.id
                LEFT JOIN kitchens k ON k.id = uk.kitchen_id
                WHERE u.username = :n
            """), {"n": new_username}).first()
        if r:
            cleanup_id = r.id
            print(f"[6] DB check: id={r.id} user={r.username} global={r.role} org={r.org_id}")
            print(f"    kitchen_id={r.kitchen_id} kitchen_role={r.kitchen_role} kitchen_name={r.kitchen_name}")
            ok = (
                r.role == "user"
                and r.kitchen_id is not None
                and r.kitchen_role == "ahli_gizi"
            )
        else:
            print(f"[6] DB check: user {new_username} NOT FOUND")
            ok = False

        browser.close()

    # cleanup
    if cleanup_id:
        with engine.begin() as c:
            c.execute(text("DELETE FROM user_kitchens WHERE user_id = :u"), {"u": cleanup_id})
            c.execute(text("DELETE FROM users WHERE id = :u"), {"u": cleanup_id})
        print("[7] cleanup done")

    print()
    if ok:
        print("===== MERGED CREATE+ASSIGN WORKS =====")
        return 0
    print("===== FAILED =====")
    return 1


if __name__ == "__main__":
    sys.exit(run())
