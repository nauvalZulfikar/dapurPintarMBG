"""Quick browser smoke for Wave 1 UI hooks."""
from __future__ import annotations
import sys
from playwright.sync_api import sync_playwright

URL = "http://localhost:5173"


def _wait_loaded(page, max_iters=60):
    for _ in range(max_iters):
        body = page.inner_text("body")
        if "Loading" not in body and "Memuat" not in body and len(body) > 50:
            page.wait_for_timeout(500)
            return
        page.wait_for_timeout(500)


def login(page, user="admin", pw="admin123"):
    page.goto(f"{URL}/login", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector("input[type='password']", timeout=10000)
    inputs = page.query_selector_all("input")
    text_inputs = [el for el in inputs if (el.get_attribute("type") or "text") != "password"]
    pass_inputs = [el for el in inputs if el.get_attribute("type") == "password"]
    text_inputs[0].fill(user)
    pass_inputs[0].fill(pw)
    page.query_selector("button[type='submit'], button:has-text('Login')").click()
    for _ in range(120):  # up to 36s — supabase eu-west latency
        if "/login" not in page.url:
            return
        page.wait_for_timeout(300)
    raise RuntimeError(f"login stuck at {page.url}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        errs = []
        page.on("console", lambda m: errs.append(f"[{m.type}] {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(f"[pageerror] {e}"))

        print("[1] login as admin (platform_admin)")
        login(page)

        # ── A: Dashboard "Export Range" button visible? ──────────────────────
        print("[2] dashboard — Export Range button")
        page.goto(f"{URL}/", wait_until="domcontentloaded")
        page.reload(wait_until="domcontentloaded")
        _wait_loaded(page, 60)
        body = page.inner_text("body")
        export_range_visible = "Export Range" in body
        print(f"    -> Export Range button: {export_range_visible}")
        if not export_range_visible:
            print(f"    -> body sample: {body[:300]!r}")
            perms = page.evaluate("() => { try { return JSON.parse(localStorage.getItem('token') || 'null') } catch (e) { return null } }")
            # actually check via /api/auth/me from inside browser
            me = page.evaluate("""async () => {
              const t = localStorage.getItem('token')
              const r = await fetch('/api/auth/me', { headers: { Authorization: 'Bearer ' + t } })
              return r.json()
            }""")
            print(f"    -> permissions in /me: {me.get('permissions')}")
        page.screenshot(path="wave1_dashboard.png", full_page=True)

        # ── B: Admin Kitchens — edit modal with Rotate buttons ───────────────
        print("[3] admin kitchens — edit shows Rotate buttons")
        page.goto(f"{URL}/admin/kitchens", wait_until="domcontentloaded")
        _wait_loaded(page, 60)
        # Click Edit on first kitchen row
        edit_btn = page.query_selector("button:has-text('Edit')")
        if edit_btn:
            edit_btn.click()
            page.wait_for_timeout(800)
            modal_text = page.inner_text("body")
            rotate_visible = "Rotate" in modal_text
            print(f"    -> Rotate buttons in edit modal: {rotate_visible}")
            page.screenshot(path="wave1_kitchens_edit.png", full_page=True)
            # close modal
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
        else:
            print("    -> [WARN] no Edit button found")
            rotate_visible = False

        # ── C: Menu Planner — edit price button visible? ────────────────────
        print("[4] menu planner — manual price edit button")
        page.goto(f"{URL}/menu-planner", wait_until="domcontentloaded")
        _wait_loaded(page, 60)
        # wait for FoodTable to auto-load (priceCount > 0 → fires listFoods)
        for _ in range(60):
            if "Daftar Bahan Makanan" in page.inner_text("body"):
                break
            page.wait_for_timeout(500)
        # explicit wait for table content
        try:
            page.wait_for_selector("table", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        show_btn = page.query_selector("button:has-text('Tampilkan Tabel')")
        if show_btn:
            show_btn.click()
            page.wait_for_timeout(4000)
        edit_btns = page.query_selector_all("button:has-text('edit')")
        count_edit = len(edit_btns)
        print(f"    -> 'edit' buttons on price column: {count_edit}")
        body_sample = page.inner_text("body")[:300]
        print(f"    -> body sample: {body_sample!r}")
        page.screenshot(path="wave1_menu.png", full_page=True)

        if errs:
            print(f"\n    -> {len(errs)} console error(s):")
            for e in errs[:5]:
                print(f"       {e}")

        browser.close()

    ok = export_range_visible and rotate_visible and count_edit > 0
    print()
    if ok:
        print("===== WAVE 1 UI HOOKS WIRED =====")
        return 0
    print("===== UI INTEGRATION INCOMPLETE =====")
    return 1


if __name__ == "__main__":
    sys.exit(main())
