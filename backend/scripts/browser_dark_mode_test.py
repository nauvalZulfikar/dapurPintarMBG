"""Visual check: dark vs light mode text contrast on admin pages."""
from __future__ import annotations
import sys
from playwright.sync_api import sync_playwright

URL = "http://localhost:5173"


def login(page):
    page.goto(f"{URL}/login", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector("input[type='password']", timeout=10000)
    inputs = page.query_selector_all("input")
    text_inputs = [el for el in inputs if (el.get_attribute("type") or "text") != "password"]
    pass_inputs = [el for el in inputs if el.get_attribute("type") == "password"]
    text_inputs[0].fill("admin")
    pass_inputs[0].fill("admin123")
    page.query_selector("button[type='submit'], button:has-text('Login')").click()
    for _ in range(50):
        if "/login" not in page.url:
            break
        page.wait_for_timeout(300)


def capture(page, path, label):
    page.wait_for_timeout(2000)
    # wait for the admin users table to load
    for _ in range(30):
        if "Loading" not in page.inner_text("body"):
            break
        page.wait_for_timeout(400)
    page.screenshot(path=path, full_page=True)
    # sample muted-text color
    color_probe = page.evaluate("""
    () => {
      const pickSel = ['label', '.text-gray-500', '.text-gray-400', 'p'].join(',')
      const el = document.querySelector(pickSel)
      if (!el) return null
      const cs = getComputedStyle(el)
      return { tag: el.tagName, color: cs.color, bg: cs.backgroundColor, text: (el.textContent||'').slice(0,40) }
    }
    """)
    print(f"  [{label}] saved {path} — sample muted-text: {color_probe}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        print("[1] login")
        login(page)

        print("[2] navigate to /admin/users and wait for data")
        page.goto(f"{URL}/admin/users", wait_until="domcontentloaded", timeout=20000)
        # wait for the users table to have data (Loading... gone)
        for _ in range(60):
            if "Loading" not in page.inner_text("body"):
                break
            page.wait_for_timeout(500)

        # open the create form
        new_btn = page.query_selector("button:has-text('+ New user')")
        if new_btn:
            new_btn.click()
            page.wait_for_timeout(800)

        # LIGHT mode first (default). Ensure html has no 'dark' class.
        page.evaluate("() => document.documentElement.classList.remove('dark')")
        page.wait_for_timeout(600)
        capture(page, "admin_light.png", "LIGHT")

        # DARK mode: add class
        page.evaluate("() => document.documentElement.classList.add('dark')")
        page.wait_for_timeout(600)
        capture(page, "admin_dark.png", "DARK")

        browser.close()
    print("\n[DONE] compare admin_light.png vs admin_dark.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
