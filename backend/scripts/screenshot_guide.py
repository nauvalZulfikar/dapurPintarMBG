#!/usr/bin/env python3
"""
Take screenshots of all DPMBG pages for the user guide.
Saves PNGs to docs/screenshots/guide/ then regenerates dpmbg_user_guide.html
with real screenshots embedded as base64.
"""
import base64, io, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page
from PIL import Image

BASE_URL  = "http://localhost:5173"
PROD_URL  = "dapurpintarmbg.com"
CREDS     = {"username": "admin", "password": "admin123"}
OUT_DIR   = Path(__file__).resolve().parent.parent.parent / "docs" / "screenshots" / "guide"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SCALE     = 1.5   # device_scale_factor — multiply CSS px to get screenshot px

SHOTS: dict[str, bytes] = {}   # name -> PNG bytes

# ─── Per-page crop target: first selector that resolves to a large-enough box wins ──
# Pages not listed fall back to DEFAULT_CROP_SELECTORS (main content area).
FOCUS_SELECTORS: dict[str, list[str]] = {
    "login": ["form", "[class*='login']", "[class*='card']", "[class*='Card']"],
    # Full-page shots — show everything (no crop)
    "dashboard":      [],
    "notifications":  [],
}
DEFAULT_CROP_SELECTORS = [
    "main",
    "[role='main']",
    "[class*='main-content']",
    "[class*='MainContent']",
    "[class*='content-area']",
]


def crop_to_box(png_bytes: bytes, bb: dict, pad_css: int = 32) -> bytes:
    """Crop a screenshot to a CSS-pixel bounding box with padding."""
    try:
        img = Image.open(io.BytesIO(png_bytes))
        x = max(0, int((bb["x"] - pad_css) * SCALE))
        y = max(0, int((bb["y"] - pad_css) * SCALE))
        r = min(img.width,  int((bb["x"] + bb["width"]  + pad_css) * SCALE))
        b = min(img.height, int((bb["y"] + bb["height"] + pad_css) * SCALE))
        if r - x < 200 or b - y < 120:   # too small — skip crop
            return png_bytes
        cropped = img.crop((x, y, r, b))
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        print(f"  [warn] crop failed: {e}")
        return png_bytes


def try_crop(page: Page, name: str, png_bytes: bytes) -> bytes:
    """Try to crop the screenshot to the page's focal element."""
    selectors = FOCUS_SELECTORS.get(name, DEFAULT_CROP_SELECTORS)
    if not selectors:
        return png_bytes   # explicit empty list = no crop
    for sel in selectors:
        try:
            bb = page.locator(sel).first.bounding_box(timeout=1500)
            if bb and bb["width"] > 150 and bb["height"] > 100:
                cropped = crop_to_box(png_bytes, bb)
                if cropped is not png_bytes:
                    print(f"  [crop] {name}: {sel}")
                return cropped
        except Exception:
            continue
    return png_bytes

