"""Shared Playwright helpers for building the DPMBG user guide (deterministic driving + screenshots)."""
import os
from playwright.sync_api import sync_playwright

BASE = os.getenv("GUIDE_BASE", "http://localhost:5173")
SHOTS = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "screenshots", "guide")


def login(page, username="admin", password="admin123"):
    page.goto(BASE + "/", wait_until="networkidle")
    page.fill('input[type="text"]', username)
    page.fill('input[type="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)


def shot(page, name):
    d = os.path.abspath(SHOTS)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name + ".png")
    page.screenshot(path=path, full_page=True)
    print("shot:", path)
    return path


def browser(headless=True):
    p = sync_playwright().start()
    b = p.chromium.launch(headless=headless)
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    return p, b, ctx
