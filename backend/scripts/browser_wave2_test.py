"""Browser smoke for Wave 2 UI hooks.

- Variance Report nav + page
- Nutrition edit '✎' icons in Menu Planner food rows
- Price 'hist' button in price column (history popover)
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
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        errs = []
        page.on("console", lambda m: errs.append(f"[{m.type}] {m.text[:200]}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(f"[pageerror] {str(e)[:200]}"))

        print("[1] login")
        login(page)

        # ── A: Variance Report nav + page ────────────────────────────────────
        print("[2] sidebar 'Variance Report' link visible")
        page.goto(f"{URL}/", wait_until="domcontentloaded")
        _wait_loaded(page)
        body = page.inner_text("body")
        nav_visible = "Variance Report" in body
        print(f"    -> sidebar link: {nav_visible}")

        print("[3] open /reports/variance and verify summary cards")
        page.goto(f"{URL}/reports/variance", wait_until="domcontentloaded")
        _wait_loaded(page, 80)
        page.wait_for_timeout(2000)
        body = page.inner_text("body")
        body_l = body.lower()
        var_loaded = "laporan variance" in body_l
        has_cards = "items diterima" in body_l and "processing waste" in body_l
        print(f"    -> page header: {var_loaded}, summary cards: {has_cards}")
        page.screenshot(path="wave2_variance.png", full_page=True)

        # ── B: Menu Planner — nutrition '✎' edit + price 'hist' button ──────
        print("[4] menu planner — nutrition pencil + history button")
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
        page.wait_for_timeout(3000)

        nutr_btns = page.query_selector_all("button[title^='Override energy'], button[title^='Override protein']")
        hist_btns = page.query_selector_all("button:has-text('hist')")
        print(f"    -> nutrition '✎' buttons: {len(nutr_btns)}")
        print(f"    -> price 'hist' buttons: {len(hist_btns)}")

        # Click first hist button to open drawer
        if hist_btns:
            hist_btns[0].click()
            page.wait_for_timeout(2000)
            body = page.inner_text("body")
            hist_open = "Riwayat Harga" in body
            print(f"    -> hist drawer opens: {hist_open}")
            page.screenshot(path="wave2_hist.png", full_page=True)
            page.keyboard.press("Escape")
        else:
            hist_open = False

        page.screenshot(path="wave2_menu.png", full_page=True)

        if errs:
            print(f"\n    -> {len(errs)} console error(s):")
            for e in errs[:5]:
                print(f"       {e}")

        browser.close()

    ok = nav_visible and var_loaded and has_cards and len(nutr_btns) > 0 and len(hist_btns) > 0 and hist_open
    print()
    print("===== WAVE 2 UI WIRED =====" if ok else "===== UI INCOMPLETE =====")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
