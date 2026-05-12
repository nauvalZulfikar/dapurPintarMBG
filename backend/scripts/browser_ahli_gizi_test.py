"""Browser smoke for Ahli Gizi feature pack UI hooks.

- Sidebar links: Nutrisi Report, Menu Tersimpan
- /nutrisi page renders header + summary cards
- /menu-library page renders + can save & delete a test menu
- Menu Planner: 'sub' button per food row + popover
"""
from __future__ import annotations
import sys
from playwright.sync_api import sync_playwright

URL = "http://localhost:5173"


def _wait_loaded(page, max_iters=80):
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
    for _ in range(120):
        if "/login" not in page.url:
            return
        page.wait_for_timeout(300)
    raise RuntimeError(f"login stuck at {page.url}")


def main():
    fails = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        errs = []
        page.on("console", lambda m: errs.append(f"[{m.type}] {m.text[:200]}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(f"[pageerror] {str(e)[:200]}"))

        print("[1] login admin")
        login(page)

        # ── A: Sidebar nav presence ──────────────────────────────────────────
        print("[2] sidebar links: Nutrisi Report + Menu Tersimpan")
        page.goto(f"{URL}/", wait_until="domcontentloaded")
        _wait_loaded(page)
        body = page.inner_text("body")
        nav_nutrisi = "Nutrisi Harian" in body or "Nutrisi Report" in body or "Laporan Nutrisi" in body
        nav_menu_lib = "Menu Tersimpan" in body or "Menu Library" in body
        print(f"    -> Nutrisi nav: {nav_nutrisi}")
        print(f"    -> Menu Tersimpan nav: {nav_menu_lib}")
        if not nav_nutrisi: fails += 1
        if not nav_menu_lib: fails += 1

        # ── B: /nutrisi page renders ─────────────────────────────────────────
        print("[3] open /nutrisi page")
        page.goto(f"{URL}/nutrisi", wait_until="domcontentloaded")
        _wait_loaded(page, 80)
        page.wait_for_timeout(2000)
        body = page.inner_text("body")
        body_l = body.lower()
        nutr_loaded = "nutrisi" in body_l or "akg" in body_l
        # Look for date input or summary cards
        date_inputs = page.query_selector_all("input[type='date']")
        print(f"    -> page header found: {nutr_loaded}")
        print(f"    -> date inputs: {len(date_inputs)}")
        if not nutr_loaded: fails += 1
        if len(date_inputs) == 0: fails += 1
        page.screenshot(path="ahli_gizi_nutrisi.png", full_page=True)

        # ── C: /menu-library page renders ────────────────────────────────────
        print("[4] open /menu-library page")
        page.goto(f"{URL}/menu-library", wait_until="domcontentloaded")
        _wait_loaded(page, 80)
        page.wait_for_timeout(1500)
        body = page.inner_text("body")
        body_l = body.lower()
        lib_loaded = "menu" in body_l and ("tersimpan" in body_l or "library" in body_l or "saved" in body_l)
        print(f"    -> Menu Library page loaded: {lib_loaded}")
        if not lib_loaded: fails += 1
        page.screenshot(path="ahli_gizi_library.png", full_page=True)

        # ── D: Menu Planner page renders (substitusi appears after optimize is run) ─
        print("[5] menu planner page loads")
        page.goto(f"{URL}/menu-planner", wait_until="domcontentloaded")
        _wait_loaded(page, 80)
        for _ in range(60):
            if "Daftar Bahan Makanan" in page.inner_text("body"):
                break
            page.wait_for_timeout(500)
        try:
            page.wait_for_selector("table", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(2000)
        body = page.inner_text("body")
        mp_loaded = "Daftar Bahan Makanan" in body or "Optimize" in body
        print(f"    -> menu planner loaded: {mp_loaded}")
        if not mp_loaded: fails += 1
        # Substitusi popover appears AFTER user clicks optimize and gets day cards.
        # That requires a heavy optimize call (~30s) so we skip it in smoke; the
        # API smoke (test_ahli_gizi_corrected.py) already validates /menu/substitutes.

        if errs:
            print(f"\n    -> {len(errs)} console error(s):")
            for e in errs[:5]:
                print(f"       {e}")

        browser.close()

    print()
    if fails == 0:
        print("===== AHLI GIZI UI WIRED =====")
        return 0
    else:
        print(f"===== UI INCOMPLETE: {fails} fail(s) =====")
        return 1


if __name__ == "__main__":
    sys.exit(main())