def b64(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode()

BACKEND_URL = "http://127.0.0.1:8001"  # explicit IPv4 — avoids ::1 resolution issues

def get_token() -> str:
    """Fetch JWT token directly from the API — avoids React synthetic event issues in headless."""
    import urllib.request, json as _json
    body = _json.dumps(CREDS).encode()
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = _json.loads(resp.read())
    return data["access_token"]

def get_kitchen_id(token: str) -> int:
    """Get the first kitchen ID for this user."""
    import urllib.request, json as _json
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as resp:
        data = _json.loads(resp.read())
    kitchens = data.get("kitchens", [])
    return kitchens[0]["id"] if kitchens else 1

ME_MOCK = {
    "id": 1, "username": "admin", "role": "platform_admin", "org_id": 1,
    "active_kitchen_id": 1,
    "kitchens": [{"id": 1, "name": "SPPG Paseh", "org_id": 1}],
    "permissions": [
        "dashboard.view","items.view","items.create","items.edit","trays.view",
        "menu.view","menu.optimize","menu.scrape","menu.save","foods.edit",
        "nutrition.report","prices.override","prices.history","reports.variance",
        "scan_errors.view","export.daily","export.range","admin.kitchens","admin.users",
        "school.view","school.manage","supplier.view","supplier.manage",
        "menu.calc","menu.build_manual","menu.submit_for_review","menu.approve",
        "menu.lock","menu.cycle_check","menu.forecast",
        "student_request.view","student_request.create","student_request.resolve",
        "po.view","po.create","po.edit","po.delete",
        "inspection.view","inspection.create","inspection.signoff_quality",
        "inspection.signoff_quantity","inspection.signoff_physical",
        "inspection.reject_bahan","inspection.finalize","container.split",
        "dispute.view","dispute.resolve",
        "production.view","production.start_batch","production.end_batch",
        "production.processing_scan","production.qc_approve",
        "sample.view","sample.manage",
        "distribution.view","distribution.dispatch","distribution.leftover",
        "vehicle.manage","driver.manage",
        "finance.view","finance.price_trends","expense.view","expense.create",
        "expense.edit","volunteer.manage","lra.view","lra.generate","lra.signoff",
        "checklist.view","checklist.daily","checklist.template_manage",
        "water_quality.view","water_quality.log",
        "production_observation.view","production_observation.create",
        "school_comm_log.view","school_comm_log.create",
        "aslap_report.view","aslap_report.generate","aslap_report.signoff",
        "notification.view","notification.subscribe",
        "executive.kpi_view","compliance.bundle_export",
    ],
}


SCHOOLS_MOCK = {"schools": [
    {"id":i,"school_id":i,"name":n,"level":lv,"age_group":ag,"student_count":sc,
     "distance":d,"contact":None,"address":None,"gps_lat":None,"gps_long":None,"is_active":True,"created_at":"2026-04-01T00:00:00"}
    for i,n,lv,ag,sc,d in [
        (1,"SDN Paseh 1","SD","SD Kelas 1-6 (6-12 tahun)",240,500),
        (2,"RA Darul Jadid","TK","TK (4-6 tahun)",26,400),
        (3,"SDN Mekarsari","SD","SD Kelas 1-6 (6-12 tahun)",185,800),
        (4,"SDN Cikopo","SD","SD Kelas 1-6 (6-12 tahun)",195,1200),
        (5,"TK Bina Bangsa","TK","TK (4-6 tahun)",60,350),
        (6,"PAUD Melati","PAUD","PAUD (3-4 tahun)",40,200),
        (7,"SDN Bojong","SD","SD Kelas 1-6 (6-12 tahun)",170,1500),
        (8,"SDN Cianten","SD","SD Kelas 1-6 (6-12 tahun)",155,900),
        (9,"SDN Sukamaju","SD","SD Kelas 1-6 (6-12 tahun)",200,700),
        (10,"SDN Cimaung","SD","SD Kelas 1-6 (6-12 tahun)",165,1100),
        (11,"SMPN 1 Paseh","SMP","SMP (12-15 tahun)",320,600),
    ]
]}

SUPPLIERS_MOCK = {"suppliers": [
    {"id":1,"name":"UD Sumber Tani","contact":"0812-3456-7890","kategori":"bahan_pokok","rating":4,"npwp":None,"rekening":None,"bank_name":None,"notes":None,"is_active":True,"created_at":"2026-04-01T00:00:00"},
    {"id":2,"name":"CV Berkah Jaya","contact":"0821-9876-5432","kategori":"sayuran","rating":4,"npwp":None,"rekening":None,"bank_name":None,"notes":None,"is_active":True,"created_at":"2026-04-01T00:00:00"},
    {"id":3,"name":"PT Fresh Protein","contact":"0813-1111-2222","kategori":"ayam","rating":3,"npwp":None,"rekening":None,"bank_name":None,"notes":None,"is_active":True,"created_at":"2026-04-01T00:00:00"},
    {"id":4,"name":"UD Sari Laut","contact":"0811-5555-6666","kategori":"ikan","rating":4,"npwp":None,"rekening":None,"bank_name":None,"notes":None,"is_active":True,"created_at":"2026-04-01T00:00:00"},
]}

USERS_MOCK = {"users": [
    {"id":1,"username":"admin","role":"platform_admin","org_id":1,"created_at":"2026-03-01T00:00:00","kitchens":[{"kitchen_id":1,"role":"admin","name":"SPPG Paseh","slug":"paseh"}]},
    {"id":2,"username":"bu_ratih","role":"nutritionist","org_id":1,"created_at":"2026-03-01T00:00:00","kitchens":[{"kitchen_id":1,"role":"nutritionist","name":"SPPG Paseh","slug":"paseh"}]},
    {"id":3,"username":"pak_dedi","role":"accountant","org_id":1,"created_at":"2026-03-01T00:00:00","kitchens":[{"kitchen_id":1,"role":"accountant","name":"SPPG Paseh","slug":"paseh"}]},
    {"id":4,"username":"mas_toni","role":"aslap","org_id":1,"created_at":"2026-03-01T00:00:00","kitchens":[{"kitchen_id":1,"role":"aslap","name":"SPPG Paseh","slug":"paseh"}]},
    {"id":5,"username":"mas_andre","role":"head_kitchen","org_id":1,"created_at":"2026-03-01T00:00:00","kitchens":[{"kitchen_id":1,"role":"head_kitchen","name":"SPPG Paseh","slug":"paseh"}]},
]}

KITCHENS_MOCK = {"kitchens": [
    {"id":1,"name":"SPPG Paseh","slug":"paseh","org_id":1,"active":True,
     "scanner_key":"demo_key","cloud_print_key":"demo_print","label_title":"SPPG Paseh",
     "created_at":"2026-03-01T00:00:00"},
]}


def setup_auth_mock(page: Page, token: str):
    """Intercept /api/auth/me and master-data endpoints so pages load instantly."""
    import json as _json

    def handle_me(route):
        route.fulfill(status=200, content_type="application/json", body=_json.dumps(ME_MOCK))

    def handle_schools(route):
        route.fulfill(status=200, content_type="application/json", body=_json.dumps(SCHOOLS_MOCK))

    def handle_suppliers(route):
        route.fulfill(status=200, content_type="application/json", body=_json.dumps(SUPPLIERS_MOCK))

    def handle_users(route):
        route.fulfill(status=200, content_type="application/json", body=_json.dumps(USERS_MOCK))

    def handle_kitchens(route):
        route.fulfill(status=200, content_type="application/json", body=_json.dumps(KITCHENS_MOCK))

    page.route("**/api/auth/me**", handle_me)
    page.route("**/api/admin/schools**", handle_schools)
    page.route("**/api/admin/users**", handle_users)
    page.route("**/api/admin/kitchens**", handle_kitchens)


def wait_for_loaded(page: Page):
    """Wait for Loading... to disappear then extra buffer."""
    try:
        page.wait_for_selector("text=Loading...", state="hidden", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(1800)


def login(page: Page, token: str, kitchen_id: int):
    """Inject token + mock /me endpoint so auth resolves without network call."""
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    # Set token in localStorage
    page.evaluate("""([tok, kid]) => {
        localStorage.setItem('token', tok);
        localStorage.setItem('active_kitchen_id', String(kid));
    }""", [token, kitchen_id])
    # Set up route mock BEFORE navigating so it catches the /me call on mount
    setup_auth_mock(page, token)
    page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
    wait_for_loaded(page)


def goto_page(page: Page, url: str, extra_ms: int = 1200):
    """Navigate and wait for content to appear. Falls back to load event on timeout."""
    try:
        page.goto(f"{BASE_URL}{url}", wait_until="domcontentloaded", timeout=25000)
    except Exception:
        try:
            page.goto(f"{BASE_URL}{url}", wait_until="load", timeout=20000)
        except Exception:
            pass
    wait_for_loaded(page)
    page.wait_for_timeout(extra_ms)

def shot(page: Page, name: str, wait_ms: int = 800) -> bytes:
    page.wait_for_timeout(wait_ms)
    try:
        page.evaluate("document.querySelectorAll('[data-tooltip],[title]').forEach(e=>e.removeAttribute('title'))")
    except Exception:
        pass
    data = page.screenshot(full_page=False, type="png")
    data = try_crop(page, name, data)
    SHOTS[name] = data
    (OUT_DIR / f"{name}.png").write_bytes(data)
    print(f"  [shot] {name}.png  ({len(data)//1024} KB)")
    return data

def expand_sidebar_group(page: Page, text: str):
    """Click a sidebar group heading to expand it if collapsed."""
    try:
        el = page.locator(f"text={text}").first
        el.click(timeout=2000)
        page.wait_for_timeout(300)
    except Exception:
        pass

def goto_sidebar(page: Page, group_text: str, link_text: str, fallback_url: str = ""):
    """Expand sidebar group then click link."""
    try:
        expand_sidebar_group(page, group_text)
        page.locator(f"text={link_text}").first.click(timeout=3000)
        page.wait_for_load_state("networkidle")
    except Exception:
        if fallback_url:
            page.goto(f"{BASE_URL}{fallback_url}", wait_until="domcontentloaded")

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=1.5,
            service_workers="block",   # prevent PWA SW from intercepting /api/ fetches
        )
        page = ctx.new_page()

        print("Getting token from API...")
        token = get_token()
        kitchen_id = get_kitchen_id(token)
        print(f"  token OK, kitchen_id={kitchen_id}")

        # ── 2. Login page (unauthenticated context) ──────────────────────────
        print("Login page...")
        ctx2 = browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1.5)
        p2 = ctx2.new_page()
        p2.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        p2.wait_for_timeout(600)
        shot(p2, "login")
        ctx2.close()

        print("Logging in (token inject)...")
        login(page, token, kitchen_id)

        # ── 1. Dashboard ────────────────────────────────────────────────────
        print("Shooting dashboard...")
        goto_page(page, "/")
        shot(page, "dashboard")

        # ── 3. Notifications bell ───────────────────────────────────────────
        print("Notifications...")
        goto_page(page, "/")
        try:
            # Click the bell button — try several selectors
            for sel in ['button[aria-label*="notif"]', 'button:has([class*="bell"])',
                        '[class*="NotificationBell"] button', 'header button']:
                try:
                    page.locator(sel).first.click(timeout=1500)
                    page.wait_for_timeout(800)
                    break
                except Exception:
                    continue
        except Exception:
            pass
        shot(page, "notifications")

        # ── 4. Build Menu Manual ────────────────────────────────────────────
        print("Build Menu Manual...")
        goto_page(page, "/menu-manual")
        shot(page, "menu_build")

        # ── 5. Menu Approval ────────────────────────────────────────────────
        print("Menu Approval...")
        goto_page(page, "/menu-approval")
        shot(page, "menu_approval")

        # ── 6. Nutrition Report (student_requests route doesn't exist — use nutrisi) ─
        print("Nutrition Report...")
        goto_page(page, "/nutrisi")
        shot(page, "nutrition_report")

        # ── 7. Purchase Orders ──────────────────────────────────────────────
        print("Purchase Orders...")
        goto_page(page, "/purchase-orders")
        shot(page, "purchase_orders")

        # ── 8. Inspections ──────────────────────────────────────────────────
        print("Inspections...")
        goto_page(page, "/inspections")
        shot(page, "inspections")

        # ── 9. Production ───────────────────────────────────────────────────
        print("Production...")
        goto_page(page, "/production")
        shot(page, "production")

        # ── 10. Distributions ───────────────────────────────────────────────
        print("Distributions...")
        goto_page(page, "/distributions")
        shot(page, "distributions")

        # ── 11. ASLAP ───────────────────────────────────────────────────────
        print("ASLAP...")
        goto_page(page, "/aslap")
        shot(page, "aslap")

        # ── 12. Finance ─────────────────────────────────────────────────────
        print("Finance...")
        goto_page(page, "/finance")
        shot(page, "finance")

        # ── 13. Executive — click "Per Dapur" tab for KPI data ─────────────
        print("Executive...")
        goto_page(page, "/executive")
        try:
            page.locator("text=Per Dapur").first.click(timeout=3000)
            page.wait_for_timeout(3000)
        except Exception:
            pass
        shot(page, "executive")

        # ── 14-16. Admin pages — fresh context each to avoid accumulated state ───
        for pg_name, pg_url in [("admin_schools","/admin/schools"),
                                 ("admin_suppliers","/admin/suppliers"),
                                 ("admin_users","/admin/users")]:
            print(f"{pg_name}...")
            adm_ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                device_scale_factor=1.5,
                service_workers="block",
            )
            adm_page = adm_ctx.new_page()
            try:
                adm_page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=15000)
                adm_page.evaluate("""([tok, kid]) => {
                    localStorage.setItem('token', tok);
                    localStorage.setItem('active_kitchen_id', String(kid));
                }""", [token, kitchen_id])
                setup_auth_mock(adm_page, token)
                adm_page.goto(f"{BASE_URL}{pg_url}", wait_until="domcontentloaded", timeout=25000)
                try:
                    adm_page.wait_for_load_state("networkidle", timeout=12000)
                except Exception:
                    pass
                try:
                    adm_page.wait_for_selector("table, h1, h2, [class*='title']", timeout=8000)
                except Exception:
                    pass
                adm_page.wait_for_timeout(1500)
                shot(adm_page, pg_name)
            except Exception as e:
                print(f"  [skip] {pg_name}: {e}")
            finally:
                adm_ctx.close()

        browser.close()

    print(f"\n[OK] {len(SHOTS)} screenshots saved to {OUT_DIR}")
    return SHOTS

