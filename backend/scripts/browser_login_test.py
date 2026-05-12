"""Browser-based login test via Playwright."""
from playwright.sync_api import sync_playwright
import sys

URL = "http://localhost:5173"
USER = "admin"
PASS = "admin123"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)
        page.on("pageerror", lambda exc: console_errors.append(f"[pageerror] {exc}"))

        print(f"[1] navigating to {URL}")
        page.goto(URL, wait_until="networkidle", timeout=30000)
        print(f"    -> title='{page.title()}' url='{page.url}'")

        # screenshot the initial state
        page.screenshot(path="login_initial.png", full_page=True)

        # look for username/password fields
        print(f"[2] filling login form")
        # try common selectors
        u_sel = "input[name='username'], input[type='text']:visible, input[placeholder*='sername' i], input[placeholder*='ser' i]"
        p_sel = "input[name='password'], input[type='password']"

        page.wait_for_selector("input[type='password']", timeout=10000)
        inputs = page.query_selector_all("input")
        print(f"    -> found {len(inputs)} input elements")
        for i, el in enumerate(inputs):
            t = el.get_attribute("type") or "text"
            n = el.get_attribute("name") or ""
            ph = el.get_attribute("placeholder") or ""
            print(f"       [{i}] type={t} name={n} placeholder={ph!r}")

        # fill: first non-password text input = username, the password input = password
        text_inputs = [el for el in inputs if (el.get_attribute("type") or "text") != "password" and (el.get_attribute("type") or "text") != "hidden"]
        pass_inputs = [el for el in inputs if el.get_attribute("type") == "password"]
        if not text_inputs or not pass_inputs:
            print("[FAIL] could not find username/password inputs")
            page.screenshot(path="login_fail.png", full_page=True)
            browser.close()
            return 1

        text_inputs[0].fill(USER)
        pass_inputs[0].fill(PASS)
        print(f"    -> filled: username={USER!r} password=***")

        # submit — click button or press Enter
        print(f"[3] submitting")
        btn = page.query_selector("button[type='submit'], button:has-text('Login'), button:has-text('Sign in'), button:has-text('Masuk')")
        if btn:
            btn.click()
        else:
            pass_inputs[0].press("Enter")

        # wait for navigation away from /login
        try:
            page.wait_for_url(lambda u: "/login" not in u, timeout=20000)
        except Exception as e:
            print(f"    -> wait_for_url timeout: {e}")

        page.wait_for_load_state("networkidle", timeout=20000)
        page.wait_for_timeout(1500)  # extra settle
        final_url = page.url
        final_title = page.title()
        print(f"    -> after submit: url='{final_url}' title='{final_title}'")

        page.screenshot(path="login_after.png", full_page=True)

        # read localStorage for token
        token = page.evaluate("() => localStorage.getItem('token') || localStorage.getItem('access_token') || localStorage.getItem('auth_token')")
        print(f"    -> localStorage token present: {bool(token)} (len={len(token) if token else 0})")

        # body text check
        body_text = page.inner_text("body")[:500]
        print(f"    -> body sample: {body_text!r}")

        # check for error banner
        err_el = page.query_selector("[role='alert'], .error, .text-red-500, .text-red-600")
        if err_el:
            err_text = err_el.inner_text()
            print(f"    -> ERROR BANNER: {err_text!r}")

        if console_errors:
            print(f"[console] {len(console_errors)} msg(s):")
            for e in console_errors[:10]:
                print(f"   {e}")

        # success heuristic: URL changed from "/" or "/login", AND token present
        success = bool(token) and ("login" not in final_url.lower())
        print()
        if success:
            print("===== LOGIN SUCCESS =====")
            browser.close()
            return 0
        else:
            print("===== LOGIN FAILED =====")
            browser.close()
            return 1


if __name__ == "__main__":
    sys.exit(run())
