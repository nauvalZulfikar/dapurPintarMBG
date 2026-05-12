#!/usr/bin/env python3
"""
DPMBG User Guide Generator
Usage: python generate_user_guide.py
Output: docs/dpmbg_user_guide.html  (open in Chrome → Ctrl+P → Save as PDF)
Optional PDF: python generate_user_guide.py --pdf  (requires: pip install weasyprint)
"""
import os, sys
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent.parent
OUT_HTML = BASE / "docs" / "dpmbg_user_guide.html"
OUT_PDF  = BASE / "docs" / "dpmbg_user_guide.pdf"

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Serif:ital,wght@0,400;0,700;1,400&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --blue:#2563EB;--green:#059669;--amber:#D97706;--red:#DC2626;
  --blue-light:#EFF6FF;--green-light:#ECFDF5;--amber-light:#FFFBEB;--red-light:#FEF2F2;
  --gray-50:#F9FAFB;--gray-100:#F3F4F6;--gray-200:#E5E7EB;--gray-400:#9CA3AF;
  --gray-600:#4B5563;--gray-800:#1F2937;--gray-900:#111827;
  --font-sans:'Inter',system-ui,sans-serif;
  --font-serif:'Noto Serif',Georgia,serif;
}
body{font-family:var(--font-sans);color:var(--gray-800);line-height:1.6;font-size:14px;background:#fff}
h1{font-size:2.2rem;font-weight:700;color:var(--gray-900);line-height:1.2}
h2{font-size:1.5rem;font-weight:700;color:var(--gray-900);margin:2rem 0 1rem}
h3{font-size:1.1rem;font-weight:600;color:var(--blue);margin:1.5rem 0 0.75rem}
h4{font-size:0.95rem;font-weight:600;color:var(--gray-700);margin:1rem 0 0.5rem}
p{margin-bottom:0.85rem}
a{color:var(--blue);text-decoration:none}
ul,ol{margin:0.5rem 0 0.85rem 1.5rem}
li{margin-bottom:0.3rem}
strong{font-weight:600}
code{background:var(--gray-100);border:1px solid var(--gray-200);border-radius:4px;padding:1px 5px;font-size:0.88em;font-family:'Courier New',monospace}

/* Page structure */
.page{max-width:210mm;margin:0 auto;padding:0}

/* Cover */
.cover{
  min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;
  background:linear-gradient(135deg,#1E3A8A 0%,#1D4ED8 40%,#059669 100%);
  color:#fff;text-align:center;padding:60px 40px;
}
.cover-badge{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);
  border-radius:999px;padding:6px 18px;font-size:0.8rem;font-weight:600;letter-spacing:.08em;
  text-transform:uppercase;margin-bottom:28px;display:inline-block}
.cover h1{font-size:2.8rem;font-weight:800;color:#fff;margin-bottom:16px;line-height:1.15}
.cover .subtitle{font-size:1.15rem;opacity:.85;max-width:480px;margin:0 auto 40px}
.cover-meta{display:flex;gap:40px;justify-content:center;margin-top:40px}
.cover-meta-item{text-align:center}
.cover-meta-item .val{font-size:1.6rem;font-weight:700}
.cover-meta-item .lbl{font-size:0.75rem;opacity:.7;text-transform:uppercase;letter-spacing:.05em}
.cover-logo{width:100px;height:100px;margin-bottom:32px}

/* TOC */
.toc-page{padding:60px 50px;border-bottom:1px solid var(--gray-200)}
.toc-page h2{color:var(--blue);font-size:1.8rem;margin-bottom:24px}
.toc-item{display:flex;align-items:baseline;gap:8px;padding:8px 0;border-bottom:1px dotted var(--gray-200)}
.toc-item .num{font-weight:700;color:var(--blue);min-width:40px}
.toc-item .title{flex:1;font-weight:500}
.toc-item .time{font-size:0.8rem;color:var(--green);font-weight:600;white-space:nowrap}

/* Chapter */
.chapter{padding:50px 50px 40px;border-bottom:3px solid var(--gray-100)}
.chapter-header{display:flex;align-items:center;gap:16px;margin-bottom:28px;
  padding:20px 24px;background:linear-gradient(90deg,var(--blue-light),#fff);
  border-left:5px solid var(--blue);border-radius:0 12px 12px 0}
.chapter-header .ch-num{font-size:0.75rem;font-weight:700;color:var(--blue);
  text-transform:uppercase;letter-spacing:.1em;min-width:50px}
.chapter-header h2{margin:0;font-size:1.6rem;color:var(--gray-900)}
.chapter-header .ch-time{font-size:0.8rem;background:var(--green);color:#fff;
  border-radius:999px;padding:3px 12px;font-weight:600;white-space:nowrap;margin-left:auto}

/* Role badges */
.roles{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 20px}
.role{display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:4px 12px;
  font-size:0.78rem;font-weight:600;border:1.5px solid currentColor}
.role-kepala{color:#7C3AED;background:#F5F3FF}
.role-gizi{color:#059669;background:#ECFDF5}
.role-akun{color:#D97706;background:#FFFBEB}
.role-aslap{color:#DC2626;background:#FEF2F2}
.role-chef{color:#0284C7;background:#F0F9FF}
.role-super{color:#1D4ED8;background:#EFF6FF}
.role-plat{color:#374151;background:#F9FAFB;border-color:#D1D5DB}

/* Story block */
.story{
  background:var(--amber-light);border-left:4px solid var(--amber);
  border-radius:0 12px 12px 0;padding:20px 24px;margin:20px 0;
  font-family:var(--font-serif);font-size:0.95rem;line-height:1.8;color:var(--gray-800);
  font-style:italic
}
.story strong{font-style:normal;color:var(--amber)}

/* Steps table */
.steps{width:100%;border-collapse:collapse;margin:16px 0}
.steps tr{border-bottom:1px solid var(--gray-100)}
.steps tr:hover{background:var(--gray-50)}
.steps td{padding:10px 12px;vertical-align:top}
.step-num{width:36px;height:36px;background:var(--blue);color:#fff;border-radius:50%;
  display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.85rem;
  flex-shrink:0}
.steps .n{width:52px}
.steps .n span{background:var(--blue);color:#fff;border-radius:50%;width:30px;height:30px;
  display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:0.85rem}
.steps .act{font-weight:500;color:var(--gray-800)}
.steps .path{font-size:0.82rem;color:var(--gray-600);margin-top:3px}
.steps .path code{font-size:0.8rem}

/* Callouts */
.tip{background:var(--green-light);border-left:4px solid var(--green);border-radius:0 8px 8px 0;
  padding:12px 16px;margin:12px 0;font-size:0.88rem}
.tip::before{content:'💡 ';font-style:normal}
.warning{background:var(--red-light);border-left:4px solid var(--red);border-radius:0 8px 8px 0;
  padding:12px 16px;margin:12px 0;font-size:0.88rem}
.warning::before{content:'⚠️ ';font-style:normal}
.info{background:var(--blue-light);border-left:4px solid var(--blue);border-radius:0 8px 8px 0;
  padding:12px 16px;margin:12px 0;font-size:0.88rem}
.info::before{content:'ℹ️ ';font-style:normal}

/* Screen mockup */
.screen{
  background:var(--gray-50);border:2px solid var(--gray-200);border-radius:12px;
  margin:20px 0;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.08)
}
.screen-titlebar{
  background:var(--gray-800);color:#fff;padding:8px 16px;display:flex;
  align-items:center;gap:8px;font-size:0.8rem
}
.screen-titlebar .dots{display:flex;gap:6px}
.screen-titlebar .dot{width:12px;height:12px;border-radius:50%}
.screen-titlebar .dot-r{background:#FF5F56}
.screen-titlebar .dot-y{background:#FFBD2E}
.screen-titlebar .dot-g{background:#27C93F}
.screen-titlebar .url{background:rgba(255,255,255,.15);border-radius:4px;padding:2px 12px;
  font-size:0.75rem;margin-left:8px;font-family:monospace}
.screen-body{padding:16px}
.screen-nav{
  background:#1E3A8A;color:#fff;padding:10px 16px;display:flex;gap:20px;
  align-items:center;font-size:0.8rem
}
.screen-nav .brand{font-weight:700;font-size:0.95rem;margin-right:12px}
.screen-nav a{color:rgba(255,255,255,.75);font-size:0.78rem}
.screen-content{padding:20px;background:#fff;min-height:120px}

/* Feature section */
.feature{margin:24px 0;padding:20px;background:#fff;border:1px solid var(--gray-200);
  border-radius:12px}
.feature-title{font-size:1rem;font-weight:700;color:var(--blue);margin-bottom:12px;
  display:flex;align-items:center;gap:8px}
.feature-title .icon{font-size:1.2rem}

/* Two-column layout */
.cols{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:16px 0}
.col{}

/* Stat cards */
.stat-row{display:flex;gap:12px;margin:16px 0;flex-wrap:wrap}
.stat-card{flex:1;min-width:120px;background:var(--blue-light);border:1px solid #BFDBFE;
  border-radius:10px;padding:14px;text-align:center}
.stat-card .sv{font-size:1.6rem;font-weight:800;color:var(--blue)}
.stat-card .sl{font-size:0.72rem;color:var(--gray-600);text-transform:uppercase;letter-spacing:.04em}

/* Timeline */
.timeline{position:relative;margin:24px 0}
.timeline::before{content:'';position:absolute;left:20px;top:0;bottom:0;width:3px;background:var(--gray-200)}
.tl-item{display:flex;gap:16px;padding:12px 0;position:relative}
.tl-dot{width:40px;height:40px;background:var(--blue);border-radius:50%;display:flex;
  align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:0.75rem;
  flex-shrink:0;z-index:1;box-shadow:0 0 0 4px var(--blue-light)}
.tl-dot.green{background:var(--green);box-shadow:0 0 0 4px var(--green-light)}
.tl-dot.amber{background:var(--amber);box-shadow:0 0 0 4px var(--amber-light)}
.tl-dot.red{background:var(--red);box-shadow:0 0 0 4px var(--red-light)}
.tl-content{flex:1;padding-top:6px}
.tl-time{font-size:0.75rem;color:var(--gray-400);font-weight:600}
.tl-title{font-weight:600;color:var(--gray-800)}
.tl-desc{font-size:0.85rem;color:var(--gray-600);margin-top:2px}

/* Table */
.data-table{width:100%;border-collapse:collapse;margin:16px 0;font-size:0.85rem}
.data-table th{background:var(--blue);color:#fff;padding:8px 12px;text-align:left;font-weight:600}
.data-table td{padding:8px 12px;border-bottom:1px solid var(--gray-100)}
.data-table tr:nth-child(even){background:var(--gray-50)}
.badge{display:inline-block;border-radius:999px;padding:2px 10px;font-size:0.75rem;font-weight:600}
.badge-blue{background:var(--blue-light);color:var(--blue)}
.badge-green{background:var(--green-light);color:var(--green)}
.badge-amber{background:var(--amber-light);color:var(--amber)}
.badge-red{background:var(--red-light);color:var(--red)}
.badge-gray{background:var(--gray-100);color:var(--gray-600)}

/* SVG containers */
.diagram{margin:20px 0;text-align:center;overflow-x:auto}

/* Print */
@media print{
  @page{size:A4;margin:15mm 15mm 20mm}
  .cover{min-height:auto;padding:40px;page-break-after:always}
  .toc-page{page-break-after:always}
  .chapter{page-break-before:always;padding:30px 20px}
  .screen,.feature,.story{page-break-inside:avoid}
  h2,h3{page-break-after:avoid}
  .tip,.warning,.info{page-break-inside:avoid}
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# SVG diagrams
# ─────────────────────────────────────────────────────────────────────────────

SVG_LOGO = """<svg class="cover-logo" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="48" fill="rgba(255,255,255,0.15)" stroke="rgba(255,255,255,0.4)" stroke-width="2"/>
  <text x="50" y="38" text-anchor="middle" fill="white" font-size="28" font-weight="800" font-family="Inter,sans-serif">DP</text>
  <text x="50" y="62" text-anchor="middle" fill="rgba(255,255,255,0.8)" font-size="13" font-family="Inter,sans-serif">MBG</text>
  <path d="M25 72 Q50 80 75 72" stroke="rgba(255,255,255,0.5)" stroke-width="2" fill="none"/>
</svg>"""

SVG_ROLES = """<svg viewBox="0 0 700 320" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;font-family:Inter,sans-serif">
  <!-- platform_admin -->
  <rect x="260" y="10" width="180" height="44" rx="8" fill="#1E3A8A"/>
  <text x="350" y="28" text-anchor="middle" fill="white" font-size="11" font-weight="700">🖥️ Platform Admin</text>
  <text x="350" y="44" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="9">Vendor IT — lintas org</text>
  <!-- superadmin -->
  <rect x="260" y="80" width="180" height="44" rx="8" fill="#1D4ED8"/>
  <text x="350" y="98" text-anchor="middle" fill="white" font-size="11" font-weight="700">🏢 Superadmin</text>
  <text x="350" y="114" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="9">Yayasan — 1 org, multi-SPPG</text>
  <!-- head_sppg -->
  <rect x="260" y="155" width="180" height="44" rx="8" fill="#2563EB"/>
  <text x="350" y="173" text-anchor="middle" fill="white" font-size="11" font-weight="700">👔 Kepala SPPG</text>
  <text x="350" y="189" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="9">Pimpinan 1 SPPG</text>
  <!-- leaf roles -->
  <rect x="20" y="240" width="130" height="44" rx="8" fill="#059669"/>
  <text x="85" y="258" text-anchor="middle" fill="white" font-size="10" font-weight="700">🥗 Ahli Gizi</text>
  <text x="85" y="274" text-anchor="middle" fill="rgba(255,255,255,0.75)" font-size="8.5">Gizi &amp; Menu</text>
  <rect x="165" y="240" width="130" height="44" rx="8" fill="#D97706"/>
  <text x="230" y="258" text-anchor="middle" fill="white" font-size="10" font-weight="700">💰 Akuntan</text>
  <text x="230" y="274" text-anchor="middle" fill="rgba(255,255,255,0.75)" font-size="8.5">Keuangan &amp; PO</text>
  <rect x="310" y="240" width="130" height="44" rx="8" fill="#DC2626"/>
  <text x="375" y="258" text-anchor="middle" fill="white" font-size="10" font-weight="700">🦺 ASLAP</text>
  <text x="375" y="274" text-anchor="middle" fill="rgba(255,255,255,0.75)" font-size="8.5">Lapangan &amp; Distribusi</text>
  <rect x="455" y="240" width="130" height="44" rx="8" fill="#0284C7"/>
  <text x="520" y="258" text-anchor="middle" fill="white" font-size="10" font-weight="700">👨‍🍳 Kepala Chef</text>
  <text x="520" y="274" text-anchor="middle" fill="rgba(255,255,255,0.75)" font-size="8.5">Produksi Masakan</text>
  <!-- connectors -->
  <line x1="350" y1="54" x2="350" y2="80" stroke="#94A3B8" stroke-width="2"/>
  <line x1="350" y1="124" x2="350" y2="155" stroke="#94A3B8" stroke-width="2"/>
  <line x1="350" y1="199" x2="350" y2="230" stroke="#94A3B8" stroke-width="2"/>
  <line x1="85" y1="230" x2="520" y2="230" stroke="#94A3B8" stroke-width="2"/>
  <line x1="85" y1="230" x2="85" y2="240" stroke="#94A3B8" stroke-width="2"/>
  <line x1="230" y1="230" x2="230" y2="240" stroke="#94A3B8" stroke-width="2"/>
  <line x1="375" y1="230" x2="375" y2="240" stroke="#94A3B8" stroke-width="2"/>
  <line x1="520" y1="230" x2="520" y2="240" stroke="#94A3B8" stroke-width="2"/>
</svg>"""

SVG_DAY_TIMELINE = """<svg viewBox="0 0 720 110" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;font-family:Inter,sans-serif">
  <rect x="0" y="0" width="720" height="110" rx="12" fill="#F8FAFC"/>
  <!-- spine -->
  <line x1="40" y1="55" x2="680" y2="55" stroke="#CBD5E1" stroke-width="3"/>
  <!-- nodes -->
  <circle cx="40"  cy="55" r="14" fill="#1E3A8A"/>
  <circle cx="120" cy="55" r="14" fill="#2563EB"/>
  <circle cx="210" cy="55" r="14" fill="#059669"/>
  <circle cx="300" cy="55" r="14" fill="#D97706"/>
  <circle cx="390" cy="55" r="14" fill="#DC2626"/>
  <circle cx="480" cy="55" r="14" fill="#0284C7"/>
  <circle cx="570" cy="55" r="14" fill="#7C3AED"/>
  <circle cx="660" cy="55" r="14" fill="#059669"/>
  <!-- labels top -->
  <text x="40"  y="22" text-anchor="middle" fill="#1E3A8A" font-size="9" font-weight="700">04:30</text>
  <text x="120" y="22" text-anchor="middle" fill="#2563EB" font-size="9" font-weight="700">05:00</text>
  <text x="210" y="22" text-anchor="middle" fill="#059669" font-size="9" font-weight="700">06:30</text>
  <text x="300" y="22" text-anchor="middle" fill="#D97706" font-size="9" font-weight="700">07:30</text>
  <text x="390" y="22" text-anchor="middle" fill="#DC2626" font-size="9" font-weight="700">08:30</text>
  <text x="480" y="22" text-anchor="middle" fill="#0284C7" font-size="9" font-weight="700">09:00</text>
  <text x="570" y="22" text-anchor="middle" fill="#7C3AED" font-size="9" font-weight="700">13:00</text>
  <text x="660" y="22" text-anchor="middle" fill="#059669" font-size="9" font-weight="700">14:00</text>
  <!-- labels bottom -->
  <text x="40"  y="82" text-anchor="middle" fill="#374151" font-size="8">Login</text>
  <text x="120" y="82" text-anchor="middle" fill="#374151" font-size="8">Menu</text>
  <text x="210" y="82" text-anchor="middle" fill="#374151" font-size="8">Inspeksi</text>
  <text x="300" y="82" text-anchor="middle" fill="#374151" font-size="8">Produksi</text>
  <text x="390" y="82" text-anchor="middle" fill="#374151" font-size="8">Distribusi</text>
  <text x="480" y="82" text-anchor="middle" fill="#374151" font-size="8">Lapangan</text>
  <text x="570" y="82" text-anchor="middle" fill="#374151" font-size="8">Keuangan</text>
  <text x="660" y="82" text-anchor="middle" fill="#374151" font-size="8">Eksekutif</text>
  <!-- icons on nodes -->
  <text x="40"  y="59" text-anchor="middle" fill="white" font-size="10">🔑</text>
  <text x="120" y="59" text-anchor="middle" fill="white" font-size="10">🥗</text>
  <text x="210" y="59" text-anchor="middle" fill="white" font-size="10">📋</text>
  <text x="300" y="59" text-anchor="middle" fill="white" font-size="10">🍳</text>
  <text x="390" y="59" text-anchor="middle" fill="white" font-size="10">🚚</text>
  <text x="480" y="59" text-anchor="middle" fill="white" font-size="10">🦺</text>
  <text x="570" y="59" text-anchor="middle" fill="white" font-size="10">💰</text>
  <text x="660" y="59" text-anchor="middle" fill="white" font-size="10">📊</text>
</svg>"""

SVG_MENU_STATE = """<svg viewBox="0 0 640 160" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;font-family:Inter,sans-serif">
  <defs><marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
    <path d="M0,0 L0,6 L8,3 z" fill="#94A3B8"/>
  </marker></defs>
  <!-- states -->
  <rect x="10"  y="55" width="90" height="36" rx="6" fill="#F3F4F6" stroke="#D1D5DB" stroke-width="1.5"/>
  <text x="55"  y="77" text-anchor="middle" fill="#374151" font-size="10" font-weight="600">Draft</text>
  <rect x="130" y="55" width="110" height="36" rx="6" fill="#FEF3C7" stroke="#F59E0B" stroke-width="1.5"/>
  <text x="185" y="77" text-anchor="middle" fill="#92400E" font-size="10" font-weight="600">Pending Review</text>
  <rect x="270" y="55" width="90" height="36" rx="6" fill="#D1FAE5" stroke="#059669" stroke-width="1.5"/>
  <text x="315" y="77" text-anchor="middle" fill="#065F46" font-size="10" font-weight="600">Approved</text>
  <rect x="390" y="55" width="90" height="36" rx="6" fill="#DBEAFE" stroke="#2563EB" stroke-width="1.5"/>
  <text x="435" y="77" text-anchor="middle" fill="#1E40AF" font-size="10" font-weight="600">Locked</text>
  <rect x="520" y="55" width="90" height="36" rx="6" fill="#F3F4F6" stroke="#D1D5DB" stroke-width="1.5"/>
  <text x="565" y="77" text-anchor="middle" fill="#6B7280" font-size="10" font-weight="600">Archived</text>
  <!-- arrows -->
  <line x1="100" y1="73" x2="128" y2="73" stroke="#94A3B8" stroke-width="2" marker-end="url(#arr)"/>
  <line x1="240" y1="73" x2="268" y2="73" stroke="#94A3B8" stroke-width="2" marker-end="url(#arr)"/>
  <line x1="360" y1="73" x2="388" y2="73" stroke="#94A3B8" stroke-width="2" marker-end="url(#arr)"/>
  <line x1="480" y1="73" x2="518" y2="73" stroke="#94A3B8" stroke-width="2" marker-end="url(#arr)"/>
  <!-- reject arrow (back) -->
  <path d="M 185 55 Q 185 20 55 20 L 55 55" stroke="#EF4444" stroke-width="1.5" fill="none" marker-end="url(#arr)" stroke-dasharray="4,3"/>
  <!-- labels -->
  <text x="114" y="65" text-anchor="middle" fill="#374151" font-size="8">Submit</text>
  <text x="254" y="65" text-anchor="middle" fill="#374151" font-size="8">Approve</text>
  <text x="374" y="65" text-anchor="middle" fill="#374151" font-size="8">Lock</text>
  <text x="499" y="65" text-anchor="middle" fill="#374151" font-size="8">Archive</text>
  <text x="120" y="18" text-anchor="middle" fill="#EF4444" font-size="8">Reject → Draft</text>
</svg>"""

SVG_SIDEBAR = """<svg viewBox="0 0 280 420" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;font-family:Inter,sans-serif;border-radius:12px;overflow:hidden">
  <!-- sidebar bg -->
  <rect width="280" height="420" fill="#1E3A8A"/>
  <!-- brand -->
  <rect x="12" y="12" width="256" height="44" rx="8" fill="rgba(255,255,255,0.1)"/>
  <text x="40" y="30" fill="white" font-size="12" font-weight="800">🍱 DPMBG</text>
  <text x="40" y="46" fill="rgba(255,255,255,0.6)" font-size="9">Dapur Pintar MBG</text>
  <!-- active item highlight -->
  <rect x="12" y="70" width="256" height="32" rx="6" fill="#2563EB"/>
  <text x="32" y="90" fill="white" font-size="10" font-weight="600">🏠 Dashboard</text>
  <!-- groups -->
  <text x="20" y="118" fill="rgba(255,255,255,0.4)" font-size="8" font-weight="700" letter-spacing="0.08em">▼ MENU &amp; GIZI</text>
  <text x="32" y="138" fill="rgba(255,255,255,0.75)" font-size="9">🥗 Build Menu Manual</text>
  <text x="32" y="156" fill="rgba(255,255,255,0.75)" font-size="9">✅ Menu Approval</text>
  <text x="32" y="174" fill="rgba(255,255,255,0.75)" font-size="9">📝 Permintaan Siswa</text>
  <text x="20" y="198" fill="rgba(255,255,255,0.4)" font-size="8" font-weight="700" letter-spacing="0.08em">▼ PENERIMAAN</text>
  <text x="32" y="218" fill="rgba(255,255,255,0.75)" font-size="9">📦 Purchase Orders</text>
  <text x="32" y="236" fill="rgba(255,255,255,0.75)" font-size="9">🔍 Inspeksi Bersama</text>
  <text x="20" y="260" fill="rgba(255,255,255,0.4)" font-size="8" font-weight="700" letter-spacing="0.08em">▼ OPERASI DAPUR</text>
  <text x="32" y="280" fill="rgba(255,255,255,0.75)" font-size="9">🍳 Produksi Batch</text>
  <text x="20" y="304" fill="rgba(255,255,255,0.4)" font-size="8" font-weight="700" letter-spacing="0.08em">▼ DISTRIBUSI</text>
  <text x="32" y="324" fill="rgba(255,255,255,0.75)" font-size="9">🚚 Distribusi Makanan</text>
  <text x="20" y="348" fill="rgba(255,255,255,0.4)" font-size="8" font-weight="700" letter-spacing="0.08em">▼ LAPANGAN (ASLAP)</text>
  <text x="32" y="368" fill="rgba(255,255,255,0.75)" font-size="9">🦺 Dasbor ASLAP</text>
  <text x="20" y="392" fill="rgba(255,255,255,0.4)" font-size="8" font-weight="700" letter-spacing="0.08em">▼ KEUANGAN  ▼ EKSEKUTIF</text>
  <text x="20" y="408" fill="rgba(255,255,255,0.4)" font-size="8" font-weight="700" letter-spacing="0.08em">▼ MASTER DATA  ▼ ADMIN</text>
</svg>"""

# ─────────────────────────────────────────────────────────────────────────────
# Helper builders
# ─────────────────────────────────────────────────────────────────────────────

def roles(*r):
    MAP = {
        'kepala':'role-kepala','nutritionist':'role-gizi','accountant':'role-akun',
        'aslap':'role-aslap','chef':'role-chef','super':'role-super','platform':'role-plat',
    }
    LABEL = {
        'kepala':'👔 Kepala SPPG','nutritionist':'🥗 Ahli Gizi','accountant':'💰 Akuntan',
        'aslap':'🦺 ASLAP','chef':'👨‍🍳 Kepala Chef','super':'🏢 Superadmin','platform':'🖥️ Platform Admin',
    }
    items = "".join(f'<span class="role {MAP[x]}">{LABEL[x]}</span>' for x in r)
    return f'<div class="roles">{items}</div>'

def story(txt):
    return f'<blockquote class="story">{txt}</blockquote>'

def tip(txt): return f'<div class="tip">{txt}</div>'
def warn(txt): return f'<div class="warning">{txt}</div>'
def info(txt): return f'<div class="info">{txt}</div>'

def steps(rows):
    """rows = list of (action_html, path_hint='')"""
    html = '<table class="steps">'
    for i,(act,*path) in enumerate(rows):
        p = f'<div class="path">{path[0]}</div>' if path and path[0] else ''
        html += f'<tr><td class="n"><span>{i+1}</span></td><td class="act">{act}{p}</td></tr>'
    html += '</table>'
    return html

def screen(url, body_html, title="DPMBG", shot_name=None):
    """Emit a placeholder that screenshot_guide.py replaces with a real screenshot."""
    if shot_name is None:
        _url_map = {
            "/login": "login", "/": "dashboard", "/menu-manual": "menu_build",
            "/menu-approval": "menu_approval", "/purchase-orders": "purchase_orders",
            "/inspections": "inspections", "/production": "production",
            "/distributions": "distributions", "/finance": "finance",
            "/aslap": "aslap", "/executive": "executive",
            "/admin/schools": "admin_schools", "/admin/users": "admin_users",
        }
        shot_name = _url_map.get(url, url.replace("/", "_").strip("_") or "dashboard")
    return f"<!-- SHOT:{shot_name} -->"

def feature_box(icon, title, body):
    return f"""<div class="feature">
  <div class="feature-title"><span class="icon">{icon}</span>{title}</div>
  {body}
</div>"""

def stat_row(*cards):
    inner = "".join(f'<div class="stat-card"><div class="sv">{v}</div><div class="sl">{l}</div></div>' for v,l in cards)
    return f'<div class="stat-row">{inner}</div>'

def badge(text, color='blue'):
    return f'<span class="badge badge-{color}">{text}</span>'

def data_table(headers, rows):
    ths = "".join(f'<th>{h}</th>' for h in headers)
    trs = "".join('<tr>'+"".join(f'<td>{c}</td>' for c in row)+'</tr>' for row in rows)
    return f'<table class="data-table"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>'

def chapter(num, emoji, title, time_label, content):
    return f"""<div class="chapter" id="ch{num}">
  <div class="chapter-header">
    <span class="ch-num">BAB {num}</span>
    <h2>{emoji} {title}</h2>
    <span class="ch-time">⏰ {time_label}</span>
  </div>
  {content}
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# COVER
# ─────────────────────────────────────────────────────────────────────────────
COVER = f"""<div class="cover">
  {SVG_LOGO}
  <div class="cover-badge">Panduan Pengguna Resmi</div>
  <h1>Sehari Penuh di<br>Dapur Pintar MBG</h1>
  <p class="subtitle">Panduan lengkap menggunakan sistem DPMBG — dari subuh hingga sore, mengikuti hari kerja nyata tim SPPG Paseh</p>
  <div style="margin-top:24px">
<!-- SHOT:dashboard -->
  </div>
  <div class="cover-meta">
    <div class="cover-meta-item"><div class="val">10</div><div class="lbl">Fase Fitur</div></div>
    <div class="cover-meta-item"><div class="val">7</div><div class="lbl">Role Pengguna</div></div>
    <div class="cover-meta-item"><div class="val">23</div><div class="lbl">Sekolah</div></div>
    <div class="cover-meta-item"><div class="val">1.500+</div><div class="lbl">Porsi/Hari</div></div>
  </div>
  <p style="margin-top:36px;font-size:0.8rem;opacity:.5">DPMBG v1.0 — Mei 2026 · SPPG Paseh, Kabupaten Bandung</p>
</div>"""

# ─────────────────────────────────────────────────────────────────────────────
# TOC
# ─────────────────────────────────────────────────────────────────────────────
TOC_ITEMS = [
    (1,  "Mengenal DPMBG",                       "Pengantar"),
    (2,  "Login & Dashboard",                     "05:00"),
    (3,  "Notifikasi & Bell",                     "05:15"),
    (4,  "Menu & Gizi — Build Manual",            "05:30"),
    (5,  "Menu — Approval & Siklus 20 Hari",      "06:00"),
    (6,  "Purchase Order & Supplier",             "06:15"),
    (7,  "Inspeksi Bersama — 3 Tanda Tangan",     "06:30"),
    (8,  "Produksi Batch & QR Scan",              "07:30"),
    (9,  "Distribusi Makanan ke Sekolah",         "08:30"),
    (10, "Pengawasan Lapangan — ASLAP",           "10:00"),
    (11, "Keuangan — Expense, LRA & Tren Harga",  "13:00"),
    (12, "Dashboard Eksekutif & BGN Bundle",      "14:00"),
    (13, "Master Data & Admin",                   "Kapan Saja"),
    (14, "Cheat Sheet Harian",                    "Referensi Cepat"),
]

TOC_HTML = '<div class="toc-page"><h2>📖 Daftar Isi</h2>'
for num,title,t in TOC_ITEMS:
    TOC_HTML += f'<div class="toc-item"><span class="num">Bab {num}</span><span class="title">{title}</span><span class="time">{t}</span></div>'
TOC_HTML += '</div>'


# ─────────────────────────────────────────────────────────────────────────────
# BAB 1 — Mengenal DPMBG
# ─────────────────────────────────────────────────────────────────────────────

BAB1 = chapter(1, "🍱", "Mengenal DPMBG", "Pengantar", f"""
<p>
  <strong>DPMBG (Dapur Pintar Makan Bergizi Gratis)</strong> adalah sistem manajemen operasional dapur
  yang dirancang khusus untuk program <em>Makan Bergizi Gratis (MBG)</em> milik pemerintah Indonesia.
  Sistem ini mengelola seluruh rantai operasional — dari perencanaan menu, pengadaan bahan, produksi
  masakan, distribusi ke sekolah, hingga pelaporan keuangan dan kepatuhan BGN.
</p>

{story('''
"Di balik 1.500 piring makan yang tiba tepat waktu di 23 sekolah setiap hari,
ada satu sistem yang bekerja diam-diam sejak subuh: DPMBG. Jam 04:00 truk supplier
sudah di halaman dapur untuk inspeksi. Jam 05:30 Kepala Chef sudah memasak.
Jam 08:00 Wave 1 jalan ke PAUD dan TK. Jam 10:00 Wave 2 jalan ke SD dan SMP.
Semuanya terkoordinasi, terdokumentasi, dan terlapor — tanpa satu pun catatan kertas."
''')}

<h3>Mengapa DPMBG?</h3>
<div class="cols">
  <div class="col">
    <h4>Tanpa DPMBG</h4>
    <ul>
      <li>Catatan manual di buku fisik, rawan hilang</li>
      <li>Tidak ada jejak audit siapa yang tanda tangan</li>
      <li>Laporan LRA dikerjakan manual di Excel tiap 2 minggu</li>
      <li>Tidak ada peringatan dini jika harga bahan naik</li>
      <li>Kepala SPPG tidak bisa pantau kondisi real-time</li>
    </ul>
  </div>
  <div class="col">
    <h4>Dengan DPMBG</h4>
    <ul>
      <li>Semua transaksi tersimpan di cloud, bisa diaudit kapan saja</li>
      <li>3-way sign-off digital untuk setiap penerimaan bahan</li>
      <li>LRA otomatis dari data transaksi yang sudah ada</li>
      <li>Alert spike harga >15% langsung muncul di dashboard</li>
      <li>KPI dashboard real-time: porsi, defect rate, cost/porsi</li>
    </ul>
  </div>
</div>

<h3>Struktur Pengguna</h3>
<p>DPMBG menggunakan sistem <strong>7 role</strong> yang mencerminkan struktur organisasi SPPG MBG sesungguhnya:</p>
<!-- SHOT:admin_users -->

{data_table(
  ['Role', 'Nama BGN', 'Tugas Utama', 'Akses'],
  [
    [badge('Kepala SPPG','blue'), 'Kepala SPPG', 'Pimpinan operasional dapur', badge('Full','green')],
    [badge('Ahli Gizi','green'), 'Pengawas Gizi/Produksi', 'Menu, gizi, QC', badge('Gizi+Menu','green')],
    [badge('Akuntan','amber'), 'Pengawas Keuangan', 'PO, keuangan, LRA', badge('Keuangan','amber')],
    [badge('ASLAP','red'), 'Asisten Lapangan', 'Inspeksi, distribusi, lapangan', badge('Ops','red')],
    [badge('Kepala Chef','blue'), 'Kepala Chef', 'Produksi batch, QR scan', badge('Dapur','blue')],
    [badge('Superadmin','blue'), 'Yayasan', 'Multi-SPPG oversight', badge('Multi-SPPG','blue')],
    [badge('Platform Admin','gray'), 'Vendor IT', 'Setup sistem, lintas org', badge('Full','gray')],
  ]
)}

<h3>Karakter dalam Panduan Ini</h3>
<p>Sepanjang panduan ini, kita akan mengikuti hari kerja tim SPPG Paseh:</p>
{data_table(
  ['Karakter','Role','Cerita'],
  [
    ['👔 Kepala SPPG', 'Kepala SPPG', 'Administrator SPPG Paseh — pemantau keseluruhan'],
    ['🥗 Ahli Gizi', 'Ahli Gizi', 'Perencana menu dan pengawas gizi'],
    ['💰 Akuntan', 'Akuntan', 'Pengelola keuangan, PO, dan pelaporan'],
    ['🦺 ASLAP', 'ASLAP', 'Asisten lapangan — inspeksi sampai distribusi'],
    ['👨‍🍳 Kepala Chef', 'Kepala Chef', 'Pemimpin dapur dan batch produksi'],
    ['🏢 Superadmin', 'Superadmin', 'Yayasan — memantau semua SPPG'],
    ['👩‍🏫 Guru Sekolah', 'Guru Sekolah', 'Konfirmasi penerimaan makan (no login required)'],
  ]
)}

<h3>Cara Menggunakan Panduan Ini</h3>
{info('Panduan ini mengikuti urutan waktu satu hari kerja. Setiap bab bercerita tentang satu fitur, siapa yang menggunakannya, dan langkah-langkah detail. Untuk referensi cepat, lihat Bab 14 — Cheat Sheet Harian.')}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 2 — Login & Dashboard
# ─────────────────────────────────────────────────────────────────────────────

SCREEN_LOGIN = screen("/login", """
<div style="max-width:320px;margin:0 auto;padding:30px;background:#F9FAFB;border-radius:10px;border:1px solid #E5E7EB">
  <div style="text-align:center;margin-bottom:20px">
    <div style="font-size:2rem">🍱</div>
    <div style="font-weight:700;font-size:1.1rem;color:#1E3A8A">DPMBG</div>
    <div style="font-size:0.8rem;color:#6B7280">Dapur Pintar MBG</div>
  </div>
  <div style="margin-bottom:12px">
    <div style="font-size:0.8rem;font-weight:600;color:#374151;margin-bottom:4px">Username</div>
    <div style="background:white;border:2px solid #2563EB;border-radius:6px;padding:8px 12px;font-size:0.85rem;color:#374151">admin</div>
  </div>
  <div style="margin-bottom:16px">
    <div style="font-size:0.8rem;font-weight:600;color:#374151;margin-bottom:4px">Password</div>
    <div style="background:white;border:1px solid #D1D5DB;border-radius:6px;padding:8px 12px;font-size:0.85rem;color:#374151">••••••••</div>
  </div>
  <div style="background:#2563EB;color:white;text-align:center;padding:10px;border-radius:6px;font-weight:600;font-size:0.9rem">Masuk</div>
</div>
""")

SCREEN_DASHBOARD = screen("/", f"""
<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px">
  {stat_row(('1.520','Target Porsi'), ('1.498','Terproses'), ('1.490','Terkirim'), ('98.2%','Konfirmasi'))}
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:12px">
    <div style="font-size:0.75rem;font-weight:700;color:#059669">COST PER PORSI HARI INI</div>
    <div style="font-size:1.8rem;font-weight:800;color:#065F46">Rp 13.200</div>
    <div style="font-size:0.75rem;color:#6B7280">Target: Rp 15.000 ✅</div>
  </div>
  <div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;padding:12px">
    <div style="font-size:0.75rem;font-weight:700;color:#2563EB">DEFECT RATE</div>
    <div style="font-size:1.8rem;font-weight:800;color:#1E40AF">0.8%</div>
    <div style="font-size:0.75rem;color:#6B7280">Threshold: &lt;2% ✅</div>
  </div>
</div>
""")

BAB2 = chapter(2, "🔑", "Login & Dashboard", "04:30", f"""
{roles('kepala','nutritionist','accountant','aslap','chef')}

{story('''
<strong>04:30 pagi.</strong> Kepala SPPG tiba di dapur — truk supplier sudah di halaman
sejak jam 04:00 dan ASLAP sedang menangani inspeksi. Kepala SPPG langsung buka laptop
dan login ke DPMBG. Dalam 30 detik dia sudah tahu: 1.520 porsi ditargetkan hari ini,
cost per porsi kemarin Rp 13.200 (di bawah target Rp 15.000), dan inspeksi berjalan lancar.
''')}

<h3>Login ke DPMBG</h3>
{SCREEN_LOGIN}

{steps([
  ('Buka browser, akses <code>http://dpmbg.sppg-paseh.id</code> (atau localhost:5173 untuk lokal)', ''),
  ('Masukkan <strong>Username</strong> dan <strong>Password</strong> yang diberikan admin', ''),
  ('Klik tombol <strong>Masuk</strong>', ''),
  ('Anda akan diarahkan ke halaman Dashboard sesuai role Anda', ''),
])}

{tip('Setiap role melihat dashboard yang berbeda. Kepala SPPG melihat KPI lengkap; ASLAP melihat ringkasan distribusi; Kepala Chef melihat status batch produksi.')}
{warn('Jangan bagikan password dengan siapapun. Setiap aksi di sistem terekam dengan nama pengguna yang login.')}

<h3>Halaman Dashboard</h3>
{SCREEN_DASHBOARD}

<p>Dashboard menampilkan ringkasan operasional hari ini secara real-time:</p>
{data_table(
  ['Kartu / Widget', 'Artinya', 'Siapa yang Peduli'],
  [
    ['Target Porsi', 'Jumlah porsi yang harus diproduksi hari ini', 'Semua role'],
    ['Terproses', 'Porsi yang sudah keluar dari batch produksi', 'Kepala SPPG, Chef'],
    ['Terkirim', 'Porsi yang sudah dikirim ke sekolah', 'ASLAP, Kepala SPPG'],
    ['% Konfirmasi', 'Sekolah yang sudah konfirmasi terima', 'ASLAP, Kepala SPPG'],
    ['Cost per Porsi', 'Total biaya dibagi jumlah porsi hari ini', 'Akuntan, Kepala SPPG'],
    ['Defect Rate', 'Persen bahan yang ditolak saat inspeksi', 'Ahli Gizi, Kepala SPPG'],
  ]
)}

<h3>Navigasi Sidebar</h3>
<div class="cols">
  <div class="col">
<!-- SHOT:dashboard -->
  </div>
  <div class="col">
    <p>Sidebar kiri berisi semua fitur, dikelompokkan dalam 8 grup yang bisa dilipat/dibuka (<strong>klik nama grup</strong> untuk toggle):</p>
    <ul>
      <li><strong>🏠 Dashboard</strong> — halaman utama</li>
      <li><strong>▼ MENU & GIZI</strong> — Build Menu, Approval, Student Requests</li>
      <li><strong>▼ PENERIMAAN</strong> — PO, Inspeksi, Tren Harga</li>
      <li><strong>▼ OPERASI DAPUR</strong> — Produksi, QR Scan</li>
      <li><strong>▼ DISTRIBUSI</strong> — Kirim ke sekolah, leftovers</li>
      <li><strong>▼ LAPANGAN (ASLAP)</strong> — Checklist, Air, Laporan</li>
      <li><strong>▼ KEUANGAN</strong> — Expense, LRA, Relawan</li>
      <li><strong>▼ EKSEKUTIF</strong> — KPI, Compliance, Ranking</li>
      <li><strong>▼ MASTER DATA</strong> — Sekolah, Supplier</li>
      <li><strong>▼ ADMIN</strong> — Pengguna, Dapur</li>
    </ul>
    {tip('Pilihan grup yang terbuka tersimpan otomatis di browser — besok langsung terbuka di grup yang sama.')}
  </div>
</div>
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 3 — Notifikasi
# ─────────────────────────────────────────────────────────────────────────────

BAB3 = chapter(3, "🔔", "Notifikasi & Bell", "04:30", f"""
{roles('kepala','nutritionist','accountant','aslap','chef')}

{story('''
<strong>04:30 pagi.</strong> Setelah login, Kepala SPPG melihat angka merah kecil di pojok kanan atas: <strong>3</strong>.
Tiga notifikasi baru sejak semalam. Dia klik bell — ada menu yang sudah disubmit Ahli Gizi kemarin
dan menunggu approval-nya, satu alert inspeksi baru yang baru saja dibuat ASLAP,
dan satu pengingat food sample yang hampir lewat 48 jam. Semua ditangani dari satu panel.
''')}

<h3>Bell Notifikasi</h3>
{screen("/", "", shot_name="notifications")}

{steps([
  ('Lihat ikon 🔔 di header kanan atas — angka merah menunjukkan notifikasi belum dibaca', ''),
  ('Klik ikon bell untuk membuka panel notifikasi', ''),
  ('Klik salah satu notifikasi untuk langsung navigasi ke halaman yang relevan', ''),
  ('Klik <strong>"Tandai semua terbaca"</strong> untuk membersihkan semua badge merah sekaligus', ''),
])}

<h3>Pengaturan Notifikasi</h3>
{steps([
  ('Buka <strong>Profil</strong> → <strong>Pengaturan Notifikasi</strong>', 'Sidebar → klik nama pengguna di header'),
  ('Pilih kategori mana yang ingin diterima (menu, inspeksi, distribusi, keuangan, sistem)', ''),
  ('Simpan preferensi', ''),
])}

{data_table(
  ['Kategori', 'Dipicu Oleh', 'Siapa yang Dinotifikasi'],
  [
    ['menu', 'Menu disubmit untuk review', 'Kepala SPPG'],
    ['inspection', 'Inspeksi baru dibuat', 'Kepala SPPG, Ahli Gizi, Akuntan'],
    ['distribution', 'Konfirmasi penerimaan sekolah', 'ASLAP, Kepala SPPG'],
    ['finance', 'Alert spike harga, LRA due', 'Akuntan, Kepala SPPG'],
    ['system', 'Informasi sistem', 'Semua role'],
  ]
)}

{tip('Notifikasi disimpan di database — tidak hilang walau browser ditutup. Riwayat bisa dilihat kapan saja.')}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 4 — Build Menu Manual & Reverse Optimizer
# ─────────────────────────────────────────────────────────────────────────────

SCREEN_BUILD_MENU = screen("/menu-manual", """
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
  <div>
    <div style="font-weight:700;font-size:0.85rem;margin-bottom:8px">🔍 Cari Bahan TKPI</div>
    <div style="border:1px solid #D1D5DB;border-radius:6px;padding:8px;font-size:0.8rem;background:white">
      <input style="width:100%;border:none;outline:none;font-size:0.82rem" placeholder="Ketik nama bahan... (mis: ayam)"/>
    </div>
    <div style="margin-top:8px;background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;padding:10px">
      <div style="font-size:0.78rem;font-weight:700;color:#1E40AF">Ayam Kampung (100g)</div>
      <div style="font-size:0.72rem;color:#374151">Energi: 179 kkal · Protein: 18.2g · Fe: 1.5mg</div>
      <div style="display:flex;gap:4px;margin-top:4px;align-items:center">
        <span style="font-size:0.72rem">Porsi:</span>
        <input style="width:50px;border:1px solid #D1D5DB;border-radius:4px;padding:2px 4px;font-size:0.75rem" value="150"/>
        <span style="font-size:0.72rem">g</span>
        <button style="background:#2563EB;color:white;border:none;border-radius:4px;padding:3px 8px;font-size:0.72rem;cursor:pointer">+ Tambah</button>
      </div>
    </div>
  </div>
  <div>
    <div style="font-weight:700;font-size:0.85rem;margin-bottom:8px">📊 Komposisi Menu</div>
    <table style="width:100%;font-size:0.75rem;border-collapse:collapse">
      <tr style="background:#F3F4F6"><td style="padding:4px 6px;font-weight:600">Bahan</td><td>Gram</td><td>Energi</td></tr>
      <tr style="border-bottom:1px solid #F3F4F6"><td style="padding:4px 6px">Ayam Kampung</td><td>150g</td><td>269kkal</td></tr>
      <tr style="border-bottom:1px solid #F3F4F6"><td style="padding:4px 6px">Nasi Putih</td><td>200g</td><td>260kkal</td></tr>
      <tr style="border-bottom:1px solid #F3F4F6"><td style="padding:4px 6px">Sayur Bayam</td><td>100g</td><td>36kkal</td></tr>
      <tr style="background:#D1FAE5"><td style="padding:4px 6px;font-weight:700">Total</td><td></td><td style="font-weight:700">565kkal</td></tr>
    </table>
    <div style="margin-top:8px;background:#FFFBEB;border:1px solid #FCD34D;border-radius:6px;padding:8px">
      <div style="font-size:0.72rem;font-weight:700;color:#92400E">AKG vs Target (SD 7-9)</div>
      <div style="margin-top:4px;background:#E5E7EB;border-radius:999px;height:8px">
        <div style="background:#059669;border-radius:999px;height:8px;width:75%"></div>
      </div>
      <div style="font-size:0.7rem;color:#6B7280;margin-top:2px">Energi: 75% dari target 750 kkal/hari</div>
    </div>
  </div>
</div>
""")

BAB4 = chapter(4, "🥗", "Build Menu Manual & Reverse Optimizer", "H-1 | Sore", f"""
{roles('nutritionist','kepala')}

{story('''
<strong>Sehari sebelum operasi (H-1), pukul 17:00.</strong> Ahli Gizi membuka laptop dengan secangkir teh.
Besok pagi produksi mulai jam 05:30 — menu harus sudah diapprove malam ini.
Dia buka DPMBG, pilih <strong>Build Menu Manual</strong> dari sidebar.
Gambaran sudah ada: nasi, ayam kampung, bayam, tempe. Tapi sebelum submit,
kandungan gizi harus memenuhi standar AKG untuk semua kelompok umur.
DPMBG hitung otomatis sambil dia input — tidak perlu buka Excel lagi.
''')}

<h3>Cara Membuka</h3>
{steps([
  ('Login sebagai <strong>Ahli Gizi</strong> atau <strong>Kepala SPPG</strong>', ''),
  ('Sidebar → klik grup <strong>▼ MENU & GIZI</strong>', ''),
  ('Klik <strong>Build Menu Manual</strong>', 'URL: /menu-manual'),
])}

<h3>Tampilan Build Menu Manual</h3>
{SCREEN_BUILD_MENU}

<h3>Langkah Menyusun Menu</h3>
{steps([
  ('Di kolom <strong>Cari Bahan TKPI</strong>, ketik nama bahan (contoh: "ayam") — hasil muncul otomatis (typeahead)', ''),
  ('Pilih bahan dari dropdown hasil pencarian', ''),
  ('Isi <strong>Porsi (gram)</strong> yang akan digunakan per 1.000 porsi', ''),
  ('Klik <strong>+ Tambah</strong> — bahan masuk ke tabel Komposisi Menu', ''),
  ('Ulangi untuk semua bahan menu hari ini (nasi, lauk, sayur, buah, susu jika ada)', ''),
  ('Pantau <strong>bar AKG</strong> di kanan — harus mencapai minimal 70% untuk setiap kelompok umur', ''),
  ('Lihat <strong>Cost per Porsi</strong> di bawah tabel — harus di bawah Rp 15.000', ''),
  ('Klik <strong>Simpan Draft</strong> jika belum selesai, atau <strong>Submit untuk Review</strong> jika sudah siap', ''),
])}

{feature_box('⚡', 'Reverse Optimizer — Bantu Susun Menu Otomatis', f"""
  <p>Tidak tahu harus mulai dari mana? Pakai <strong>Reverse Optimizer</strong>!
  Sistem akan mencari kombinasi bahan yang memenuhi target gizi dengan cost minimal
  menggunakan algoritma <em>linear programming</em>.</p>
  {steps([
    ('Di halaman Build Menu Manual, klik tab <strong>Optimizer Otomatis</strong>', ''),
    ('Set target: energi, protein, biaya maksimal per porsi', ''),
    ('Klik <strong>Hitung Otomatis</strong> — sistem menjalankan optimizer PuLP', ''),
    ('Review hasil rekomendasi bahan dan gramase yang disarankan', ''),
    ('Klik <strong>Pakai Rekomendasi Ini</strong> untuk memasukkan ke form manual', ''),
  ])}
  {tip('Optimizer bekerja berdasarkan harga bahan terkini dari database — hasil selalu up-to-date.')}
""")}

{feature_box('🔄', 'Cek Siklus 20 Hari', f"""
  <p>Menu MBG wajib memenuhi aturan rotasi: dalam 20 hari, bahan protein tertentu
  tidak boleh muncul terlalu sering (contoh: ayam maksimal 8 kali dalam 20 hari).
  DPMBG cek otomatis.</p>
  {steps([
    ('Di halaman Build Menu Manual, lihat panel <strong>Peringatan Siklus</strong>', ''),
    ('Jika muncul warning kuning, berarti bahan sudah hampir melewati batas frekuensi', ''),
    ('Jika warning merah, bahan sudah melebihi batas — wajib diganti sebelum submit', ''),
  ])}
  {data_table(
    ['Bahan', 'Batas Maksimal (20 hari)'],
    [
      ['Telur', '≤ 8 kali'],
      ['Ayam', '≤ 8 kali'],
      ['Tahu', '≤ 10 kali'],
      ['Tempe', '≤ 10 kali'],
      ['Ikan', '≤ 8 kali'],
      ['Daging Sapi', '≤ 4 kali'],
    ]
  )}
""")}

{warn('Menu yang melanggar siklus tidak bisa disubmit untuk review. Perbaiki bahan terlebih dahulu.')}

<h3>Forecast Kebutuhan Bahan</h3>
{steps([
  ('Sidebar → grup <strong>▼ MENU & GIZI</strong> → klik <strong>Build Menu Manual</strong>', ''),
  ('Klik tab <strong>Forecast</strong> di bagian atas halaman', ''),
  ('Pilih <strong>Dari tanggal</strong> dan <strong>Sampai tanggal</strong>', ''),
  ('Klik <strong>Hitung Forecast</strong> — sistem kalkulasi kebutuhan bahan × jumlah siswa × hari', ''),
  ('Lihat hasil: total gram per bahan, total biaya estimasi per periode', ''),
  ('Klik <strong>Export Excel</strong> untuk unduh laporan forecast', ''),
])}

{tip('Forecast sangat berguna untuk Akuntan (Akuntan) dalam membuat Purchase Order mingguan.')}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 5 — Menu Approval, Student Requests
# ─────────────────────────────────────────────────────────────────────────────

BAB5 = chapter(5, "✅", "Menu Approval & Siklus Persetujuan", "H-1 | Malam", f"""
{roles('kepala','nutritionist')}

{story('''
<strong>H-1, pukul 18:00.</strong> Ahli Gizi selesai menyusun menu dan menekan tombol <em>Submit untuk Review</em>.
Beberapa detik kemudian, notifikasi muncul di HP Kepala SPPG: "Menu baru perlu approval."
Kepala SPPG buka DPMBG, cek komposisi gizi dan siklus 20 hari, lalu klik <strong>Setujui</strong>.
Status menu berubah ke <em>Approved</em> — Kepala Chef bisa mulai produksi besok subuh berdasarkan menu ini.
''')}

<h3>Alur Status Menu</h3>
<!-- SHOT:menu_approval -->

{data_table(
  ['Status', 'Artinya', 'Siapa yang Bisa Ubah'],
  [
    [badge('Draft','gray'), 'Menu sedang disusun', 'Ahli Gizi'],
    [badge('Pending Review','amber'), 'Menunggu persetujuan Kepala SPPG', 'Ahli Gizi (submit), Kepala SPPG (review)'],
    [badge('Approved','green'), 'Disetujui, siap dieksekusi', 'Kepala SPPG'],
    [badge('Locked','blue'), 'Dikunci, tidak bisa diubah', 'Kepala SPPG'],
    [badge('Archived','gray'), 'Arsip historis', 'Kepala SPPG'],
  ]
)}

<h3>Submit Menu untuk Review (Ahli Gizi)</h3>
{steps([
  ('Selesaikan komposisi menu di Build Menu Manual', 'Sidebar → ▼ MENU & GIZI → Build Menu Manual'),
  ('Pastikan tidak ada warning merah di panel Siklus', ''),
  ('Klik tombol <strong>Submit untuk Review</strong>', ''),
  ('Tulis catatan opsional untuk Kepala SPPG', ''),
  ('Klik <strong>Konfirmasi Submit</strong> — status berubah ke Pending Review', ''),
])}

<h3>Menyetujui Menu (Kepala SPPG)</h3>
{steps([
  ('Buka notifikasi bell atau langsung ke halaman Approval', 'Sidebar → ▼ MENU & GIZI → Menu Approval'),
  ('Pilih filter <strong>Pending Review</strong> untuk melihat menu yang menunggu', ''),
  ('Klik menu yang ingin di-review — detail komposisi gizi muncul', ''),
  ('Review AKG per kelompok umur, cek siklus 20 hari, lihat cost per porsi', ''),
  ('Klik <strong>Setujui</strong> (approve) atau <strong>Kembalikan</strong> (reject) dengan catatan alasan', ''),
  ('Jika approve → status menu berubah ke Approved + notifikasi ke Ahli Gizi', ''),
])}

{tip('Kepala SPPG bisa langsung klik link dari notifikasi bell untuk langsung ke halaman approval menu yang bersangkutan.')}

<h3>Permintaan Khusus Siswa</h3>
{steps([
  ('Sidebar → ▼ MENU & GIZI → klik <strong>Permintaan Siswa</strong>', 'URL: /student-requests'),
  ('Klik <strong>+ Permintaan Baru</strong>', ''),
  ('Isi sekolah, kelas, keterangan alergi atau kebutuhan khusus', ''),
  ('Klik <strong>Simpan</strong>', ''),
  ('Untuk menyelesaikan permintaan: klik item → klik <strong>Tandai Selesai</strong> dengan catatan tindakan', ''),
])}

{info('Permintaan siswa (alergi, kebutuhan diet khusus) dicatat agar Ahli Gizi dan Kepala Chef bisa menyesuaikan menu atau porsi tertentu.')}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 6 — Purchase Orders & Supplier
# ─────────────────────────────────────────────────────────────────────────────

SCREEN_PO = screen("/purchase-orders", """
<div style="margin-bottom:12px;display:flex;justify-content:space-between;align-items:center">
  <div style="font-weight:700;font-size:0.9rem">Purchase Orders</div>
  <button style="background:#2563EB;color:white;border:none;border-radius:6px;padding:6px 14px;font-size:0.8rem">+ Buat PO</button>
</div>
<table style="width:100%;font-size:0.78rem;border-collapse:collapse">
  <tr style="background:#F3F4F6">
    <th style="padding:6px 8px;text-align:left">No. PO</th>
    <th>Supplier</th><th>Tgl Order</th><th>Total</th><th>Status</th>
  </tr>
  <tr style="border-bottom:1px solid #F3F4F6">
    <td style="padding:6px 8px;font-family:monospace;font-size:0.72rem">PO-20260501-001</td>
    <td>UD Sumber Tani</td><td>01 Mei 2026</td><td>Rp 4.250.000</td>
    <td><span style="background:#D1FAE5;color:#065F46;border-radius:999px;padding:2px 8px;font-size:0.7rem;font-weight:600">Diterima</span></td>
  </tr>
  <tr style="border-bottom:1px solid #F3F4F6;background:#F9FAFB">
    <td style="padding:6px 8px;font-family:monospace;font-size:0.72rem">PO-20260501-002</td>
    <td>CV Berkah Jaya</td><td>01 Mei 2026</td><td>Rp 1.800.000</td>
    <td><span style="background:#FEF3C7;color:#92400E;border-radius:999px;padding:2px 8px;font-size:0.7rem;font-weight:600">Pending</span></td>
  </tr>
</table>
""")

BAB6 = chapter(6, "📦", "Purchase Order & Manajemen Supplier", "H-1 | Siang", f"""
{roles('accountant','kepala')}

{story('''
<strong>H-1, pukul 13:00.</strong> Akuntan membuka halaman Purchase Orders. Supplier harus tahu pesanan
paling lambat sore ini supaya bisa siapkan barang untuk pengiriman subuh besok jam 04:00.
Berdasarkan forecast dari menu yang sudah diapprove, dia perlu memesan ayam kampung 50 kg
dan bayam 30 kg dari UD Sumber Tani. Klik <em>Buat PO</em>, pilih supplier, tambah item —
dalam 5 menit PO tersimpan dan supplier bisa dihubungi untuk konfirmasi.
''')}

<h3>Daftar Purchase Orders</h3>
{SCREEN_PO}

<h3>Membuat Purchase Order Baru</h3>
{steps([
  ('Sidebar → klik grup <strong>▼ PENERIMAAN</strong>', ''),
  ('Klik <strong>Purchase Orders</strong>', 'URL: /purchase-orders'),
  ('Klik tombol <strong>+ Buat PO</strong>', ''),
  ('Pilih <strong>Supplier</strong> dari dropdown (berdasarkan master data supplier)', ''),
  ('Isi <strong>Tanggal Order</strong> dan <strong>Tanggal Diharapkan Tiba</strong>', ''),
  ('Klik <strong>+ Tambah Item</strong> — pilih bahan, isi kuantitas dan satuan', ''),
  ('Ulangi untuk semua bahan yang dipesan', ''),
  ('Klik <strong>Simpan PO</strong> — nomor PO otomatis digenerate (PO-YYYYMMDD-XXX)', ''),
])}

{feature_box('⚡', 'Auto-Generate PO dari Forecast', f"""
  <p>Tidak perlu input manual jika sudah punya forecast! Sistem bisa generate PO otomatis.</p>
  {steps([
    ('Sidebar → ▼ PENERIMAAN → Purchase Orders', ''),
    ('Klik <strong>Generate dari Forecast</strong>', ''),
    ('Pilih periode forecast dan supplier untuk masing-masing bahan', ''),
    ('Review quantities yang disarankan sistem', ''),
    ('Klik <strong>Buat PO Otomatis</strong>', ''),
  ])}
""")}

<h3>Tren Harga & Alert Spike</h3>
{steps([
  ('Sidebar → ▼ PENERIMAAN → klik <strong>Tren Harga</strong>', 'URL: /finance (tab Tren Harga)'),
  ('Pilih bahan dari dropdown untuk melihat grafik harga 30/60/90 hari terakhir', ''),
  ('Cek kolom <strong>WoW%</strong> (Week-over-Week change) — perubahan harga minggu ini vs minggu lalu', ''),
  ('Alert merah muncul otomatis jika kenaikan harga ≥15%', ''),
])}

{warn('Jika ada spike alert merah pada bahan utama, laporkan ke Kepala SPPG sebelum membuat PO baru — mungkin perlu cari supplier alternatif.')}

<h3>Manajemen Supplier</h3>
{steps([
  ('Sidebar → ▼ MASTER DATA → klik <strong>Supplier</strong>', 'URL: /admin/suppliers'),
  ('Lihat daftar semua supplier aktif beserta rating mereka', ''),
  ('Klik <strong>+ Tambah Supplier</strong> untuk mendaftarkan supplier baru', ''),
  ('Isi nama, kontak, alamat, dan kategori bahan yang disuplai', ''),
  ('Rating supplier otomatis turun setiap kali bahan dari supplier tersebut <strong>ditolak</strong> saat inspeksi', ''),
])}

{data_table(
  ['Kolom Supplier', 'Artinya'],
  [
    ['Nama', 'Nama resmi usaha supplier'],
    ['Kontak', 'No. HP atau email PIC supplier'],
    ['Kategori', 'Jenis bahan yang biasa disuplai'],
    ['Rating', 'Score 1-5 berbasis histori penerimaan (auto-update)'],
    ['Default Item', 'Bahan-bahan yang biasanya dipesan dari supplier ini'],
  ]
)}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 7 — Joint Inspection
# ─────────────────────────────────────────────────────────────────────────────

SVG_INSPECTION_FLOW = """<svg viewBox="0 0 640 130" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;font-family:Inter,sans-serif">
  <rect x="0" y="0" width="640" height="130" rx="10" fill="#F8FAFC"/>
  <defs><marker id="arr2" markerWidth="8" markerHeight="6" refX="6" refY="3" orient="auto">
    <path d="M0,0 L0,6 L8,3 z" fill="#94A3B8"/>
  </marker></defs>
  <!-- steps -->
  <rect x="10" y="40" width="100" height="50" rx="8" fill="#DBEAFE" stroke="#93C5FD"/>
  <text x="60" y="61" text-anchor="middle" fill="#1E40AF" font-size="9" font-weight="700">1. Buat</text>
  <text x="60" y="75" text-anchor="middle" fill="#1E40AF" font-size="9">Inspeksi</text>
  <text x="60" y="88" text-anchor="middle" fill="#6B7280" font-size="8">(ASLAP)</text>
  <rect x="130" y="40" width="100" height="50" rx="8" fill="#D1FAE5" stroke="#6EE7B7"/>
  <text x="180" y="61" text-anchor="middle" fill="#065F46" font-size="9" font-weight="700">2. Tanda</text>
  <text x="180" y="75" text-anchor="middle" fill="#065F46" font-size="9">Tangan Gizi</text>
  <text x="180" y="88" text-anchor="middle" fill="#6B7280" font-size="8">(Ahli Gizi)</text>
  <rect x="250" y="40" width="100" height="50" rx="8" fill="#FEF3C7" stroke="#FCD34D"/>
  <text x="300" y="61" text-anchor="middle" fill="#92400E" font-size="9" font-weight="700">3. Tanda</text>
  <text x="300" y="75" text-anchor="middle" fill="#92400E" font-size="9">Tangan Akun</text>
  <text x="300" y="88" text-anchor="middle" fill="#6B7280" font-size="8">(Akuntan)</text>
  <rect x="370" y="40" width="100" height="50" rx="8" fill="#FEE2E2" stroke="#FCA5A5"/>
  <text x="420" y="61" text-anchor="middle" fill="#991B1B" font-size="9" font-weight="700">4. Tanda</text>
  <text x="420" y="75" text-anchor="middle" fill="#991B1B" font-size="9">Tangan Fisik</text>
  <text x="420" y="88" text-anchor="middle" fill="#6B7280" font-size="8">(ASLAP)</text>
  <rect x="490" y="40" width="140" height="50" rx="8" fill="#E0E7FF" stroke="#A5B4FC"/>
  <text x="560" y="61" text-anchor="middle" fill="#3730A3" font-size="9" font-weight="700">5. Finalisasi</text>
  <text x="560" y="75" text-anchor="middle" fill="#3730A3" font-size="9">Container Split</text>
  <text x="560" y="88" text-anchor="middle" fill="#6B7280" font-size="8">(Cetak Label)</text>
  <!-- arrows -->
  <line x1="110" y1="65" x2="128" y2="65" stroke="#94A3B8" stroke-width="2" marker-end="url(#arr2)"/>
  <line x1="230" y1="65" x2="248" y2="65" stroke="#94A3B8" stroke-width="2" marker-end="url(#arr2)"/>
  <line x1="350" y1="65" x2="368" y2="65" stroke="#94A3B8" stroke-width="2" marker-end="url(#arr2)"/>
  <line x1="470" y1="65" x2="488" y2="65" stroke="#94A3B8" stroke-width="2" marker-end="url(#arr2)"/>
</svg>"""

BAB7 = chapter(7, "🔍", "Inspeksi Bersama — 3 Tanda Tangan Digital", "04:00", f"""
{roles('aslap','nutritionist','accountant','kepala')}

{story('''
<strong>04:00 subuh.</strong> Truk supplier UD Sumber Tani tiba di halaman dapur. ASLAP yang sudah standby
langsung buka DPMBG di tabletnya dan buat inspeksi baru yang otomatis memuat line item dari PO kemarin.
Dia catat bobot aktual per container. Ahli Gizi tanda tangan digital untuk kualitas gizi.
Akuntan tanda tangan untuk kuantitas sesuai PO. ASLAP tanda tangan terakhir untuk kondisi fisik.
Tiga tanda tangan, semua digital, semua timestamped. Dalam 45 menit bahan sudah masuk gudang —
Kepala Chef bisa mulai masak jam 05:30.
''')}

<h3>Alur Inspeksi Bersama</h3>
<!-- SHOT:inspections -->

<h3>Langkah 1: Buat Inspeksi Baru (ASLAP)</h3>
{steps([
  ('Sidebar → klik grup <strong>▼ PENERIMAAN</strong> → klik <strong>Inspeksi Bersama</strong>', 'URL: /inspections'),
  ('Klik <strong>+ Inspeksi Baru</strong>', ''),
  ('Pilih <strong>Purchase Order</strong> terkait dari dropdown', ''),
  ('Isi tanggal dan waktu kedatangan supplier', ''),
  ('Klik <strong>Buat Inspeksi</strong> — nomor inspeksi otomatis (INS-YYYYMMDD-XXX)', ''),
])}

<h3>Langkah 2: Input Item per Container</h3>
{steps([
  ('Di halaman inspeksi, klik <strong>+ Tambah Item</strong>', ''),
  ('Pilih bahan sesuai PO, isi <strong>Kuantitas Diterima</strong>, <strong>Kondisi</strong> (Baik/Cacat), dan catatan', ''),
  ('Ulangi untuk semua bahan dalam pengiriman', ''),
  ('Untuk bahan cacat: pilih kondisi <strong>Cacat</strong> dan klik <strong>Ajukan Dispute</strong> ke supplier', ''),
])}

{feature_box('📦', 'Container Split — Pisah Jadi Beberapa Wadah', f"""
  <p>Bahan yang masuk dalam jumlah besar perlu dipecah ke beberapa container
  agar distribusi ke sekolah lebih efisien.</p>
  {steps([
    ('Di halaman inspeksi, setelah semua item diinput, klik <strong>Pecah Container</strong>', ''),
    ('Pilih item yang akan dipecah', ''),
    ('Akuntan input <strong>jumlah container yang direncanakan</strong>; ASLAP input <strong>jumlah aktual</strong>', ''),
    ('Sistem generate barcode unik untuk setiap container (format: BHN-XXXXXXXX)', ''),
    ('Klik <strong>Cetak Label</strong> untuk print label barcode ke label printer', ''),
  ])}
  {tip('Setiap container punya barcode unik. Kepala Chef bisa scan barcode ini saat batch produksi untuk debit stok FIFO otomatis.')}
""")}

<h3>Langkah 3-5: Tanda Tangan Digital</h3>
{steps([
  ('<strong>Ahli Gizi</strong> login → buka inspeksi yang sedang berjalan → klik <strong>Tanda Tangan Kualitas Gizi</strong>', 'Memverifikasi kandungan gizi dan kesegaran bahan'),
  ('<strong>Akuntan</strong> login → buka inspeksi → klik <strong>Tanda Tangan Kuantitas</strong>', 'Memverifikasi bobot/jumlah sesuai PO'),
  ('<strong>ASLAP</strong> login → buka inspeksi → klik <strong>Tanda Tangan Kondisi Fisik</strong>', 'Memverifikasi kondisi fisik kemasan dan tidak ada kontaminasi'),
  ('Setelah 3 tanda tangan lengkap, klik <strong>Finalisasi Inspeksi</strong>', 'Status berubah ke Selesai, stok bahan otomatis bertambah'),
])}

{warn('Inspeksi hanya bisa difinalisasi setelah KETIGA tanda tangan diberikan. Jika salah satu penandatangan tidak hadir, Kepala SPPG bisa memberikan tanda tangan pengganti.')}

<h3>Dispute & Penolakan Bahan</h3>
{steps([
  ('Jika ada bahan yang tidak sesuai (busuk, kurang berat, dll), klik <strong>Tolak Bahan</strong> pada item tersebut', ''),
  ('Isi alasan penolakan dan bukti (teks)', ''),
  ('Klik <strong>Buat Dispute</strong> — dispute tercatat dengan nomor referensi', ''),
  ('Rating supplier otomatis turun 1 poin untuk setiap penolakan', ''),
  ('Dispute bisa diselesaikan setelah supplier memberikan penggantian: klik <strong>Selesaikan Dispute</strong>', ''),
])}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 8 — Produksi Batch & QR Scan
# ─────────────────────────────────────────────────────────────────────────────

BAB8 = chapter(8, "🍳", "Produksi Batch & QR Scan Tablet", "05:30", f"""
{roles('chef','kepala','nutritionist')}

{story('''
<strong>05:30 pagi.</strong> Inspeksi selesai, semua bahan sudah masuk gudang dan di-scan ke inventori.
Kepala Chef buka DPMBG di tablet yang dipasang di tembok dapur, pilih menu yang sudah Approved
kemarin malam, dan klik <em>Mulai Batch Baru</em>. Timer 6 jam mulai berjalan — BGN mewajibkan
makanan dikonsumsi maksimal 6 jam dari selesai masak. Setiap container bahan yang diambil dari
gudang di-scan barcodenya. Sistem otomatis catat pemakaian dan kurangi stok dengan metode FIFO —
container paling lama masuk, paling pertama terpakai.
''')}

<h3>Memulai Batch Produksi</h3>
{steps([
  ('Sidebar → klik grup <strong>▼ OPERASI DAPUR</strong> → klik <strong>Produksi Batch</strong>', 'URL: /production'),
  ('Klik <strong>+ Batch Baru</strong>', ''),
  ('Pilih <strong>Menu</strong> yang sudah Approved untuk hari ini', ''),
  ('Isi <strong>Target Porsi</strong> untuk batch ini', ''),
  ('Klik <strong>Mulai Batch</strong> — timer otomatis berjalan', ''),
])}

{feature_box('📱', 'QR Scan Container — Debit Stok FIFO', f"""
  <p>Saat memasak, Kepala Chef scan barcode setiap container bahan yang digunakan.
  Sistem otomatis catat dan kurangi stok dengan metode <strong>FIFO</strong>
  (First In First Out — container paling lama masuk, paling pertama dipakai).</p>
  {steps([
    ('Di halaman Produksi, klik <strong>Scan Container</strong>', ''),
    ('Izinkan browser mengakses kamera', ''),
    ('Arahkan kamera tablet ke barcode container (BHN-XXXXXXXX)', ''),
    ('Sistem otomatis membaca barcode dan menampilkan info bahan', ''),
    ('Konfirmasi jumlah yang digunakan (gram)', ''),
    ('Klik <strong>Catat Penggunaan</strong> — stok terkurangi otomatis', ''),
  ])}
  {tip('Scan minimal setiap 10 container (MEALS_PER_SCAN=10). Tidak perlu scan per gram — cukup scan saat ambil container baru.')}
  {warn('Jika kamera tidak bisa scan, gunakan tombol <strong>Input Manual</strong> dan ketik kode BHN secara manual.')}
""")}

<h3>Selama Produksi Berjalan</h3>
{steps([
  ('Monitor progress di halaman Produksi: porsi terproduksi vs target (progress bar)', ''),
  ('Tambahkan catatan observasi jika ada kejadian penting: klik <strong>+ Catatan</strong>', ''),
  ('Jika ada bahan tambahan diperlukan: klik <strong>Tambah Bahan</strong> dan scan container tambahan', ''),
])}

<h3>Mengakhiri Batch & Approve QC</h3>
{steps([
  ('Setelah semua porsi selesai, klik <strong>Selesaikan Batch</strong>', ''),
  ('Isi jumlah porsi aktual yang berhasil diproduksi', ''),
  ('<strong>Ahli Gizi</strong> login → di halaman Produksi → klik <strong>Approve QC</strong>', 'Memverifikasi kualitas masakan sesuai standar gizi'),
  ('Batch status berubah ke <strong>QC Approved</strong> — siap untuk distribusi', ''),
])}

<h3>Sampel Makanan (Wajib BGN)</h3>
{steps([
  ('Di halaman Produksi, setelah batch selesai, klik <strong>Catat Sampel</strong>', ''),
  ('Isi informasi: label sampel, waktu pengambilan, lokasi penyimpanan', ''),
  ('Sampel wajib disimpan minimal <strong>48 jam</strong> (standar BGN untuk traceability keamanan pangan)', ''),
  ('Sistem otomatis menandai sampel yang sudah melewati 48 jam sebagai "Bisa Dibuang"', ''),
])}

{info('Pencatatan sampel makanan adalah persyaratan wajib BGN. Dokumen ini bisa diexport dalam BGN Compliance Bundle (Bab 12).')}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 9 — Distribusi Makanan ke Sekolah
# ─────────────────────────────────────────────────────────────────────────────

SVG_WAVE = """<svg viewBox="0 0 560 120" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;font-family:Inter,sans-serif">
  <rect x="0" y="0" width="560" height="120" rx="10" fill="#F8FAFC"/>
  <rect x="10" y="10" width="250" height="100" rx="8" fill="#EFF6FF" stroke="#93C5FD" stroke-width="2"/>
  <text x="135" y="35" text-anchor="middle" fill="#1E40AF" font-size="11" font-weight="700">🚌 Gelombang 1 — Pagi</text>
  <text x="135" y="52" text-anchor="middle" fill="#374151" font-size="9">PAUD / TK / SD Kelas 1-6</text>
  <text x="135" y="68" text-anchor="middle" fill="#374151" font-size="9">Target delivery: 08:30 – 09:30</text>
  <text x="135" y="85" text-anchor="middle" fill="#059669" font-size="9" font-weight="600">✓ Prioritas utama</text>
  <rect x="300" y="10" width="250" height="100" rx="8" fill="#FEF3C7" stroke="#FCD34D" stroke-width="2"/>
  <text x="425" y="35" text-anchor="middle" fill="#92400E" font-size="11" font-weight="700">🚌 Gelombang 2 — Siang</text>
  <text x="425" y="52" text-anchor="middle" fill="#374151" font-size="9">SD Kelas 7-9 / SMP</text>
  <text x="425" y="68" text-anchor="middle" fill="#374151" font-size="9">Target delivery: 10:30 – 12:00</text>
  <text x="425" y="85" text-anchor="middle" fill="#D97706" font-size="9" font-weight="600">✓ Setelah gelombang 1 selesai</text>
</svg>"""

BAB9 = chapter(9, "🚚", "Distribusi Makanan ke Sekolah", "08:00 / 10:00", f"""
{roles('aslap','kepala')}

{story('''
<strong>08:00 pagi.</strong> Produksi selesai jam 07:30 dan makanan sudah dikemas. ASLAP di parkiran
dengan dua truk siap jalan untuk Gelombang 1: PAUD, TK, dan SD kelas 1-3 — sekolah yang
makan lebih pagi. Dia buka DPMBG, input jumlah per sekolah, klik <em>Dispatch</em>, dan truk jalan.
Jam 10:00 Gelombang 2 jalan untuk SD kelas 4-6 dan SMP. Sejam setelah dispatch,
notifikasi konfirmasi mulai masuk satu per satu dari guru di setiap sekolah — semua tercatat otomatis.
''')}

<h3>Sistem Gelombang (Wave Classifier)</h3>
<!-- SHOT:distributions -->

<h3>Mendispatch Pengiriman</h3>
{steps([
  ('Sidebar → klik grup <strong>▼ DISTRIBUSI</strong> → klik <strong>Distribusi Makanan</strong>', 'URL: /distributions'),
  ('Pilih tab <strong>Gelombang 1</strong> atau <strong>Gelombang 2</strong> sesuai jadwal', ''),
  ('Lihat daftar sekolah dan target porsi untuk masing-masing sekolah', ''),
  ('Isi <strong>Jumlah Dikirim</strong> untuk setiap sekolah', ''),
  ('Pilih <strong>Driver</strong> dan <strong>Kendaraan</strong> dari dropdown', ''),
  ('Klik <strong>Dispatch Gelombang</strong> — status semua sekolah dalam gelombang berubah ke "Dikirim"', ''),
])}

<h3>Konfirmasi Terima oleh Guru Sekolah (Tanpa Login)</h3>
{steps([
  ('Guru menerima link konfirmasi (dikirim via WhatsApp atau scan QR di DPMBG)', ''),
  ('Guru buka link di HP — <strong>tidak perlu login</strong>', 'URL: /confirm/<token>'),
  ('Halaman menampilkan: nama sekolah, tanggal, jumlah porsi yang dikirim', ''),
  ('Guru isi <strong>Jumlah Diterima Aktual</strong> dan klik <strong>Konfirmasi Terima</strong>', ''),
  ('Jika ada sisa: isi <strong>Sisa Makanan</strong> yang tidak terdistribusi ke siswa', ''),
  ('Klik <strong>Submit Konfirmasi</strong> — tercatat dengan timestamp', ''),
])}

{tip('Guru tidak perlu punya akun DPMBG. Link konfirmasi adalah halaman publik yang hanya bisa diakses sekali per pengiriman.')}

<h3>Dashboard Agregat Distribusi</h3>
{steps([
  ('Di halaman Distribusi, scroll ke bawah untuk melihat <strong>Rekap Hari Ini</strong>', ''),
  ('Lihat per-sekolah: target porsi / dikirim / dikonfirmasi / sisa', ''),
  ('Sekolah yang belum konfirmasi tampil dengan status <strong>Menunggu</strong> (kuning)', ''),
  ('Sekolah yang sudah konfirmasi tampil <strong>Terkonfirmasi</strong> (hijau)', ''),
])}

<h3>Input Sisa Makanan (Leftover)</h3>
{steps([
  ('Saat kembali dari pengiriman, ASLAP input sisa makanan yang dibawa kembali', ''),
  ('Sidebar → ▼ DISTRIBUSI → klik <strong>Sisa Makanan</strong>', ''),
  ('Isi jumlah sisa per kategori, alasan (over-estimate / siswa absen / dll)', ''),
  ('Klik <strong>Simpan</strong> — data leftover tersimpan untuk analisis efisiensi', ''),
])}

{data_table(
  ['Kolom Dashboard', 'Artinya'],
  [
    ['Target', 'Jumlah porsi yang seharusnya diterima sekolah hari ini'],
    ['Dikirim', 'Jumlah yang di-dispatch oleh ASLAP'],
    ['Dikonfirmasi', 'Jumlah yang dikonfirmasi guru diterima'],
    ['Sisa', 'Sisa yang tidak terdistribusi ke siswa (dilaporkan guru)'],
    ['Gap', 'Dikirim minus Dikonfirmasi — idealnya 0'],
  ]
)}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 10 — ASLAP
# ─────────────────────────────────────────────────────────────────────────────

BAB10 = chapter(10, "🦺", "Pengawasan Lapangan — ASLAP", "06:00", f"""
{roles('aslap','kepala')}

{story('''
<strong>06:00 pagi.</strong> Inspeksi bahan selesai, Kepala Chef sudah mulai masak. ASLAP sekarang
punya 20 menit untuk checklist harian sebelum sibuk persiapan pengiriman. Dia buka tab
<em>Dasbor ASLAP</em> di DPMBG — checklist kebersihan, suhu kompor, cuci tangan, kondisi
sampah, dan test kualitas air. Semua diisi dengan foto sebagai bukti.
Siang harinya dia isi observasi produksi dan logbook komunikasi sekolah.
Laporan mingguan akan di-generate hari Jumat.
''')}

<h3>Membuka Dasbor ASLAP</h3>
{steps([
  ('Sidebar → klik grup <strong>▼ LAPANGAN (ASLAP)</strong> → klik <strong>Dasbor ASLAP</strong>', 'URL: /aslap'),
  ('Dashboard menampilkan 5 tab: Checklist, Kualitas Air, Observasi Produksi, Log Komunikasi, Laporan Mingguan', ''),
])}

{feature_box('✅', 'Checklist Harian', f"""
  {steps([
    ('Klik tab <strong>Checklist</strong>', ''),
    ('Checklist hari ini sudah terisi template standar (bisa dikustomisasi Kepala SPPG)', ''),
    ('Centang setiap item yang sudah dipenuhi — ada keterangan wajib untuk item yang tidak centang', ''),
    ('Klik <strong>Simpan Checklist</strong> — timestamp otomatis tercatat', ''),
  ])}
  {data_table(
    ['Contoh Item Checklist', 'Kategori'],
    [
      ['Kebersihan area persiapan makanan ✓', 'Sanitasi'],
      ['Suhu penyimpanan bahan dingin <4°C ✓', 'Penyimpanan'],
      ['APD lengkap (sarung tangan, masker) ✓', 'K3'],
      ['APAR dalam kondisi baik ✓', 'Keselamatan'],
      ['Wastafel berfungsi dan bersabun ✓', 'Sanitasi'],
    ]
  )}
""")}

{feature_box('💧', 'Kualitas Air', f"""
  {steps([
    ('Klik tab <strong>Kualitas Air</strong>', ''),
    ('Klik <strong>+ Catat Pengukuran</strong>', ''),
    ('Isi nilai <strong>TDS</strong> (Total Dissolved Solids, satuan ppm) dan <strong>pH</strong>', ''),
    ('Sistem otomatis evaluasi: TDS harus <500 ppm, pH harus 6.5–8.5', ''),
    ('Jika melebihi ambang batas → alert merah muncul otomatis + notifikasi ke Kepala SPPG', ''),
    ('Klik <strong>Simpan</strong>', ''),
  ])}
  {warn('TDS > 500 ppm atau pH di luar 6.5–8.5 = air tidak layak masak. Hentikan penggunaan dan laporkan segera ke Kepala SPPG.')}
""")}

{feature_box('👁️', 'Observasi Produksi & Log Komunikasi Sekolah', f"""
  <p><strong>Observasi Produksi:</strong> Catat temuan penting selama proses produksi berlangsung
  (contoh: temperature kontrol tidak terpenuhi, bahan terlihat kurang segar, dll).</p>
  {steps([
    ('Klik tab <strong>Observasi Produksi</strong> → <strong>+ Observasi Baru</strong>', ''),
    ('Isi kategori (Higienitas/Suhu/Bahan/Proses), deskripsi, dan tingkat urgensi', ''),
    ('Klik <strong>Simpan</strong>', ''),
  ])}
  <p style="margin-top:12px"><strong>Log Komunikasi Sekolah:</strong> Catat setiap komunikasi dengan pihak sekolah
  yang berkaitan dengan distribusi atau keluhan.</p>
  {steps([
    ('Klik tab <strong>Log Komunikasi</strong> → <strong>+ Log Baru</strong>', ''),
    ('Pilih sekolah, metode komunikasi (telepon/WA/tatap muka), dan ringkasan isi komunikasi', ''),
    ('Klik <strong>Simpan</strong>', ''),
  ])}
""")}

<h3>Laporan Mingguan ASLAP</h3>
{steps([
  ('Klik tab <strong>Laporan Mingguan</strong>', ''),
  ('Pilih minggu yang ingin dilaporkan', ''),
  ('Klik <strong>Generate Laporan</strong> — sistem agregasi otomatis dari semua data minggu tersebut', ''),
  ('Review ringkasan: total checklist, rata-rata kualitas air, jumlah observasi, log komunikasi', ''),
  ('Tambahkan catatan narasi manual jika perlu', ''),
  ('Klik <strong>Submit Laporan</strong> — laporan dikirim ke Kepala SPPG untuk ditandatangani', ''),
  ('<strong>Kepala SPPG</strong> login → buka laporan → klik <strong>Tanda Tangan & Setujui</strong>', ''),
])}

{info('Laporan mingguan ASLAP adalah bagian dari BGN Compliance Bundle yang diekspor untuk pelaporan ke pemerintah.')}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 11 — Keuangan
# ─────────────────────────────────────────────────────────────────────────────

BAB11 = chapter(11, "💰", "Keuangan — Expense, LRA & Tren Harga", "13:00", f"""
{roles('accountant','kepala')}

{story('''
<strong>13:00 siang.</strong> Akuntan selesai makan siang dan kembali ke meja kerjanya.
Saatnya urusan keuangan. Dia buka DPMBG, langsung ke modul Keuangan.
Ada beberapa pengeluaran operasional hari ini yang perlu dicatat,
laporan LRA biweekly hampir jatuh tempo (tinggal 2 hari),
dan ada satu bahan yang harganya naik 18% dari minggu lalu — perlu alert.
Semua dia urus dalam satu platform.
''')}

<h3>Membuka Modul Keuangan</h3>
{steps([
  ('Sidebar → klik grup <strong>▼ KEUANGAN</strong>', ''),
  ('4 sub-modul tersedia: Tren Harga, Expense Tracker, LRA Biweekly, Pembayaran Relawan', ''),
])}

{feature_box('📈', 'Tren Harga & Spike Alert', f"""
  {steps([
    ('Sidebar → ▼ KEUANGAN → klik <strong>Tren Harga</strong>', 'URL: /finance → tab Tren Harga'),
    ('Pilih bahan dari dropdown untuk melihat grafik harga historis', ''),
    ('Lihat kolom <strong>WoW%</strong> — perubahan harga minggu ini vs minggu lalu', ''),
    ('Baris merah = spike alert (kenaikan ≥15%)', ''),
    ('Klik bahan yang spike untuk melihat detail riwayat harga dan supplier alternatif', ''),
  ])}
  {warn('Spike alert ≥15% berarti cost per porsi berisiko melewati batas Rp 15.000. Pertimbangkan substitusi bahan atau negosiasi ulang dengan supplier.')}
""")}

{feature_box('🧾', 'Expense Tracker', f"""
  {steps([
    ('Sidebar → ▼ KEUANGAN → klik <strong>Expense</strong>', ''),
    ('Klik <strong>+ Catat Pengeluaran</strong>', ''),
    ('Pilih <strong>Kategori</strong> dari 8 pilihan:', ''),
  ])}
  {data_table(
    ['Kategori', 'Contoh'],
    [
      ['Bahan Makanan', 'Pembelian ayam, beras, sayuran'],
      ['Kemasan', 'Kotak makan, plastik wrap, sendok'],
      ['Operasional', 'Gas LPG, listrik, air'],
      ['Transportasi', 'BBM kendaraan distribusi'],
      ['Kebersihan', 'Sabun, deterjen, alat kebersihan'],
      ['APD & K3', 'Sarung tangan, masker, boot'],
      ['Maintenance', 'Servis peralatan dapur'],
      ['Lain-lain', 'Pengeluaran tidak terkategori di atas'],
    ]
  )}
  {steps([
    ('Isi jumlah (Rp), tanggal, keterangan, dan lampirkan bukti (opsional)', ''),
    ('Klik <strong>Simpan</strong>', ''),
    ('Dashboard otomatis update <strong>Cost per Porsi Hari Ini</strong>', ''),
  ])}
""")}

{feature_box('📋', 'LRA Biweekly (Laporan Realisasi Anggaran)', f"""
  <p>LRA adalah laporan keuangan wajib setiap 2 minggu yang merangkum seluruh pemasukan dan pengeluaran SPPG.</p>
  {steps([
    ('Sidebar → ▼ KEUANGAN → klik <strong>LRA Biweekly</strong>', ''),
    ('Klik <strong>+ Generate LRA Baru</strong>', ''),
    ('Pilih periode (contoh: 16 Apr – 30 Apr 2026)', ''),
    ('Klik <strong>Generate</strong> — sistem agregasi otomatis dari semua expense dan transaksi periode tersebut', ''),
    ('Review ringkasan: total pemasukan, total pengeluaran per kategori, surplus/defisit', ''),
    ('Tambahkan catatan narasi jika ada penjelasan khusus', ''),
    ('Klik <strong>Submit LRA</strong> — dikirim ke Kepala SPPG untuk ditandatangani', ''),
    ('<strong>Kepala SPPG</strong> login → klik <strong>Tanda Tangan LRA</strong> → selesai', ''),
  ])}
  {tip('LRA yang sudah ditandatangani masuk otomatis ke BGN Compliance Bundle. Tidak perlu input ulang.')}
""")}

{feature_box('👥', 'Pembayaran Relawan', f"""
  {steps([
    ('Sidebar → ▼ KEUANGAN → klik <strong>Relawan</strong>', ''),
    ('Klik <strong>+ Catat Pembayaran</strong>', ''),
    ('Isi nama relawan, peran, jumlah honor, dan tanggal pembayaran', ''),
    ('Klik <strong>Simpan</strong> — tercatat di expense kategori khusus relawan', ''),
  ])}
""")}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 12 — Executive Dashboard
# ─────────────────────────────────────────────────────────────────────────────

SCREEN_EXEC = screen("/executive", f"""
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;margin-bottom:14px">
  <div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;padding:10px;text-align:center">
    <div style="font-size:1.5rem;font-weight:800;color:#1E40AF">1.520</div>
    <div style="font-size:0.7rem;color:#6B7280">Target Porsi</div>
  </div>
  <div style="background:#ECFDF5;border:1px solid #6EE7B7;border-radius:8px;padding:10px;text-align:center">
    <div style="font-size:1.5rem;font-weight:800;color:#065F46">98.2%</div>
    <div style="font-size:0.7rem;color:#6B7280">Konfirmasi Sekolah</div>
  </div>
  <div style="background:#FFFBEB;border:1px solid #FCD34D;border-radius:8px;padding:10px;text-align:center">
    <div style="font-size:1.5rem;font-weight:800;color:#92400E">Rp13.2K</div>
    <div style="font-size:0.7rem;color:#6B7280">Cost per Porsi</div>
  </div>
  <div style="background:#FEF2F2;border:1px solid #FCA5A5;border-radius:8px;padding:10px;text-align:center">
    <div style="font-size:1.5rem;font-weight:800;color:#991B1B">0.8%</div>
    <div style="font-size:0.7rem;color:#6B7280">Defect Rate</div>
  </div>
</div>
<div style="background:#F0FDF4;border:1px solid #6EE7B7;border-radius:10px;padding:14px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <div style="font-weight:700;font-size:0.9rem">🎯 Skor Kepatuhan BGN</div>
    <div style="font-size:1.8rem;font-weight:800;color:#059669">87 <span style="font-size:1rem;color:#065F46">/ 100</span></div>
  </div>
  <div style="background:#D1FAE5;border-radius:999px;height:10px">
    <div style="background:linear-gradient(90deg,#059669,#10B981);border-radius:999px;height:10px;width:87%"></div>
  </div>
  <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:0.72rem;color:#374151">
    <span>Inspeksi 90%</span><span>Menu Approved 95%</span><span>Distribusi 98%</span><span>LRA 85%</span><span>Checklist 80%</span>
  </div>
  <div style="text-align:right;margin-top:4px"><span style="background:#059669;color:white;border-radius:999px;padding:2px 10px;font-size:0.75rem;font-weight:700">Grade A</span></div>
</div>
""")

BAB12 = chapter(12, "📊", "Dashboard Eksekutif & BGN Compliance Bundle", "14:00", f"""
{roles('kepala','super','platform')}

{story('''
<strong>14:00 siang.</strong> Kepala SPPG duduk di mejanya dengan secangkir kopi.
Saatnya review harian. Dia buka tab <em>Eksekutif</em> di DPMBG.
Dalam satu layar: 1.520 porsi target, 98.2% sekolah sudah konfirmasi terima,
cost per porsi Rp 13.200 (masih aman di bawah target Rp 15.000), defect rate 0.8%.
Skor kepatuhan BGN: 87/100 — Grade A. Hari yang baik.
Dia klik <em>Export BGN Bundle</em> dan file JSON siap untuk laporan bulanan ke BGN.
''')}

<h3>Membuka Dashboard Eksekutif</h3>
{steps([
  ('Sidebar → klik grup <strong>▼ EKSEKUTIF</strong>', ''),
  ('Pilih level: <strong>Per-Kitchen KPI</strong> (Kepala SPPG) atau <strong>Multi-Kitchen</strong> (Superadmin/Platform Admin)', ''),
])}

<h3>Tampilan Dashboard Eksekutif</h3>
{SCREEN_EXEC}

<h3>KPI Per-Kitchen (Kepala SPPG)</h3>
{steps([
  ('Sidebar → ▼ EKSEKUTIF → klik <strong>Dashboard Eksekutif</strong>', 'URL: /executive'),
  ('Lihat 4 kartu utama: Target Porsi, % Konfirmasi, Cost per Porsi, Defect Rate', ''),
  ('Scroll ke bawah untuk grafik tren 30 hari (porsi terkonfirmasi, expense, defects, bahan diterima)', ''),
  ('Klik <strong>Ganti Metrik</strong> untuk memilih metrik tren yang ditampilkan', ''),
])}

{feature_box('🎯', 'Skor Kepatuhan 5-Faktor', f"""
  <p>Skor kepatuhan BGN dihitung dari 5 faktor, masing-masing berkontribusi 20%:</p>
  {data_table(
    ['Faktor', 'Artinya', 'Cara Meningkatkan'],
    [
      ['Inspeksi Selesai', '% inspeksi yang berhasil difinalisasi', 'Pastikan 3 tanda tangan selalu lengkap'],
      ['Menu Approved', '% menu yang sudah di-approve tepat waktu', 'Submit menu H-1 sebelum produksi'],
      ['Distribusi Terkonfirmasi', '% sekolah yang konfirmasi terima', 'Follow-up guru yang belum konfirmasi'],
      ['LRA Submitted', '% periode LRA yang sudah dilaporkan', 'Generate LRA sebelum deadline'],
      ['Checklist Harian', '% checklist harian yang terisi lengkap', 'Isi checklist setiap hari tanpa lupa'],
    ]
  )}
  {data_table(
    ['Skor', 'Grade', 'Artinya'],
    [
      ['90-100', badge('A','green'), 'Excellent — patuh penuh'],
      ['75-89', badge('B','blue'), 'Good — ada minor gap'],
      ['60-74', badge('C','amber'), 'Fair — perlu perhatian'],
      ['< 60', badge('D','red'), 'Poor — intervensi diperlukan'],
    ]
  )}
""")}

{feature_box('🏆', 'Multi-Kitchen Ranking (Superadmin)', f"""
  <p>Superadmin (Yayasan) bisa melihat perbandingan semua SPPG dalam satu organisasi.</p>
  {steps([
    ('Login sebagai <strong>Superadmin</strong>', ''),
    ('Sidebar → ▼ EKSEKUTIF → klik <strong>Multi-Kitchen</strong>', 'URL: /executive → tab Multi-Kitchen'),
    ('Lihat ranking: SPPG dengan skor kepatuhan terbaik, cost terendah, defect rate terendah', ''),
  ])}
""")}

<h3>BGN Compliance Bundle Export</h3>
{steps([
  ('Sidebar → ▼ EKSEKUTIF → klik <strong>BGN Bundle</strong>', ''),
  ('Pilih <strong>Dari Tanggal</strong> dan <strong>Sampai Tanggal</strong> (biasanya 1 bulan)', ''),
  ('Klik <strong>Generate Bundle</strong> — sistem agregasi: LRA, sampel makanan, checklist, variance report', ''),
  ('Review ringkasan yang muncul', ''),
  ('Klik <strong>Download JSON</strong> untuk file yang bisa diserahkan ke BGN', ''),
])}

{info('BGN Compliance Bundle berisi: data LRA periode, food samples dengan timestamps, daily checklists, variance report (defect rate, cost per porsi), dan total porsi bulan berjalan.')}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 13 — Master Data & Admin
# ─────────────────────────────────────────────────────────────────────────────

BAB13 = chapter(13, "⚙️", "Master Data & Manajemen Admin", "Kapan Saja", f"""
{roles('kepala','super','platform')}

{story('''
Fitur-fitur di bab ini tidak terikat waktu harian — tapi sangat penting untuk setup awal
dan pemeliharaan sistem. Kepala SPPG menggunakan ini untuk mengelola data sekolah, supplier,
dan pengguna. Superadmin mengelola dapur (kitchen). Platform Admin mengelola organisasi.
''')}

{feature_box('🏫', 'Manajemen Sekolah', f"""
  {steps([
    ('Sidebar → ▼ MASTER DATA → klik <strong>Sekolah</strong>', 'URL: /admin/schools'),
    ('Lihat daftar 23 sekolah beserta data: nama, jenjang, jumlah siswa, wave pengiriman', ''),
    ('Klik <strong>+ Tambah Sekolah</strong> untuk mendaftarkan sekolah baru', ''),
    ('Isi: nama resmi, kode sekolah, jenjang (PAUD/TK/SD/SMP), jumlah siswa, alamat', ''),
    ('Jenjang menentukan wave pengiriman otomatis: PAUD/TK/SD → Wave 1; SD 7-9/SMP → Wave 2', ''),
    ('Klik <strong>Simpan</strong>', ''),
    ('Untuk edit: klik sekolah yang ada → klik <strong>Edit</strong>', ''),
  ])}
""")}

{feature_box('👤', 'Manajemen Pengguna', f"""
  {steps([
    ('Sidebar → ▼ ADMIN → klik <strong>Pengguna</strong>', 'URL: /admin/users'),
    ('Lihat daftar semua pengguna yang terdaftar di dapur ini', ''),
    ('Klik <strong>+ Tambah Pengguna</strong>', ''),
    ('Isi username, nama lengkap, password awal, dan pilih role', ''),
    ('Role yang bisa dipilih: <code>head_sppg</code>, <code>nutritionist</code>, <code>accountant</code>, <code>aslap</code>, <code>head_kitchen</code>', ''),
    ('Klik <strong>Simpan</strong> — pengguna baru bisa langsung login', ''),
  ])}
  {warn('Setiap pengguna hanya bisa melihat data dari dapur (kitchen) yang sama. Untuk akses multi-dapur, gunakan role Superadmin.')}
""")}

{feature_box('🏢', 'Manajemen Dapur (Superadmin)', f"""
  {steps([
    ('Login sebagai <strong>Superadmin</strong>', ''),
    ('Sidebar → ▼ ADMIN → klik <strong>Dapur</strong>', ''),
    ('Lihat semua SPPG / dapur dalam organisasi Anda', ''),
    ('Klik <strong>+ Tambah Dapur</strong> untuk mendaftarkan SPPG baru', ''),
    ('Isi nama SPPG, lokasi, dan informasi kontak', ''),
    ('Superadmin bisa switch masuk ke dapur manapun untuk monitor', ''),
  ])}
""")}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 14 — Cheat Sheet
# ─────────────────────────────────────────────────────────────────────────────

BAB14 = chapter(14, "⚡", "Cheat Sheet Harian", "Referensi Cepat", f"""
<p>Cetak halaman ini dan tempel di meja kerja sebagai referensi cepat.</p>

{data_table(
  ['Waktu', 'Siapa', 'Tugas', 'Sidebar Path'],
  [
    ['H-1 | 13:00', '💰 Akuntan', 'Cek tren harga + buat PO ke supplier', '▼ PENERIMAAN → Purchase Orders'],
    ['H-1 | 17:00', '🥗 Ahli Gizi', 'Build Menu Manual + cek AKG + siklus 20 hari', '▼ MENU & GIZI → Build Menu Manual'],
    ['H-1 | 18:00', '🥗 Ahli Gizi', 'Submit menu untuk review', '▼ MENU & GIZI → Menu Approval'],
    ['H-1 | 18:00', '👔 Kepala SPPG', 'Approve atau reject menu', '▼ MENU & GIZI → Menu Approval'],
    ['04:00', '🦺 ASLAP', 'Buat inspeksi saat truk supplier tiba', '▼ PENERIMAAN → Inspeksi Bersama'],
    ['04:00', '🥗 Ahli Gizi', 'Tanda tangan kualitas gizi di inspeksi', '▼ PENERIMAAN → Inspeksi Bersama'],
    ['04:00', '💰 Akuntan', 'Tanda tangan kuantitas di inspeksi', '▼ PENERIMAAN → Inspeksi Bersama'],
    ['04:30', '👔 Kepala SPPG', 'Login & cek dashboard + notifikasi', '/ → 🔔 bell'],
    ['05:30', '👨‍🍳 Kepala Chef', 'Mulai batch produksi + scan QR container', '▼ OPERASI DAPUR → Produksi Batch'],
    ['06:00', '🦺 ASLAP', 'Isi checklist harian + kualitas air', '▼ LAPANGAN → Dasbor ASLAP'],
    ['07:00', '🥗 Ahli Gizi', 'Approve QC setelah batch selesai + ambil food sample', '▼ OPERASI DAPUR → Produksi Batch'],
    ['08:00', '🦺 ASLAP', 'Dispatch Gelombang 1 (PAUD/TK/SD kelas 1-3)', '▼ DISTRIBUSI → Distribusi Makanan'],
    ['10:00', '🦺 ASLAP', 'Dispatch Gelombang 2 (SD kelas 4-6/SMP)', '▼ DISTRIBUSI → Distribusi Makanan'],
    ['13:00', '💰 Akuntan', 'Catat pengeluaran hari ini', '▼ KEUANGAN → Expense'],
    ['14:00', '👔 Kepala SPPG', 'Review KPI + skor kepatuhan harian', '▼ EKSEKUTIF → Dashboard Eksekutif'],
    ['Jumat', '🦺 ASLAP', 'Generate + submit laporan mingguan ASLAP', '▼ LAPANGAN → Dasbor ASLAP → Laporan'],
    ['2x/bulan', '💰 Akuntan', 'Generate + submit LRA biweekly', '▼ KEUANGAN → LRA Biweekly'],
    ['Kapan saja', '👩‍🏫 Guru Sekolah', 'Konfirmasi terima makanan (via link WA)', 'Halaman publik, tidak perlu login'],
  ]
)}

<h3>Shortcut Penting</h3>
{data_table(
  ['Situasi', 'Yang Harus Dilakukan', 'Lokasi'],
  [
    ['Bahan ditolak saat inspeksi', 'Klik Tolak Bahan → Buat Dispute → Catat alasan', 'Inspeksi Bersama'],
    ['Kamera QR tidak bisa scan', 'Klik Input Manual → ketik kode BHN-XXXXXXXX', 'Produksi Batch'],
    ['Sekolah tidak konfirmasi', 'Hubungi guru dan kirim ulang link konfirmasi', 'Distribusi → detail sekolah'],
    ['Spike harga bahan >15%', 'Notifikasi otomatis muncul — cari supplier alternatif', 'Keuangan → Tren Harga'],
    ['Air TDS >500 atau pH abnormal', 'Alert otomatis → laporkan ke Kepala SPPG segera', 'ASLAP → Kualitas Air'],
    ['Menu ditolak (reject)', 'Cek catatan alasan dari Kepala SPPG → revisi → submit ulang', 'Menu Approval'],
    ['Lupa password', 'Hubungi Kepala SPPG atau Superadmin untuk reset password', 'Admin → Pengguna'],
  ]
)}

{tip('Untuk pelatihan pengguna baru, mulai dari Bab 2 (Login) dan Bab 13 (Admin). Kemudian biarkan masing-masing role membaca bab yang relevan dengan tugasnya.')}
{info('Pertanyaan atau masalah teknis? Hubungi Platform Admin atau kirim email ke support@dpmbg.id')}
""")


# ─────────────────────────────────────────────────────────────────────────────
# APPENDIX
# ─────────────────────────────────────────────────────────────────────────────

APPENDIX = f"""<div class="chapter" id="appendix">
  <div class="chapter-header">
    <span class="ch-num">APPENDIX</span>
    <h2>📌 Referensi Tambahan</h2>
    <span class="ch-time">⏰ Kapan Saja</span>
  </div>

  <h3>Daftar Lengkap Role & Hak Akses</h3>
  {data_table(
    ['Fitur / Halaman', '👔 Kepala', '🥗 Gizi', '💰 Akun', '🦺 ASLAP', '👨‍🍳 Chef'],
    [
      ['Dashboard', '✅', '✅', '✅', '✅', '✅'],
      ['Build Menu Manual', '✅', '✅', '', '', ''],
      ['Menu Approval', '✅ (approve)', '✅ (submit)', '', '', ''],
      ['Student Requests', '✅', '✅', '', '✅', ''],
      ['Purchase Orders', '✅', '', '✅', '', ''],
      ['Tren Harga', '✅', '✅', '✅', '', ''],
      ['Inspeksi (buat)', '✅', '', '✅ (qty)', '✅', ''],
      ['Inspeksi (tanda tangan)', '✅', '✅ (gizi)', '✅ (qty)', '✅ (fisik)', ''],
      ['Container Split', '✅', '', '', '✅', ''],
      ['Produksi Batch', '✅', '', '', '', '✅'],
      ['QR Scan', '✅', '', '', '', '✅'],
      ['QC Approve', '✅', '✅', '', '', ''],
      ['Distribusi Dispatch', '✅', '', '', '✅', ''],
      ['ASLAP Checklist', '✅ (view)', '', '', '✅ (isi)', ''],
      ['Kualitas Air', '✅ (view)', '', '', '✅ (isi)', ''],
      ['Laporan ASLAP', '✅ (ttd)', '', '', '✅ (buat)', ''],
      ['Expense Tracker', '✅', '', '✅', '', ''],
      ['LRA Biweekly', '✅ (ttd)', '', '✅ (buat)', '', ''],
      ['Executive Dashboard', '✅', '', '', '', ''],
      ['BGN Compliance Bundle', '✅', '', '✅', '', ''],
      ['Manajemen Sekolah', '✅', '', '', '', ''],
      ['Manajemen Supplier', '✅', '', '✅', '', ''],
      ['Manajemen Pengguna', '✅', '', '', '', ''],
    ]
  )}

  <h3>Standar Ambang Batas</h3>
  {data_table(
    ['Parameter', 'Nilai Normal', 'Alert Jika', 'Tindakan'],
    [
      ['Cost per Porsi', '≤ Rp 15.000', '> Rp 15.000', 'Review menu dan expense'],
      ['Defect Rate', '< 2%', '≥ 2%', 'Evaluasi supplier dan proses'],
      ['Kenaikan Harga Bahan', '< 15% WoW', '≥ 15%', 'Cari supplier alternatif'],
      ['TDS Air', '< 500 ppm', '≥ 500 ppm', 'Hentikan penggunaan, lapor'],
      ['pH Air', '6.5 – 8.5', 'Di luar range', 'Hentikan penggunaan, lapor'],
      ['Retensi Sampel Makanan', '48 jam', 'Buang setelah 48 jam', 'Sistem beri notifikasi'],
    ]
  )}

  <h3>Glosarium</h3>
  {data_table(
    ['Istilah', 'Arti'],
    [
      ['SPPG', 'Satuan Pelayanan Pemenuhan Gizi — unit dapur MBG'],
      ['BGN', 'Badan Gizi Nasional — regulator program MBG'],
      ['MBG', 'Makan Bergizi Gratis — program pangan bergizi pemerintah'],
      ['AKG', 'Angka Kecukupan Gizi — standar gizi harian per kelompok umur'],
      ['TKPI', 'Tabel Komposisi Pangan Indonesia — basis data nilai gizi bahan makanan'],
      ['LRA', 'Laporan Realisasi Anggaran — laporan keuangan biweekly'],
      ['FIFO', 'First In First Out — stok paling lama masuk, paling pertama digunakan'],
      ['Wave', 'Gelombang pengiriman — Wave 1 = pagi (PAUD/TK/SD), Wave 2 = siang (SD 7-9/SMP)'],
      ['PO', 'Purchase Order — surat pemesanan bahan ke supplier'],
      ['WoW', 'Week-over-Week — perbandingan nilai minggu ini vs minggu lalu'],
      ['KPI', 'Key Performance Indicator — indikator kinerja utama'],
    ]
  )}
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────

def build_html():
    chapters_html = "\n".join([
        BAB1, BAB2, BAB3, BAB4, BAB5, BAB6, BAB7,
        BAB8, BAB9, BAB10, BAB11, BAB12, BAB13, BAB14,
        APPENDIX,
    ])
    date_str = datetime.now().strftime("%d %B %Y")
    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Panduan Pengguna DPMBG 2026</title>
<style>{CSS}</style>
</head>
<body>
<div class="page">
{COVER}
{TOC_HTML}
{chapters_html}
<div style="text-align:center;padding:40px;color:var(--gray-400);font-size:0.8rem;border-top:1px solid var(--gray-100);margin-top:40px">
  <p>DPMBG User Guide v1.0 &mdash; Digenerate {date_str}</p>
  <p>SPPG Paseh, Kabupaten Bandung &mdash; Program Makan Bergizi Gratis</p>
</div>
</div>
</body>
</html>"""


if __name__ == "__main__":
    html = build_html()
    OUT_HTML.parent.mkdir(exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    size_kb = OUT_HTML.stat().st_size // 1024
    print(f"[OK] Generated: {OUT_HTML}  ({size_kb} KB)")
    print(f"     Open in Chrome -> Ctrl+P -> Save as PDF")

    if "--pdf" in sys.argv:
        try:
            import weasyprint  # type: ignore
            print("Converting to PDF via WeasyPrint...")
            weasyprint.HTML(filename=str(OUT_HTML)).write_pdf(str(OUT_PDF))
            pdf_kb = OUT_PDF.stat().st_size // 1024
            print(f"[OK] PDF: {OUT_PDF}  ({pdf_kb} KB)")
        except ImportError:
            print("[WARN] WeasyPrint not installed. For PDF conversion:")
            print("       pip install weasyprint")
            print("       then re-run with --pdf flag")


