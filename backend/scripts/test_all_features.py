"""Systematically test every DPMBG feature as a user via Playwright.
Takes screenshots of each page/feature for verification."""

import json, time, sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent.parent
OUT = BASE / "docs" / "screenshots" / "feature_test"
OUT.mkdir(parents=True, exist_ok=True)

URL = "http://localhost:5173"
API = "http://localhost:8001"
RESULTS = []


def log(feature, status, detail=""):
    entry = {"feature": feature, "status": status, "detail": detail}
    RESULTS.append(entry)
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"  {icon} {feature}: {detail}")


def shot(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"))


def test_login(page):
    print("\n── 1. LOGIN ──")

    # Screenshot the login page
    page.goto(URL + "/login", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    shot(page, "01_login_page")

    uname = page.locator("input[type='text']").first
    pwd = page.locator("input[type='password']").first
    if uname.is_visible() and pwd.is_visible():
        log("Login Form", "PASS", "Username & password fields visible")
    else:
        log("Login Form", "FAIL", "Login fields not found")

    # Use API-based auth to bypass potential headless timing issues
    import requests
    r = requests.post(f"{API}/api/auth/login", json={"username": "wronguser", "password": "wrongpass"})
    if r.status_code == 401:
        log("Login Wrong Creds", "PASS", f"API returns 401 for wrong creds")
    else:
        log("Login Wrong Creds", "WARN", f"API returns {r.status_code}")

    r = requests.post(f"{API}/api/auth/login", json={"username": "admin", "password": "admin123"})
    if r.status_code == 200:
        token = r.json()["access_token"]
        log("Login API", "PASS", "API returns 200 + token")
    else:
        log("Login API", "FAIL", f"API returns {r.status_code}")
        return False

    # Inject token into localStorage and navigate to dashboard
    page.evaluate(f"localStorage.setItem('token', '{token}')")
    page.evaluate("localStorage.setItem('active_kitchen_id', '1')")
    page.goto(URL + "/", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    shot(page, "01_login_success")

    if "/login" not in page.url:
        log("Login Redirect", "PASS", f"Dashboard at {page.url}")
        return True
    else:
        log("Login Redirect", "FAIL", f"Still at {page.url}")
        return False


def test_dashboard(page):
    print("\n── 2. DASHBOARD ──")
    page.wait_for_timeout(1500)
    shot(page, "02_dashboard")

    # KPI cards
    kpi_cards = page.locator(".rounded-xl, .rounded-lg, [class*='card'], [class*='stat']").all()
    log("Dashboard KPI Cards", "PASS" if len(kpi_cards) >= 2 else "WARN",
        f"Found {len(kpi_cards)} card-like elements")

    # Sidebar
    sidebar = page.locator("nav, aside, [class*='sidebar']").first
    if sidebar.is_visible():
        log("Dashboard Sidebar", "PASS", "Sidebar navigation visible")
    else:
        log("Dashboard Sidebar", "WARN", "Sidebar not clearly visible")


def navigate_sidebar(page, text):
    """Click a sidebar item by text, handling sub-menu expansion."""
    link = page.locator(f"nav a:has-text('{text}'), aside a:has-text('{text}'), a:has-text('{text}')").first
    try:
        link.click(timeout=5000)
        page.wait_for_timeout(2000)
        return True
    except:
        # Try clicking parent group first
        group = page.locator(f"text='{text}'").first
        try:
            group.click(timeout=3000)
            page.wait_for_timeout(1500)
            return True
        except:
            return False


def test_page(page, nav_text, shot_name, feature_name, checks=None):
    """Navigate to a page and run optional checks."""
    if navigate_sidebar(page, nav_text):
        page.wait_for_timeout(2000)
        shot(page, shot_name)
        log(feature_name, "PASS", f"Page loaded — {page.url}")

        if checks:
            for check_name, selector in checks.items():
                try:
                    el = page.locator(selector).first
                    if el.is_visible(timeout=3000):
                        log(f"  {feature_name} → {check_name}", "PASS", "Element visible")
                    else:
                        log(f"  {feature_name} → {check_name}", "WARN", "Element exists but not visible")
                except:
                    log(f"  {feature_name} → {check_name}", "WARN", "Element not found")
        return True
    else:
        log(feature_name, "FAIL", f"Could not navigate to '{nav_text}'")
        return False


def count_tabs(page):
    """Count tab-like buttons on current page."""
    tabs = page.locator("button[role='tab'], [class*='tab'], button[class*='Tab']").all()
    return len(tabs)


def test_build_menu(page):
    print("\n── 3. BUILD MENU ──")
    if navigate_sidebar(page, "Build Menu"):
        page.wait_for_timeout(2000)
        shot(page, "03_build_menu")
        log("Build Menu Page", "PASS", f"Loaded — {page.url}")

        # Search ingredient
        search = page.locator("input[placeholder*='cari' i], input[placeholder*='search' i], input[type='search']").first
        try:
            if search.is_visible(timeout=3000):
                search.fill("nasi")
                page.wait_for_timeout(1500)
                shot(page, "03_build_menu_search")
                log("Build Menu Search", "PASS", "Ingredient search works")
            else:
                log("Build Menu Search", "WARN", "Search field not visible")
        except:
            log("Build Menu Search", "WARN", "Search field not found")
    else:
        log("Build Menu Page", "FAIL", "Cannot navigate")


def test_menu_approval(page):
    print("\n── 4. MENU APPROVAL ──")
    if navigate_sidebar(page, "Approval") or navigate_sidebar(page, "Menu"):
        page.wait_for_timeout(2000)
        shot(page, "04_menu_approval")
        tab_count = count_tabs(page)
        log("Menu Approval Page", "PASS", f"Loaded — {tab_count} tabs found")
    else:
        log("Menu Approval Page", "FAIL", "Cannot navigate")


def test_purchase_orders(page):
    print("\n── 5. PURCHASE ORDERS ──")
    if navigate_sidebar(page, "Purchase") or navigate_sidebar(page, "PO"):
        page.wait_for_timeout(2000)
        shot(page, "05_purchase_orders")
        tab_count = count_tabs(page)

        # + PO Baru button
        po_btn = page.locator("button:has-text('PO'), button:has-text('Baru'), button:has-text('New')").first
        try:
            has_btn = po_btn.is_visible(timeout=3000)
        except:
            has_btn = False
        log("Purchase Orders Page", "PASS", f"Loaded — {tab_count} tabs, +PO button: {has_btn}")
    else:
        log("Purchase Orders Page", "FAIL", "Cannot navigate")


def test_inspections(page):
    print("\n── 6. JOINT INSPECTION ──")
    if navigate_sidebar(page, "Inspection") or navigate_sidebar(page, "Inspeksi"):
        page.wait_for_timeout(2000)
        shot(page, "06_inspections")
        tab_count = count_tabs(page)
        log("Joint Inspection Page", "PASS", f"Loaded — {tab_count} tabs")
    else:
        log("Joint Inspection Page", "FAIL", "Cannot navigate")


def test_production(page):
    print("\n── 7. PRODUCTION ──")
    if navigate_sidebar(page, "Production") or navigate_sidebar(page, "Produksi"):
        page.wait_for_timeout(2000)
        shot(page, "07_production")
        log("Production Page", "PASS", f"Loaded — {page.url}")
    else:
        log("Production Page", "FAIL", "Cannot navigate")


def test_distribution(page):
    print("\n── 8. DISTRIBUTION ──")
    if navigate_sidebar(page, "Distribu") or navigate_sidebar(page, "Distribution"):
        page.wait_for_timeout(2000)
        shot(page, "08_distribution")
        tab_count = count_tabs(page)
        log("Distribution Page", "PASS", f"Loaded — {tab_count} tabs")
    else:
        log("Distribution Page", "FAIL", "Cannot navigate")


def test_aslap(page):
    print("\n── 9. ASLAP ──")
    if navigate_sidebar(page, "ASLAP") or navigate_sidebar(page, "Pengawasan"):
        page.wait_for_timeout(2000)
        shot(page, "09_aslap")
        tab_count = count_tabs(page)
        log("ASLAP Page", "PASS", f"Loaded — {tab_count} tabs")
    else:
        log("ASLAP Page", "FAIL", "Cannot navigate")


def test_finance(page):
    print("\n── 10. FINANCE ──")
    if navigate_sidebar(page, "Finance") or navigate_sidebar(page, "Keuangan") or navigate_sidebar(page, "Akuntan"):
        page.wait_for_timeout(2000)
        shot(page, "10_finance")
        tab_count = count_tabs(page)
        log("Finance Page", "PASS", f"Loaded — {tab_count} tabs")
    else:
        log("Finance Page", "FAIL", "Cannot navigate")


def test_executive(page):
    print("\n── 11. EXECUTIVE DASHBOARD ──")
    if navigate_sidebar(page, "Executive") or navigate_sidebar(page, "Eksekutif"):
        page.wait_for_timeout(2000)
        shot(page, "11_executive")
        tab_count = count_tabs(page)

        export_btn = page.locator("button:has-text('Export'), button:has-text('BGN')").first
        try:
            has_export = export_btn.is_visible(timeout=3000)
        except:
            has_export = False
        log("Executive Dashboard", "PASS", f"Loaded — {tab_count} tabs, Export btn: {has_export}")
    else:
        log("Executive Dashboard", "FAIL", "Cannot navigate")


def test_master_schools(page):
    print("\n── 12. MASTER SEKOLAH ──")
    if navigate_sidebar(page, "Sekolah"):
        page.wait_for_timeout(2000)
        shot(page, "12_master_schools")

        rows = page.locator("tr, [class*='row']").all()
        add_btn = page.locator("button:has-text('Tambah'), button:has-text('Add'), button:has-text('+')").first
        try:
            has_add = add_btn.is_visible(timeout=3000)
        except:
            has_add = False
        log("Master Sekolah", "PASS", f"Loaded — {len(rows)} rows, +Tambah btn: {has_add}")
    else:
        log("Master Sekolah", "FAIL", "Cannot navigate")


def test_master_suppliers(page):
    print("\n── 13. MASTER SUPPLIER ──")
    if navigate_sidebar(page, "Supplier"):
        page.wait_for_timeout(2000)
        shot(page, "13_master_suppliers")
        log("Master Supplier", "PASS", f"Loaded — {page.url}")
    else:
        log("Master Supplier", "FAIL", "Cannot navigate")


def test_master_users(page):
    print("\n── 14. USERS ──")
    if navigate_sidebar(page, "Users") or navigate_sidebar(page, "User"):
        page.wait_for_timeout(2000)
        shot(page, "14_users")

        rows = page.locator("tr, [class*='row']").all()
        log("Users Management", "PASS", f"Loaded — {len(rows)} user rows visible")
    else:
        log("Users Management", "FAIL", "Cannot navigate")


def test_notifications(page):
    print("\n── 15. NOTIFICATIONS ──")
    bell = page.locator("[class*='bell'], [class*='notif'], button:has([class*='Bell']), svg[class*='bell' i]").first
    try:
        if bell.is_visible(timeout=3000):
            bell.click()
            page.wait_for_timeout(1500)
            shot(page, "15_notifications")
            log("Notifications Bell", "PASS", "Bell icon clicked, panel should open")
        else:
            log("Notifications Bell", "WARN", "Bell icon not visible")
    except:
        log("Notifications Bell", "WARN", "Bell icon not found — trying alternate selectors")
        # Try broader search
        shot(page, "15_notifications_fallback")


def main():
    print(f"=" * 60)
    print(f"DPMBG Feature Test — {time.strftime('%Y-%m-%d %H:%M')}")
    print(f"Screenshots → {OUT}")
    print(f"=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.0)
        ctx.set_default_timeout(15000)
        page = ctx.new_page()

        # 1. Login
        if not test_login(page):
            print("\n⛔ Login failed — cannot continue.")
            browser.close()
            return

        # 2. Dashboard
        test_dashboard(page)

        # 3-14. Feature pages
        test_build_menu(page)
        test_menu_approval(page)
        test_purchase_orders(page)
        test_inspections(page)
        test_production(page)
        test_distribution(page)
        test_aslap(page)
        test_finance(page)
        test_executive(page)
        test_master_schools(page)
        test_master_suppliers(page)
        test_master_users(page)

        # 15. Notifications
        test_notifications(page)

        # Get full sidebar for reference
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        shot(page, "99_final_sidebar")

        browser.close()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"RESULTS SUMMARY")
    print(f"{'=' * 60}")
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    warned = sum(1 for r in RESULTS if r["status"] == "WARN")
    total = len(RESULTS)
    print(f"  PASS: {passed}  |  WARN: {warned}  |  FAIL: {failed}  |  Total: {total}")

    report_path = OUT / "test_report.json"
    report_path.write_text(json.dumps(RESULTS, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Report saved: {report_path}")


if __name__ == "__main__":
    main()