if __name__ == "__main__":
    shots = run()
    print("\nBuilding guide with real screenshots...")

    # Import and patch the guide generator
    sys.path.insert(0, str(Path(__file__).parent))

    # Build base64 map
    shot_b64 = {k: b64(v) for k, v in shots.items()}

    def img_tag(name: str, alt: str = "", caption: str = "") -> str:
        src = shot_b64.get(name, "")
        if not src:
            return f'<div style="background:#F3F4F6;border:1px dashed #D1D5DB;border-radius:8px;padding:20px;text-align:center;color:#6B7280;font-size:0.85rem">Screenshot: {name}</div>'
        cap = f'<p style="text-align:center;font-size:0.75rem;color:#6B7280;margin-top:6px;font-style:italic">{caption}</p>' if caption else ""
        return (
            f'<div style="margin:16px 0;border-radius:10px;overflow:hidden;'
            f'box-shadow:0 4px 16px rgba(0,0,0,.12);border:1px solid #E5E7EB">'
            f'<div style="background:#1E3A8A;padding:7px 14px;display:flex;align-items:center;gap:8px">'
            f'<span style="display:flex;gap:5px"><span style="width:11px;height:11px;border-radius:50%;background:#FF5F56;display:inline-block"></span>'
            f'<span style="width:11px;height:11px;border-radius:50%;background:#FFBD2E;display:inline-block"></span>'
            f'<span style="width:11px;height:11px;border-radius:50%;background:#27C93F;display:inline-block"></span></span>'
            f'<span style="background:rgba(255,255,255,.15);border-radius:4px;padding:2px 10px;'
            f'font-size:0.72rem;color:rgba(255,255,255,.85);font-family:monospace">'
            f'{PROD_URL}</span></div>'
            f'<img src="{src}" alt="{alt}" style="width:100%;display:block"/>'
            f'</div>{cap}'
        )

    import re, generate_user_guide as gg

    html = gg.build_html()
    html = html.replace("localhost:5173", PROD_URL)

    # Replace every <!-- SHOT:name --> marker with a real screenshot img_tag
    def _replace_shot(m):
        name = m.group(1)
        captions = {
            "login":          "Halaman Login DPMBG",
            "dashboard":      "Dashboard utama DPMBG",
            "notifications":  "Panel notifikasi real-time",
            "menu_build":     "Build Menu Manual — input bahan TKPI",
            "menu_approval":  "Alur persetujuan menu",
            "purchase_orders":"Daftar Purchase Orders",
            "inspections":    "Halaman Inspeksi Bersama",
            "production":     "Produksi Batch & QR Scan",
            "distributions":  "Sistem Gelombang Distribusi",
            "aslap":          "Dasbor ASLAP — 5 tab pengawasan",
            "finance":        "Modul Keuangan — Expense & LRA",
            "executive":      "Dashboard Eksekutif — KPI & Compliance",
            "admin_schools":  "Manajemen Data Sekolah",
            "admin_suppliers":"Manajemen Supplier",
            "admin_users":    "Manajemen Pengguna & Role",
            "nutrition_report":"Laporan Nutrisi",
        }
        cap = captions.get(name, name)
        return img_tag(name, cap, cap)
    html = re.sub(r'<!-- SHOT:(\w+) -->', _replace_shot, html)

    # Inject real screenshots before each relevant chapter section
    INJECT_MAP = {
        'id="ch2"': ("login",    "Halaman Login DPMBG"),
        'id="ch3"': ("notifications", "Panel notifikasi dengan unread badge"),
        'id="ch4"': ("menu_build",    "Build Menu Manual — input bahan TKPI"),
        'id="ch5"': ("menu_approval", "Halaman Menu Approval — queue pending review"),
        'id="ch6"': ("purchase_orders", "Daftar Purchase Orders"),
        'id="ch7"': ("inspections",   "Halaman Inspeksi Bersama"),
        'id="ch8"': ("production",    "Halaman Produksi Batch"),
        'id="ch9"': ("distributions", "Halaman Distribusi Makanan"),
        'id="ch10"': ("aslap",        "Dasbor ASLAP — 5 tab pengawasan lapangan"),
        'id="ch11"': ("finance",      "Modul Keuangan — Expense & LRA"),
        'id="ch12"': ("executive",    "Dashboard Eksekutif — KPI & Compliance Score"),
        'id="ch13"': ("admin_schools","Manajemen Data Sekolah"),
        'id="ch14"': ("admin_users",  "Manajemen Pengguna & Akses"),
    }

    for anchor, (shot_name, caption) in INJECT_MAP.items():
        img_html = img_tag(shot_name, caption, f"Tampilan nyata: {caption}")
        # Insert real screenshot right after the chapter-header closing div
        html = html.replace(
            anchor,
            anchor,   # keep anchor
        )
        # Find the chapter-header end for this chapter and insert screenshot after it
        ch_start = html.find(f'<div class="chapter" {anchor}')
        if ch_start == -1:
            ch_start = html.find(f'<div class="chapter" id="{anchor.split(chr(34))[1]}"')
        if ch_start != -1:
            header_end = html.find('</div>', html.find('chapter-header', ch_start))
            if header_end != -1:
                insert_pos = header_end + len('</div>')
                html = html[:insert_pos] + "\n" + img_html + "\n" + html[insert_pos:]

    out = Path(__file__).resolve().parent.parent.parent / "docs" / "dpmbg_user_guide.html"
    out.write_text(html, encoding="utf-8")
    size = out.stat().st_size // 1024
    print(f"[OK] Guide updated: {out}  ({size} KB)")
    print(f"     Open in Chrome -> Ctrl+P -> Save as PDF")
