"""Render the generated HTML guide to PNG pages so we can visually compare
guide vs app screenshots without needing a backend running.

Output: docs/screenshots/guide_render/iterN/page_*.png
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent.parent
HTML = BASE / "docs" / "dpmbg_user_guide.html"
ITER = sys.argv[1] if len(sys.argv) > 1 else "iter1"
OUT = BASE / "docs" / "screenshots" / "guide_render" / ITER
OUT.mkdir(parents=True, exist_ok=True)


def main():
    if not HTML.exists():
        print(f"[ERR] {HTML} not found")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1100, "height": 1400},
                                  device_scale_factor=1.0)
        page = ctx.new_page()
        page.goto(f"file:///{HTML.as_posix()}", wait_until="networkidle")
        page.wait_for_timeout(800)

        chapters = page.locator(".chapter").all()
        print(f"Found {len(chapters)} chapter elements")
        for i, ch in enumerate(chapters):
            try:
                cid = ch.get_attribute("id") or f"ch{i}"
                ch.scroll_into_view_if_needed()
                page.wait_for_timeout(200)
                bb = ch.bounding_box()
                if not bb:
                    continue
                ch.screenshot(path=str(OUT / f"{cid}.png"))
                print(f"  [shot] {cid}.png  ({int(bb['height'])} px tall)")
            except Exception as e:
                print(f"  [skip] {cid}: {e}")

        page.screenshot(path=str(OUT / "full_page.png"), full_page=True)
        print(f"\n[OK] Rendered to {OUT}")
        browser.close()


if __name__ == "__main__":
    main()
