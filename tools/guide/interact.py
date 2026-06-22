"""Phase 1b interaction pass: open each feature's tab-panels and modal/floating
windows, screenshot each state. SAFE — never clicks a mutating button (Submit,
Confirm Produksi, Optimasi, Scrape, Test Print, ✓OK, Delete, Deactivate). Create
modals are opened then closed via Escape WITHOUT submitting.

Run: GUIDE_BASE=http://localhost:5173 python tools/guide/interact.py
Outputs: docs/screenshots/guide/<slug>/NN-<state>.png
"""
import os
from _lib import browser, login, SHOTS

BASE = os.getenv("GUIDE_BASE", "http://localhost:5173")

# kind: "tab" = click + screenshot (stays on page) ; "modal" = click + screenshot + Escape
# (slug, route, [ (kind, button_text, shot_name) ... ])
PLAN = [
    ("executive", "/executive", [
        ("tab", "Per Dapur", "01-per-dapur"),
        ("tab", "Multi-SPPG", "02-multi-sppg"),
        ("tab", "Platform (Cross-Org)", "03-platform"),
    ]),
    ("menu-planner", "/menu-planner", [
        ("modal", "Atur AKG", "01-atur-akg"),
        ("modal", "Buka Tersimpan", "02-buka-tersimpan"),
    ]),
    ("menu-approval", "/menu-approval", [
        ("tab", "Nunggu Review", "01-nunggu-review"),
        ("tab", "Disetujui", "02-disetujui"),
        ("tab", "Ditolak", "03-ditolak"),
        ("tab", "Semua", "04-semua"),
    ]),
    ("nutrisi", "/nutrisi", [
        ("tab", "Laporan Harian", "01-laporan-harian"),
        ("tab", "AKG Tracker Mingguan", "02-akg-tracker"),
    ]),
    ("purchase-orders", "/purchase-orders", [
        ("tab", "sent", "01-filter-sent"),
        ("modal", "Detail", "02-detail"),
        ("modal", "PO Baru", "03-po-baru-modal"),
    ]),
    ("inspections", "/inspections", [
        ("tab", "accepted", "01-filter-accepted"),
        ("modal", "Mulai Inspeksi", "02-mulai-inspeksi-modal"),
    ]),
    ("receiving", "/receiving", [
        ("tab", "Bahan Masuk", "01-bahan-masuk"),
        ("tab", "Defect / Reject", "02-defect-reject"),
    ]),
    ("production", "/production", [
        ("modal", "Detail", "01-batch-detail"),
    ]),
    ("distributions", "/distributions", [
        ("tab", "Aggregate Hari Ini", "01-aggregate"),
        ("tab", "Wave 1 & 2", "02-wave"),
        ("tab", "Sisa Porsi", "03-sisa-porsi"),
        ("tab", "Vehicle & Driver", "04-vehicle-driver"),
    ]),
    ("aslap", "/aslap", [
        ("tab", "Checklist Hari Ini", "01-checklist"),
        ("tab", "Water Quality", "02-water-quality"),
        ("tab", "Production Obs", "03-production-obs"),
        ("tab", "Komunikasi Sekolah", "04-komunikasi"),
        ("tab", "Weekly Report", "05-weekly-report"),
    ]),
    ("finance", "/finance", [
        ("tab", "Cost-per-porsi", "01-cost-per-porsi"),
        ("tab", "Price Trends", "02-price-trends"),
        ("tab", "Spike Alerts", "03-spike-alerts"),
        ("tab", "Expense", "04-expense"),
        ("tab", "LRA Biweekly", "05-lra"),
        ("tab", "PO Generator", "06-po-generator"),
    ]),
    ("admin-schools", "/admin/schools", [
        ("modal", "Tambah Sekolah", "01-tambah-modal"),
    ]),
    ("admin-suppliers", "/admin/suppliers", [
        ("modal", "Tambah Supplier", "01-tambah-modal"),
    ]),
    ("admin-users", "/admin/users", [
        ("modal", "New user", "01-new-user-modal"),
    ]),
    ("admin-kitchens", "/admin/kitchens", [
        ("modal", "New kitchen", "01-new-kitchen-modal"),
    ]),
    ("admin-orgs", "/admin/organizations", [
        ("modal", "New organization", "01-new-org-modal"),
    ]),
]


def click_by_text(page, text):
    # try exact button role first, then substring locator, return True if clicked
    try:
        loc = page.get_by_role("button", name=text, exact=False).first
        if loc.count() and loc.is_visible():
            loc.click(timeout=4000)
            return True
    except Exception:
        pass
    try:
        loc = page.locator(f"button:has-text(\"{text}\")").first
        if loc.count() and loc.is_visible():
            loc.click(timeout=4000)
            return True
    except Exception:
        pass
    # tabs sometimes are <a> or <div role=tab>
    try:
        loc = page.get_by_text(text, exact=False).first
        if loc.count() and loc.is_visible():
            loc.click(timeout=4000)
            return True
    except Exception:
        pass
    return False


def main():
    p, b, ctx = browser(headless=True)
    page = ctx.new_page()
    login(page)
    for slug, route, steps in PLAN:
        d = os.path.abspath(os.path.join(SHOTS, slug))
        os.makedirs(d, exist_ok=True)
        for kind, text, name in steps:
            # re-navigate fresh before modal steps so prior filter state doesn't bleed
            page.goto(BASE + route, wait_until="networkidle", timeout=20000)
            page.wait_for_timeout(1300)
            ok = click_by_text(page, text)
            page.wait_for_timeout(1100)
            path = os.path.join(d, name + ".png")
            page.screenshot(path=path, full_page=True)
            status = "OK " if ok else "MISS"
            print(f"[{status}] {slug:16s} {kind:5s} '{text}' -> {name}.png")
            if kind == "modal":
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
    ctx.close(); b.close(); p.stop()


if __name__ == "__main__":
    main()
