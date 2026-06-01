"""Embed existing PNGs from docs/screenshots/guide/ into the generated HTML guide.

Replaces every <!-- SHOT:name --> marker with a base64-encoded img tag.
Run after generate_user_guide.py when backend is unavailable.
"""
import base64, re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
HTML = BASE / "docs" / "dpmbg_user_guide.html"
SHOT_DIR = BASE / "docs" / "screenshots" / "guide"
PROD_URL = "dapurpintarmbg.com"

CAPTIONS = {
    "login":            "Halaman Login — Dapur Pintar MBG",
    "dashboard":        "Dashboard kosong (sebelum operasi mulai) — 4 KPI + Pipeline Funnel",
    "notifications":    "Dashboard dengan ikon Bell aktif (yellow) di header",
    "menu_build":       "Build Menu Manual — pencari bahan TKPI + panel Analisis Gizi & Biaya",
    "menu_approval":    "Approval Menu — 7 tab status + Forecast Bahan",
    "purchase_orders":  "Purchase Orders — tombol + PO Baru + 7 tab status",
    "inspections":      "Joint Inspection — tombol + Mulai Inspeksi + 6 tab status",
    "production":       "Production — Tablet Kepala Chef + tombol Scan",
    "distributions":    "Distribusi Hari Ini — 4 tab (Aggregate / Wave 1&2 / Sisa / Vehicle)",
    "aslap":            "ASLAP — Operasi Harian — 5 tab pengawasan lapangan",
    "finance":          "Akuntan Finance — 6 tab (Cost-per-porsi / Price Trends / Spike Alerts / Expense / LRA / PO Generator)",
    "executive":        "Executive Dashboard — 3 tab + tombol Export BGN Compliance Bundle",
    "admin_schools":    "Master Sekolah Binaan — 11 sekolah SPPG Paseh",
    "admin_suppliers":  "Master Supplier — daftar supplier aktif",
    "admin_users":      "Users — 5 user demo dengan role berbeda (admin, bu_ratih, pak_dedi, mas_toni, mas_andre)",
    "nutrition_report": "Laporan Nutrisi — Laporan Harian + AKG Tracker Mingguan",
}


def b64_of(name: str) -> str | None:
    p = SHOT_DIR / f"{name}.png"
    if not p.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def img_tag(name: str, caption: str) -> str:
    src = b64_of(name)
    if not src:
        return (
            f'<div style="background:#F3F4F6;border:1px dashed #D1D5DB;'
            f'border-radius:8px;padding:20px;text-align:center;color:#6B7280;'
            f'font-size:0.85rem">Screenshot belum tersedia: {name}.png</div>'
        )
    cap = (
        f'<p style="text-align:center;font-size:0.75rem;color:#6B7280;'
        f'margin-top:6px;font-style:italic">{caption}</p>'
    )
    return (
        f'<div style="margin:16px 0;border-radius:10px;overflow:hidden;'
        f'box-shadow:0 4px 16px rgba(0,0,0,.12);border:1px solid #E5E7EB">'
        f'<div style="background:#1E3A8A;padding:7px 14px;display:flex;'
        f'align-items:center;gap:8px">'
        f'<span style="display:flex;gap:5px">'
        f'<span style="width:11px;height:11px;border-radius:50%;background:#FF5F56;display:inline-block"></span>'
        f'<span style="width:11px;height:11px;border-radius:50%;background:#FFBD2E;display:inline-block"></span>'
        f'<span style="width:11px;height:11px;border-radius:50%;background:#27C93F;display:inline-block"></span>'
        f'</span>'
        f'<span style="background:rgba(255,255,255,.15);border-radius:4px;'
        f'padding:2px 10px;font-size:0.72rem;color:rgba(255,255,255,.85);'
        f'font-family:monospace">{PROD_URL}</span></div>'
        f'<img src="{src}" alt="{caption}" style="width:100%;display:block"/>'
        f'</div>{cap}'
    )


def main():
    html = HTML.read_text(encoding="utf-8")
    html = html.replace("localhost:5173", PROD_URL)

    def _replace(m):
        name = m.group(1)
        caption = CAPTIONS.get(name, name)
        return img_tag(name, caption)

    html, n = re.subn(r"<!-- SHOT:(\w+) -->", _replace, html)
    HTML.write_text(html, encoding="utf-8")
    size_kb = HTML.stat().st_size // 1024
    print(f"[OK] Embedded {n} screenshots into {HTML.name} ({size_kb} KB)")


if __name__ == "__main__":
    main()
