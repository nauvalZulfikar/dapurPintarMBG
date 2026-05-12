"""Verify New User form in light + dark mode + loading state."""
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
    [el for el in inputs if el.get_attribute("type") != "password"][0].fill(user)
    [el for el in inputs if el.get_attribute("type") == "password"][0].fill(pw)
    page.query_selector("button[type='submit'], button:has-text('Login')").click()
    for _ in range(120):
        if "/login" not in page.url:
            return
        page.wait_for_timeout(300)
    raise RuntimeError(f"login stuck")


def open_form(page):
    page.goto(f"{URL}/admin/users", wait_until="domcontentloaded")
    _wait_loaded(page)
    page.click("button:has-text('+ New user')")
    page.wait_for_selector("[data-testid='create-user-form']", timeout=10000)
    page.wait_for_timeout(500)


def probe_input_color(page, selector_in_form: str, field_desc: str):
    el = page.locator("[data-testid='create-user-form']").locator(selector_in_form).first
    info = el.evaluate("""(n) => {
      const cs = getComputedStyle(n)
      return { color: cs.color, bg: cs.backgroundColor, name: n.tagName }
    }""")
    print(f"      {field_desc:20s}: fg={info['color']} bg={info['bg']}")


def main():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        print("[1] login + open New user form")
        login(page)
        open_form(page)
        # Type something so inputs have visible text
        form = page.locator("[data-testid='create-user-form']")
        form.locator("input:not([type='password'])").first.fill("contrast_probe_abc")
        form.locator("input[type='password']").first.fill("contrast_probe_123")

        # LIGHT mode probe
        print("\n[2] light mode — probe input computed colors")
        page.evaluate("() => document.documentElement.classList.remove('dark')")
        page.wait_for_timeout(400)
        probe_input_color(page, "input:not([type='password'])", "Username input")
        probe_input_color(page, "input[type='password']", "Password input")
        probe_input_color(page, "select", "Access select")
        page.screenshot(path="newuser_light.png", full_page=True)

        # DARK mode probe
        print("\n[3] dark mode — probe input computed colors")
        page.evaluate("() => document.documentElement.classList.add('dark')")
        page.wait_for_timeout(400)
        probe_input_color(page, "input:not([type='password'])", "Username input")
        probe_input_color(page, "input[type='password']", "Password input")
        probe_input_color(page, "select", "Access select")
        page.screenshot(path="newuser_dark.png", full_page=True)

        # Loading state probe
        print("\n[4] loading state — slow network simulation")
        page.evaluate("() => document.documentElement.classList.remove('dark')")
        # pick kitchen (required)
        selects = form.locator("select")
        kvals = [o.get_attribute("value") for o in selects.nth(1).locator("option").element_handles()]
        first_kid = next(v for v in kvals if v)
        selects.nth(1).select_option(value=first_kid)

        # throttle the POST response by intercepting
        ctx.route("**/api/admin/users", lambda r: (page.wait_for_timeout(200), r.continue_())[1])

        # Click Create, immediately check button state
        page.click("[data-testid='create-user-form'] button:has-text('Create user')")
        page.wait_for_timeout(150)
        body = page.inner_text("body")
        loading_visible = ("Creating" in body) or ("Membuat user" in body)
        print(f"    -> loading text visible: {loading_visible}")
        # spinner svg
        spinners = page.query_selector_all("[data-testid='create-user-form'] svg.animate-spin")
        print(f"    -> spinner svg count: {len(spinners)}")
        page.screenshot(path="newuser_loading.png", full_page=True)

        results["loading_text"] = loading_visible
        results["spinner"] = len(spinners) > 0
        results["light_shot"] = "newuser_light.png"
        results["dark_shot"] = "newuser_dark.png"

        # wait for form to close (user created)
        page.wait_for_timeout(3000)

        browser.close()

    print()
    print(f"loading indicator: {'✓' if results.get('loading_text') and results.get('spinner') else '✗'}")
    print("check screenshots: newuser_light.png, newuser_dark.png, newuser_loading.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
