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
  <text x="32" y="236" fill="rgba(255,255,255,0.75)" font-size="9">🤝 Joint Inspection</text>
  <text x="20" y="260" fill="rgba(255,255,255,0.4)" font-size="8" font-weight="700" letter-spacing="0.08em">▼ OPERASI DAPUR</text>
  <text x="32" y="280" fill="rgba(255,255,255,0.75)" font-size="9">🍳 Produksi Batch</text>
  <text x="20" y="304" fill="rgba(255,255,255,0.4)" font-size="8" font-weight="700" letter-spacing="0.08em">▼ DISTRIBUSI</text>
  <text x="32" y="324" fill="rgba(255,255,255,0.75)" font-size="9">🚐 Distribusi</text>
  <text x="20" y="348" fill="rgba(255,255,255,0.4)" font-size="8" font-weight="700" letter-spacing="0.08em">▼ LAPANGAN (ASLAP)</text>
  <text x="32" y="368" fill="rgba(255,255,255,0.75)" font-size="9">📝 ASLAP Daily</text>
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
    <div class="cover-meta-item"><div class="val">14</div><div class="lbl">Bab Panduan</div></div>
    <div class="cover-meta-item"><div class="val">7</div><div class="lbl">Role Pengguna</div></div>
    <div class="cover-meta-item"><div class="val">11</div><div class="lbl">Sekolah Binaan</div></div>
    <div class="cover-meta-item"><div class="val">SPPG</div><div class="lbl">Paseh</div></div>
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
    (4,  "Build Menu Manual",                     "05:30"),
    (5,  "Approval Menu & Siklus 20 Hari",        "06:00"),
    (6,  "Purchase Orders & Master Supplier",     "06:15"),
    (7,  "Joint Inspection — 3 Tanda Tangan",     "06:30"),
    (8,  "Production — Tablet Kepala Chef",       "07:30"),
    (9,  "Distribusi ke Sekolah (Wave 1 & 2)",    "08:30"),
    (10, "ASLAP — Operasi Harian",                "10:00"),
    (11, "Akuntan Finance — Expense, LRA & Price Trends", "13:00"),
    (12, "Executive Dashboard & BGN Bundle",      "14:00"),
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
"Di balik ribuan piring makan yang tiba tepat waktu di 11 sekolah binaan SPPG Paseh setiap hari,
ada satu sistem yang bekerja diam-diam sejak subuh: DPMBG. Jam 04:00 truk supplier
sudah di halaman dapur untuk Joint Inspection. Jam 05:30 Kepala Chef sudah memasak.
Jam 08:00 Wave 1 jalan ke PAUD/TK/SD. Jam 10:00 Wave 2 jalan ke SMP.
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

SCREEN_LOGIN = screen("/login", "")

SCREEN_DASHBOARD = screen("/", "")

BAB2 = chapter(2, "🔑", "Login & Dashboard", "04:30", f"""
{roles('kepala','nutritionist','accountant','aslap','chef')}

{story('''
<strong>04:30 pagi.</strong> Kepala SPPG tiba di dapur — truk supplier sudah di halaman
sejak jam 04:00 dan ASLAP sedang menangani Joint Inspection. Kepala SPPG langsung buka laptop
dan login ke DPMBG. Begitu masuk Dashboard, dia langsung tahu kondisi 4 KPI utama hari ini —
Items Received, Items Processed, Trays Packed, Trays Delivered — beserta Pipeline Funnel
yang menunjukkan konversi tiap tahap. Tinggal lihat sekejap.
''')}

<h3>Login ke DPMBG</h3>
{SCREEN_LOGIN}

{steps([
  ('Buka browser, akses <code>https://dapurpintarmbg.com</code> (atau <code>http://localhost:5173</code> untuk lokal dev)', ''),
  ('Di kartu login bertanda <strong>DAPUR PINTAR · MBG</strong>, isi <strong>Username</strong> dan <strong>Password</strong> yang diberikan admin', ''),
  ('Klik tombol biru <strong>Login</strong>', ''),
  ('Anda akan diarahkan ke halaman Dashboard sesuai role Anda', ''),
])}

{tip('Setiap role melihat menu sidebar yang berbeda. Kepala SPPG melihat semua; ASLAP hanya melihat menu Lapangan & Distribusi; Kepala Chef hanya melihat Produksi.')}
{warn('Jangan bagikan password dengan siapapun. Setiap aksi di sistem terekam dengan nama pengguna yang login.')}

<h3>Halaman Dashboard</h3>
<!-- SHOT:dashboard -->

<p>Dashboard menampilkan 4 kartu metrik utama di atas, <strong>Pipeline Funnel</strong> (Received → Processed → Packed → Delivered), dan beberapa widget operasional. Saat dapur belum mulai operasi, semua angka kosong/0% — angka terisi otomatis begitu QR scan mulai dilakukan di gudang dan dapur.</p>
{data_table(
  ['Kartu / Widget', 'Artinya', 'Siapa yang Peduli'],
  [
    ['Items Received', 'Jumlah container bahan yang sudah di-scan masuk gudang', 'Kepala SPPG, ASLAP'],
    ['Items Processed', 'Container yang sudah di-scan masuk dapur (siap diolah)', 'Kepala SPPG, Chef'],
    ['Trays Packed', 'Tray porsi yang sudah dikemas siap kirim', 'Chef, ASLAP'],
    ['Trays Delivered', 'Tray yang sudah dikirim ke sekolah', 'ASLAP, Kepala SPPG'],
    ['Pipeline Funnel', 'Konversi Received → Processed → Packed → Delivered (%)', 'Kepala SPPG'],
    ['Item Processing Rate', 'Persentase container yang sudah diproses dari yang diterima', 'Chef, Kepala SPPG'],
    ['Tray Fill Rate', 'Persentase tray terisi sesuai kebutuhan siswa', 'Chef, Ahli Gizi'],
    ['Avg Durations', 'Rata-rata waktu Receiving→Processing & Packing→Delivery (lebih pendek lebih baik)', 'Kepala SPPG'],
    ['Hourly Scan Activity', 'Aktivitas scan QR per jam — tools tracking ritme operasional', 'Kepala SPPG'],
  ]
)}

<p>Di kanan atas ada <strong>date picker</strong> (default hari ini) + tombol <strong>Export Daily</strong> dan <strong>Export Range</strong> untuk download CSV.</p>

<h3>Navigasi Sidebar</h3>
<p>Sidebar kiri berisi semua fitur, dikelompokkan dalam beberapa grup yang bisa dilipat/dibuka (<strong>klik nama grup</strong> untuk toggle). Item yang tidak sesuai permission Anda otomatis disembunyikan.</p>
<ul>
  <li><strong>(pinned)</strong> ⊞ <strong>Dashboard</strong>, 📈 <strong>Executive</strong> — selalu di paling atas</li>
  <li><strong>▼ MENU & GIZI</strong> — Menu Planner, Build Manual, Approval Menu, Nutrisi Harian</li>
  <li><strong>▼ PENERIMAAN BAHAN</strong> — Purchase Orders, Joint Inspection, Receiving (Quick)</li>
  <li><strong>▼ PRODUKSI & DISTRIBUSI</strong> — Production, Distribusi</li>
  <li><strong>▼ LAPANGAN & MONITORING</strong> — ASLAP Daily, Scan Errors, Variance Report</li>
  <li><strong>▼ KEUANGAN</strong> — Akuntan Finance</li>
  <li><strong>▼ MASTER DATA</strong> — Sekolah, Supplier</li>
  <li><strong>▼ ADMIN DAPUR</strong> — All Kitchens (superadmin), Kitchens, Users</li>
  <li><strong>▼ PLATFORM</strong> — Organizations (hanya Platform Admin)</li>
</ul>
{tip('Header sidebar menampilkan brand "DAPUR PINTAR · SPPG Paseh", dropdown switcher Kitchen (kalau punya akses multi-dapur), dan ikon bell 🔔 notifikasi.')}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 3 — Notifikasi
# ─────────────────────────────────────────────────────────────────────────────

BAB3 = chapter(3, "🔔", "Notifikasi & Bell", "04:30", f"""
{roles('kepala','nutritionist','accountant','aslap','chef')}

{story('''
<strong>04:30 pagi.</strong> Setelah login, Kepala SPPG melihat ikon bell 🔔 di area brand sidebar (kiri atas, di samping label "Dapur Pintar · SPPG Paseh"). Kalau ada notifikasi baru, ikon bell menyala kuning sebagai indikator. Dia klik bell — daftar notifikasi terbuka: menu yang sudah disubmit Ahli Gizi kemarin menunggu approval-nya, alert inspeksi baru yang baru saja dibuat ASLAP, dan pengingat food sample yang hampir lewat 48 jam. Semua ditangani dari satu panel.
''')}

<h3>Ikon Bell di Sidebar</h3>
<!-- SHOT:notifications -->

<p>Ikon bell 🔔 ada di area brand sidebar (paling atas, di sebelah label dapur). Di screenshot di atas, ikon bell tampak kuning — itu indikator bahwa ada notifikasi yang belum dibaca.</p>

{steps([
  ('Lihat ikon 🔔 di area brand sidebar kiri atas — warna kuning + badge angka = ada notifikasi belum dibaca', ''),
  ('Klik ikon bell untuk membuka daftar notifikasi', ''),
  ('Klik salah satu notifikasi untuk langsung navigasi ke halaman yang relevan', ''),
  ('Klik <strong>"Tandai semua terbaca"</strong> untuk membersihkan semua badge sekaligus', ''),
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

SCREEN_BUILD_MENU = screen("/menu-manual", "")

BAB4 = chapter(4, "✎", "Build Menu Manual", "H-1 | Sore", f"""
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
  ('Klik item <strong>Build Manual</strong> (icon ✎)', 'URL: /menu-manual'),
])}

<h3>Tampilan Build Menu Manual</h3>
{SCREEN_BUILD_MENU}

<p>Halaman menampilkan judul <strong>Build Menu Manual</strong> dengan subtitle
<em>"Input menu manual (mis. dari permintaan siswa), lihat gizi & biaya real-time vs AKG."</em>.
Layout 2 kolom: kiri = pencari bahan + daftar bahan dipilih; kanan = panel <strong>Analisis Gizi & Biaya</strong>.</p>

<h3>Langkah Menyusun Menu</h3>
{steps([
  ('Di kolom kiri, gunakan input <strong>"Cari bahan TKPI (nama atau kode)..."</strong> untuk mencari bahan', ''),
  ('Pilih kategori bahan dari dropdown di sebelah kanan input pencarian (opsional filter)', ''),
  ('Klik hasil yang muncul untuk menambahkan bahan ke daftar <strong>Bahan dipilih</strong>', 'Counter angka di label akan bertambah, mis. "Bahan dipilih (3)"'),
  ('Untuk tiap bahan yang sudah masuk, isi gramase per porsi', ''),
  ('Panel kanan <strong>Analisis Gizi & Biaya</strong> akan otomatis update real-time menampilkan total energi, protein, lemak, KH, biaya per porsi, dan % AKG vs target kelompok umur', ''),
  ('Pantau % AKG — harus mencapai minimal 70% untuk setiap kelompok umur yang dilayani', ''),
  ('Cost per porsi harus di bawah Rp 15.000', ''),
])}

{tip('Saat halaman pertama dibuka dengan menu kosong, daftar bahan menampilkan placeholder <em>"Belum ada bahan. Cari di atas."</em> dan panel analisis menampilkan <em>"Pilih bahan dulu."</em>')}

{info('Untuk fitur Reverse Optimizer otomatis (kombinasi bahan dengan cost minimal & gizi maksimal), Sikus 20 hari, dan Forecast Kebutuhan Bahan — gunakan halaman <strong>Menu Planner</strong> atau <strong>Approval Menu</strong> (lihat Bab 5). Halaman Build Manual fokus pada input cepat 1 menu untuk skenario ad-hoc (permintaan siswa, diet khusus).')}
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

<h3>Halaman Approval Menu</h3>
<!-- SHOT:menu_approval -->

<p>Judul halaman <strong>Approval Menu</strong> dengan subtitle
<em>"Alur: Draft → Nunggu Review → Disetujui → Terkunci. Cycle 20 hari & forecast bahan ada di bawah."</em>.
Di atas ada 7 tab filter status, dan di bawah ada panel <strong>Forecast Bahan dari Menu Approved</strong>.</p>

<h3>Tab Status (urut kiri ke kanan)</h3>
{data_table(
  ['Tab', 'Status', 'Artinya', 'Siapa yang Bisa Ubah'],
  [
    [badge('Nunggu Review','amber'), 'Pending review (default tab aktif)', 'Menunggu approval Kepala SPPG', 'Ahli Gizi (submit) → Kepala SPPG (review)'],
    [badge('Draft','gray'), 'Draft', 'Menu sedang disusun, belum disubmit', 'Ahli Gizi'],
    [badge('Disetujui','green'), 'Approved', 'Sudah di-approve, siap dieksekusi', 'Kepala SPPG'],
    [badge('Terkunci','blue'), 'Locked', 'Dikunci, tidak bisa diubah lagi', 'Kepala SPPG'],
    [badge('Ditolak','red'), 'Rejected', 'Di-reject, harus revisi', 'Kepala SPPG (action) → Ahli Gizi (perbaiki)'],
    [badge('Arsip','gray'), 'Archived', 'Arsip historis', 'Kepala SPPG'],
    [badge('Semua','gray'), 'Semua', 'Lihat semua status sekaligus', '—'],
  ]
)}

<h3>Submit Menu untuk Review (Ahli Gizi)</h3>
{steps([
  ('Selesaikan komposisi menu di Build Manual atau Menu Planner', 'Sidebar → ▼ MENU & GIZI → Build Manual / Menu Planner'),
  ('Pastikan komposisi gizi memenuhi AKG dan cost di bawah Rp 15.000/porsi', ''),
  ('Klik tombol <strong>Submit untuk Review</strong>', ''),
  ('Tulis catatan opsional untuk Kepala SPPG', ''),
  ('Klik <strong>Konfirmasi Submit</strong> — status menu pindah ke tab <strong>Nunggu Review</strong>', ''),
])}

<h3>Menyetujui Menu (Kepala SPPG)</h3>
{steps([
  ('Buka notifikasi bell atau langsung ke halaman approval', 'Sidebar → ▼ MENU & GIZI → Approval Menu'),
  ('Pastikan tab <strong>Nunggu Review</strong> aktif (default sudah aktif)', ''),
  ('Klik menu yang ingin di-review — detail komposisi gizi muncul', ''),
  ('Review AKG per kelompok umur, cek siklus 20 hari, lihat cost per porsi', ''),
  ('Klik <strong>Disetujui</strong> (approve) atau <strong>Ditolak</strong> dengan catatan alasan', ''),
  ('Jika approve → menu pindah ke tab <strong>Disetujui</strong> + notifikasi ke Ahli Gizi', ''),
])}

{tip('Kepala SPPG bisa langsung klik link dari notifikasi bell untuk langsung ke halaman approval menu yang bersangkutan.')}

<h3>Forecast Bahan dari Menu Approved</h3>
<p>Panel di bawah daftar menu memungkinkan menghitung total kebutuhan bahan untuk semua menu yang sudah <strong>Disetujui</strong> dalam rentang tanggal tertentu — output siap dikonversi jadi Purchase Order (lihat Bab 6).</p>
{steps([
  ('Scroll ke bawah daftar menu, temukan panel <strong>Forecast Bahan dari Menu Approved</strong>', ''),
  ('Isi tanggal <strong>Dari</strong> dan <strong>Sampai</strong> (default 7 hari ke depan)', ''),
  ('Klik tombol biru <strong>Hitung</strong>', ''),
  ('Sistem agregasi: total gram per bahan × jumlah siswa × hari', ''),
])}

{info('Forecast ini langsung dipakai modul Akuntan untuk meng-generate PO (lihat tab PO Generator di halaman Akuntan Finance).')}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 6 — Purchase Orders & Supplier
# ─────────────────────────────────────────────────────────────────────────────

SCREEN_PO = screen("/purchase-orders", "")

BAB6 = chapter(6, "📦", "Purchase Order & Manajemen Supplier", "H-1 | Siang", f"""
{roles('accountant','kepala')}

{story('''
<strong>H-1, pukul 13:00.</strong> Akuntan membuka halaman Purchase Orders. Supplier harus tahu pesanan
paling lambat sore ini supaya bisa siapkan barang untuk pengiriman subuh besok jam 04:00.
Berdasarkan forecast dari menu yang sudah diapprove, dia perlu memesan ayam kampung 50 kg
dan bayam 30 kg dari UD Sumber Tani. Klik tombol biru <em>+ PO Baru</em>, pilih supplier, tambah item —
dalam 5 menit PO tersimpan dan supplier bisa dihubungi untuk konfirmasi.
''')}

<h3>Halaman Purchase Orders</h3>
{SCREEN_PO}

<p>Judul halaman <strong>Purchase Orders</strong> dengan subtitle
<em>"Akuntan generate PO dari forecast menu approved."</em>. Tombol biru <strong>+ PO Baru</strong> di kanan atas.
Di bawah ada 7 tab filter: <code>Semua</code> (default aktif) · <code>draft</code> · <code>sent</code> · <code>partial</code> · <code>received</code> · <code>closed</code> · <code>cancelled</code>.</p>

<h3>Membuat Purchase Order Baru</h3>
{steps([
  ('Sidebar → klik grup <strong>▼ PENERIMAAN BAHAN</strong>', ''),
  ('Klik item <strong>Purchase Orders</strong> (icon 📋)', 'URL: /purchase-orders'),
  ('Klik tombol biru <strong>+ PO Baru</strong> di kanan atas', ''),
  ('Pilih <strong>Supplier</strong> dari dropdown (berdasarkan Master Supplier)', ''),
  ('Isi tanggal order dan tanggal kedatangan yang diharapkan', ''),
  ('Tambahkan item: pilih bahan, isi kuantitas dan satuan', ''),
  ('Ulangi untuk semua bahan yang dipesan', ''),
  ('Submit — nomor PO otomatis digenerate, status awal = <code>draft</code>', ''),
  ('Klik action <strong>Send</strong> untuk pindahkan status ke <code>sent</code> (PO terkirim ke supplier)', ''),
])}

<h3>Lifecycle Status PO</h3>
{data_table(
  ['Status', 'Artinya', 'Action Selanjutnya'],
  [
    ['draft', 'PO baru dibuat, belum dikirim', 'Akuntan: kirim ke supplier'],
    ['sent', 'PO sudah dikirim ke supplier, menunggu kedatangan', 'ASLAP: tunggu truk datang → buka Joint Inspection'],
    ['partial', 'Bahan datang sebagian (split delivery)', 'Lanjut tunggu sisa atau close manual'],
    ['received', 'Semua bahan sudah masuk + lulus inspeksi', 'Auto-update dari Joint Inspection'],
    ['closed', 'PO selesai (final)', '—'],
    ['cancelled', 'PO dibatalkan sebelum supplier kirim', '—'],
  ]
)}

{feature_box('⚡', 'Auto-Generate PO dari Forecast Menu', f"""
  <p>Tidak perlu input manual jika sudah punya forecast! Modul Akuntan punya generator PO otomatis.</p>
  {steps([
    ('Sidebar → ▼ KEUANGAN → <strong>Akuntan Finance</strong>', ''),
    ('Klik tab <strong>PO Generator</strong>', ''),
    ('Pilih periode forecast (yang sudah dihitung di Approval Menu) dan supplier untuk masing-masing bahan', ''),
    ('Review quantities yang disarankan sistem', ''),
    ('Klik <strong>Generate</strong> — PO otomatis dibuat dengan status <code>draft</code>', ''),
  ])}
""")}

<h3>Price Trends & Spike Alerts</h3>
{steps([
  ('Sidebar → ▼ KEUANGAN → klik <strong>Akuntan Finance</strong>', 'URL: /finance'),
  ('Klik tab <strong>Price Trends</strong>', ''),
  ('Pilih bahan dari dropdown untuk melihat grafik harga 30/60/90 hari terakhir', ''),
  ('Klik tab <strong>Spike Alerts</strong> untuk lihat daftar bahan yang naik ≥15% minggu ini', ''),
])}

{warn('Jika ada spike alert merah pada bahan utama, laporkan ke Kepala SPPG sebelum membuat PO baru — mungkin perlu cari supplier alternatif.')}

<h3>Manajemen Supplier</h3>
{steps([
  ('Sidebar → ▼ MASTER DATA → klik <strong>Supplier</strong>', 'URL: /admin/suppliers'),
  ('Halaman <strong>Master Supplier</strong> menampilkan daftar semua supplier aktif', ''),
  ('Klik tombol biru <strong>+ Tambah Supplier</strong> di kanan atas untuk mendaftarkan supplier baru', ''),
  ('Centang checkbox <strong>Tampilkan non-aktif</strong> di samping tombol kalau mau lihat supplier yang sudah dinonaktifkan', ''),
  ('Isi nama, kontak, kategori bahan, rating awal, NPWP, rekening', ''),
])}

{data_table(
  ['Kolom Supplier', 'Artinya'],
  [
    ['Nama', 'Nama resmi usaha supplier'],
    ['Kontak', 'No. HP atau email PIC supplier'],
    ['Kategori', 'Jenis bahan yang biasa disuplai (bahan_pokok, sayuran, ayam, ikan)'],
    ['Rating', 'Score 1-5 berbasis histori penerimaan'],
    ['NPWP / Rekening', 'Untuk pencairan invoice'],
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

BAB7 = chapter(7, "🤝", "Joint Inspection — 3 Tanda Tangan Digital", "04:00", f"""
{roles('aslap','nutritionist','accountant','kepala')}

{story('''
<strong>04:00 subuh.</strong> Truk supplier UD Sumber Tani tiba di halaman dapur. ASLAP yang sudah standby
langsung buka DPMBG di tabletnya dan buat inspeksi baru yang otomatis memuat line item dari PO kemarin.
Dia catat bobot aktual per container. Ahli Gizi tanda tangan digital untuk kualitas gizi.
Akuntan tanda tangan untuk kuantitas sesuai PO. ASLAP tanda tangan terakhir untuk kondisi fisik.
Tiga tanda tangan, semua digital, semua timestamped. Dalam 45 menit bahan sudah masuk gudang —
Kepala Chef bisa mulai masak jam 05:30.
''')}

<h3>Halaman Joint Inspection</h3>
<!-- SHOT:inspections -->

<p>Judul halaman <strong>Joint Inspection</strong> dengan subtitle
<em>"3-orang sign-off saat bahan datang dari supplier (BGN compliance)."</em>.
Tombol biru <strong>+ Mulai Inspeksi</strong> di kanan atas. Di bawah ada 6 tab filter:
<code>inspecting</code> (default aktif) · <code>pending</code> · <code>accepted</code> · <code>partial</code> · <code>rejected</code> · <code>Semua</code>.</p>

<h3>Langkah 1: Mulai Inspeksi (ASLAP)</h3>
{steps([
  ('Sidebar → klik grup <strong>▼ PENERIMAAN BAHAN</strong> → klik <strong>Joint Inspection</strong>', 'URL: /inspections'),
  ('Klik tombol biru <strong>+ Mulai Inspeksi</strong> di kanan atas', ''),
  ('Pilih <strong>Purchase Order</strong> terkait dari dropdown (PO dengan status <code>sent</code>)', ''),
  ('Isi tanggal dan waktu kedatangan supplier', ''),
  ('Submit — inspeksi baru muncul di tab <code>inspecting</code> (sedang berjalan)', ''),
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

BAB8 = chapter(8, "🍳", "Production — Tablet Kepala Chef", "05:30", f"""
{roles('chef','kepala','nutritionist')}

{story('''
<strong>05:30 pagi.</strong> Inspeksi selesai, semua bahan sudah masuk gudang dan di-scan ke inventori.
Kepala Chef buka DPMBG di tablet yang dipasang di tembok dapur, pilih menu yang sudah Approved
kemarin malam, dan klik <em>Mulai Batch Baru</em>. Timer 6 jam mulai berjalan — BGN mewajibkan
makanan dikonsumsi maksimal 6 jam dari selesai masak. Setiap container bahan yang diambil dari
gudang di-scan barcodenya. Sistem otomatis catat pemakaian dan kurangi stok dengan metode FIFO —
container paling lama masuk, paling pertama terpakai.
''')}

<h3>Halaman Production</h3>
<!-- SHOT:production -->

<p>Judul halaman <strong>Production — Tablet Kepala Chef</strong> dengan subtitle
<em>"Mulai batch dari menu approved. FIFO auto-debit. Timer 6 jam SOP BGN."</em>.
Halaman dirancang untuk tablet di dinding dapur (touch-friendly). Tiga panel utama:</p>
<ul>
  <li><strong>Menu Approved Hari Ini</strong> — daftar menu yang sudah di-approve, klik untuk mulai batch</li>
  <li><strong>Batch Aktif</strong> — batch yang sedang berjalan dengan countdown timer 6 jam (kosong: <em>"Belum ada batch."</em>)</li>
  <li><strong>Tablet Scan — Step Processing (JWT auth)</strong> — tombol biru <strong>📷 Scan</strong> untuk buka kamera</li>
</ul>

<h3>Memulai Batch Produksi</h3>
{steps([
  ('Sidebar → klik grup <strong>▼ PRODUKSI & DISTRIBUSI</strong> → klik <strong>Production</strong>', 'URL: /production'),
  ('Di panel <strong>Menu Approved Hari Ini</strong>, klik menu yang akan dimasak', ''),
  ('Isi <strong>Target Porsi</strong> untuk batch ini', ''),
  ('Submit — batch muncul di panel <strong>Batch Aktif</strong> dengan timer 6 jam mulai berjalan', ''),
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
# BAB 9 — Distribusi ke Sekolah (Wave 1 & 2)
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

BAB9 = chapter(9, "🚐", "Distribusi ke Sekolah (Wave 1 & 2)", "08:00 / 10:00", f"""
{roles('aslap','kepala')}

{story('''
<strong>08:00 pagi.</strong> Produksi selesai jam 07:30 dan makanan sudah dikemas. ASLAP di parkiran
dengan dua truk siap jalan untuk Wave 1: PAUD, TK, dan SD — sekolah yang makan lebih pagi.
Dia buka DPMBG, klik tab Wave 1 & 2, input jumlah per sekolah, klik <em>Dispatch</em>, dan truk jalan.
Jam 10:00 Wave 2 jalan untuk SMP. Sejam setelah dispatch, notifikasi konfirmasi mulai masuk
satu per satu dari guru di setiap sekolah — semua tercatat otomatis.
''')}

<h3>Halaman Distribusi</h3>
<!-- SHOT:distributions -->

<p>Judul halaman <strong>Distribusi Hari Ini</strong> dengan subtitle
<em>"Aggregate per sekolah · 2-wave classifier · receipt tracking · sisa porsi."</em>.
Empat tab di atas: <code>Aggregate Hari Ini</code> (default aktif) · <code>Wave 1 & 2</code> · <code>Sisa Porsi</code> · <code>Vehicle & Driver</code>.</p>

<h3>Mendispatch Pengiriman</h3>
{steps([
  ('Sidebar → klik grup <strong>▼ PRODUKSI & DISTRIBUSI</strong> → klik <strong>Distribusi</strong>', 'URL: /distributions'),
  ('Klik tab <strong>Wave 1 & 2</strong> untuk lihat daftar pengiriman per gelombang', ''),
  ('Wave classifier otomatis pilihkan sekolah: PAUD/TK/SD = Wave 1, SMP = Wave 2', ''),
  ('Untuk tiap sekolah: isi jumlah porsi dikirim, pilih driver + vehicle dari tab Vehicle & Driver', ''),
  ('Klik <strong>Dispatch</strong> per item atau dispatch seluruh gelombang sekaligus', ''),
])}

<h3>Konfirmasi Terima oleh Guru Sekolah (Tanpa Login)</h3>
{steps([
  ('Guru menerima link konfirmasi (dikirim via WhatsApp atau scan QR yang dicetak di label kontainer)', ''),
  ('Guru buka link di HP — <strong>tidak perlu login</strong>', 'URL publik: /confirm/<token>'),
  ('Halaman menampilkan: nama sekolah, tanggal, jumlah porsi yang dikirim', ''),
  ('Guru isi <strong>Jumlah Diterima Aktual</strong> dan klik <strong>Konfirmasi Terima</strong>', ''),
  ('Jika ada sisa: isi <strong>Sisa Makanan</strong> yang tidak terdistribusi ke siswa', ''),
  ('Submit — tercatat dengan timestamp', ''),
])}

{tip('Guru tidak perlu punya akun DPMBG. Link konfirmasi adalah halaman publik yang hanya bisa diakses sekali per pengiriman.')}

<h3>Tab Aggregate Hari Ini</h3>
{steps([
  ('Klik tab <strong>Aggregate Hari Ini</strong> (default tab aktif)', ''),
  ('Lihat ringkasan per-sekolah: target porsi · dikirim · dikonfirmasi · sisa', ''),
  ('Status sekolah otomatis berubah: <span style="color:#D97706">Menunggu</span> (kuning) → <span style="color:#059669">Terkonfirmasi</span> (hijau) saat guru klik konfirmasi', ''),
])}

<h3>Tab Sisa Porsi</h3>
{steps([
  ('Saat kembali dari pengiriman, ASLAP input sisa makanan yang dibawa kembali', ''),
  ('Klik tab <strong>Sisa Porsi</strong>', ''),
  ('Isi jumlah sisa per sekolah, alasan (over-estimate / siswa absen / dll)', ''),
  ('Submit — data leftover tersimpan untuk analisis efisiensi & laporan BGN', ''),
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

BAB10 = chapter(10, "📝", "ASLAP — Operasi Harian", "06:00", f"""
{roles('aslap','kepala')}

{story('''
<strong>06:00 pagi.</strong> Inspeksi bahan selesai, Kepala Chef sudah mulai masak. ASLAP sekarang
punya 20 menit untuk checklist harian sebelum sibuk persiapan pengiriman. Dia buka tab
<em>ASLAP Daily</em> di DPMBG — checklist kebersihan, suhu kompor, cuci tangan, kondisi
sampah, dan test kualitas air. Semua diisi dengan foto sebagai bukti.
Siang harinya dia isi observasi produksi dan logbook komunikasi sekolah.
Laporan mingguan akan di-generate hari Jumat.
''')}

<h3>Membuka ASLAP Daily</h3>
<!-- SHOT:aslap -->

<p>Judul halaman <strong>ASLAP — Operasi Harian</strong> dengan subtitle
<em>"Daily checklist · water quality · production observation · komunikasi sekolah · weekly report"</em>.
5 tab di atas: <code>Checklist Hari Ini</code> (default aktif) · <code>Water Quality</code> · <code>Production Obs</code> · <code>Komunikasi Sekolah</code> · <code>Weekly Report</code>.</p>

{steps([
  ('Sidebar → klik grup <strong>▼ LAPANGAN & MONITORING</strong> → klik <strong>ASLAP Daily</strong> (icon 📝)', 'URL: /aslap'),
])}

{feature_box('✅', 'Checklist Hari Ini', f"""
  {steps([
    ('Klik tab <strong>Checklist Hari Ini</strong> (default tab aktif)', ''),
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

{feature_box('💧', 'Water Quality', f"""
  {steps([
    ('Klik tab <strong>Water Quality</strong>', ''),
    ('Klik <strong>+ Catat Pengukuran</strong>', ''),
    ('Isi nilai <strong>TDS</strong> (Total Dissolved Solids, satuan ppm) dan <strong>pH</strong>', ''),
    ('Sistem otomatis evaluasi: TDS harus <500 ppm, pH harus 6.5–8.5', ''),
    ('Jika melebihi ambang batas → alert merah muncul otomatis + notifikasi ke Kepala SPPG', ''),
    ('Klik <strong>Simpan</strong>', ''),
  ])}
  {warn('TDS > 500 ppm atau pH di luar 6.5–8.5 = air tidak layak masak. Hentikan penggunaan dan laporkan segera ke Kepala SPPG.')}
""")}

{feature_box('👁️', 'Production Obs & Komunikasi Sekolah', f"""
  <p><strong>Production Obs:</strong> Catat temuan penting selama proses produksi berlangsung
  (contoh: temperature kontrol tidak terpenuhi, bahan terlihat kurang segar, dll).</p>
  {steps([
    ('Klik tab <strong>Production Obs</strong> → <strong>+ Observasi Baru</strong>', ''),
    ('Isi kategori (Higienitas/Suhu/Bahan/Proses), deskripsi, dan tingkat urgensi', ''),
    ('Simpan', ''),
  ])}
  <p style="margin-top:12px"><strong>Komunikasi Sekolah:</strong> Catat setiap komunikasi dengan pihak sekolah
  yang berkaitan dengan distribusi atau keluhan.</p>
  {steps([
    ('Klik tab <strong>Komunikasi Sekolah</strong> → <strong>+ Log Baru</strong>', ''),
    ('Pilih sekolah, metode komunikasi (telepon/WA/tatap muka), dan ringkasan isi komunikasi', ''),
    ('Simpan', ''),
  ])}
""")}

<h3>Weekly Report</h3>
{steps([
  ('Klik tab <strong>Weekly Report</strong>', ''),
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

BAB11 = chapter(11, "💰", "Akuntan Finance — Expense, LRA & Price Trends", "13:00", f"""
{roles('accountant','kepala')}

{story('''
<strong>13:00 siang.</strong> Akuntan selesai makan siang dan kembali ke meja kerjanya.
Saatnya urusan keuangan. Dia buka DPMBG, langsung ke modul Keuangan.
Ada beberapa pengeluaran operasional hari ini yang perlu dicatat,
laporan LRA biweekly hampir jatuh tempo (tinggal 2 hari),
dan ada satu bahan yang harganya naik 18% dari minggu lalu — perlu alert.
Semua dia urus dalam satu platform.
''')}

<h3>Halaman Akuntan Finance</h3>
<!-- SHOT:finance -->

<p>Judul halaman <strong>Akuntan Finance</strong> dengan subtitle
<em>"Price trends · Cost-per-porsi · Expense · LRA biweekly · PO Generator"</em>.
6 tab di atas: <code>Cost-per-porsi</code> (default aktif) · <code>Price Trends</code> · <code>Spike Alerts</code> · <code>Expense</code> · <code>LRA Biweekly</code> · <code>PO Generator</code>.</p>

<h3>Membuka Modul</h3>
{steps([
  ('Sidebar → klik grup <strong>▼ KEUANGAN</strong> → klik <strong>Akuntan Finance</strong> (icon 💰)', 'URL: /finance'),
])}

{feature_box('📈', 'Tab Price Trends & Spike Alerts', f"""
  {steps([
    ('Klik tab <strong>Price Trends</strong>', ''),
    ('Pilih bahan dari dropdown untuk melihat grafik harga historis (30/60/90 hari)', ''),
    ('Lihat kolom <strong>WoW%</strong> — perubahan harga minggu ini vs minggu lalu', ''),
    ('Klik tab <strong>Spike Alerts</strong> untuk daftar khusus bahan yang naik ≥15%', ''),
    ('Klik bahan yang spike untuk melihat detail riwayat harga dan supplier alternatif', ''),
  ])}
  {warn('Spike alert ≥15% berarti cost per porsi berisiko melewati batas Rp 15.000. Pertimbangkan substitusi bahan atau negosiasi ulang dengan supplier.')}
""")}

{feature_box('🧾', 'Tab Expense', f"""
  {steps([
    ('Klik tab <strong>Expense</strong>', ''),
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

{feature_box('📋', 'Tab LRA Biweekly (Laporan Realisasi Anggaran)', f"""
  <p>LRA adalah laporan keuangan wajib setiap 2 minggu yang merangkum seluruh pemasukan dan pengeluaran SPPG.</p>
  {steps([
    ('Klik tab <strong>LRA Biweekly</strong>', ''),
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

{feature_box('💼', 'Tab Cost-per-porsi (default tab aktif)', f"""
  <p>Tab default saat pertama buka modul Finance. Menampilkan cost-per-porsi harian/mingguan/bulanan,
  dengan threshold Rp 15.000 sebagai garis batas BGN.</p>
  {steps([
    ('Pilih rentang periode (Today / This Week / This Month / Custom)', ''),
    ('Lihat angka cost/porsi rata-rata dan grafik trend', ''),
    ('Warna merah = sudah lewat threshold, kuning = mendekati', ''),
  ])}
""")}

{feature_box('⚙️', 'Tab PO Generator', f"""
  <p>Auto-generate Purchase Order dari forecast Approval Menu (lihat Bab 5).</p>
  {steps([
    ('Klik tab <strong>PO Generator</strong>', ''),
    ('Pilih periode forecast yang sudah dihitung', ''),
    ('Pilih supplier per kategori bahan', ''),
    ('Klik <strong>Generate</strong> — PO baru muncul di halaman Purchase Orders dengan status <code>draft</code>', ''),
  ])}
""")}
""")


# ─────────────────────────────────────────────────────────────────────────────
# BAB 12 — Executive Dashboard
# ─────────────────────────────────────────────────────────────────────────────

SCREEN_EXEC = screen("/executive", "")

BAB12 = chapter(12, "📈", "Executive Dashboard & BGN Compliance Bundle", "14:00", f"""
{roles('kepala','super','platform')}

{story('''
<strong>14:00 siang.</strong> Kepala SPPG duduk di mejanya dengan secangkir kopi.
Saatnya review harian. Dia klik menu <em>Executive</em> di sidebar atas.
Dalam satu layar: total porsi terkonfirmasi hari ini, % sekolah yang sudah konfirmasi,
cost per porsi rata-rata, defect rate. Tab default <strong>Per Dapur</strong> aktif.
Dia klik tombol hijau <em>📦 Export BGN Compliance Bundle</em> di pojok kanan atas
dan file ZIP siap untuk laporan bulanan ke BGN.
''')}

<h3>Halaman Executive Dashboard</h3>
{SCREEN_EXEC}

<p>Judul halaman <strong>Executive Dashboard</strong> dengan subtitle
<em>"3 level: per-kitchen · multi-kitchen (yayasan) · platform-wide"</em>.
3 tab pemilih level:
<code>Per Dapur</code> (default aktif, untuk Kepala SPPG) ·
<code>Multi-SPPG (Yayasan)</code> (untuk Superadmin) ·
<code>Platform (Cross-Org)</code> (untuk Platform Admin).
Tombol hijau besar <strong>📦 Export BGN Compliance Bundle</strong> di kanan atas — satu klik download bundle JSON+PDF
yang berisi LRA + sampel + checklist + variance + porsi periode.</p>

{steps([
  ('Sidebar → klik <strong>Executive</strong> (pinned di atas, icon 📈)', 'URL: /executive'),
  ('Tab default <strong>Per Dapur</strong> sudah aktif — lihat KPI dapur yang lagi aktif', ''),
  ('Klik tab <strong>Multi-SPPG (Yayasan)</strong> kalau punya akses Superadmin — bandingin semua SPPG dalam organisasi', ''),
  ('Klik tab <strong>Platform (Cross-Org)</strong> kalau Platform Admin — lihat agregat lintas organisasi', ''),
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

{feature_box('🏆', 'Multi-SPPG Ranking (Superadmin)', f"""
  <p>Superadmin (Yayasan) bisa melihat perbandingan semua SPPG dalam satu organisasi.</p>
  {steps([
    ('Login sebagai <strong>Superadmin</strong>', ''),
    ('Buka Executive Dashboard → klik tab <strong>Multi-SPPG (Yayasan)</strong>', 'URL: /executive'),
    ('Lihat ranking: SPPG dengan skor kepatuhan terbaik, cost terendah, defect rate terendah', ''),
  ])}
""")}

<h3>BGN Compliance Bundle Export</h3>
{steps([
  ('Buka Executive Dashboard', 'Sidebar → Executive (icon 📈)'),
  ('Klik tombol hijau <strong>📦 Export BGN Compliance Bundle</strong> di kanan atas', ''),
  ('Pilih <strong>Dari Tanggal</strong> dan <strong>Sampai Tanggal</strong> (biasanya 1 bulan kalender berjalan)', ''),
  ('Sistem otomatis agregasi: LRA, sampel makanan, checklist, variance report, total porsi', ''),
  ('File ZIP berisi JSON + PDF terdownload — siap diserahkan ke BGN', ''),
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

{feature_box('🏫', 'Master Sekolah Binaan', f"""
  <p>Halaman <strong>Master Sekolah Binaan</strong> di <code>/admin/schools</code>.
  Default sandbox SPPG Paseh berisi 11 sekolah (3 TK, 7 SD, 1 SMP). Tabel kolom:
  <strong>Nama · Jenjang · Kelompok AKG · Siswa · Jarak (m) · Kontak · Status · Aksi</strong>.</p>
  {steps([
    ('Sidebar → ▼ MASTER DATA → klik <strong>Sekolah</strong> (icon 🏫)', 'URL: /admin/schools'),
    ('Centang checkbox <strong>Tampilkan non-aktif</strong> di header kalau mau lihat yang sudah dinonaktifkan', ''),
    ('Klik tombol biru <strong>+ Tambah Sekolah</strong> di kanan atas untuk mendaftarkan baru', ''),
    ('Isi: nama, jenjang (PAUD / TK / SD / SMP), kelompok AKG, jumlah siswa, jarak (m), kontak', ''),
    ('Jenjang menentukan wave pengiriman otomatis: PAUD/TK/SD = Wave 1; SMP = Wave 2', ''),
    ('Status default <span style="color:#059669">Aktif</span> — bisa di-Edit / Nonaktifkan per baris', ''),
  ])}
""")}

{feature_box('👤', 'Users — Manajemen Pengguna', f"""
  <p>Halaman <strong>Users</strong> di <code>/admin/users</code>. Tabel kolom:
  <strong>ID · USERNAME · ROLE · KITCHENS</strong> + aksi inline <strong>Role | Reset pw | Delete</strong> per baris.</p>
  {steps([
    ('Sidebar → ▼ ADMIN DAPUR → klik <strong>Users</strong> (icon 👤)', 'URL: /admin/users'),
    ('Klik tombol gelap <strong>+ New user</strong> di kanan atas', ''),
    ('Isi username, password awal, role global, dan assign ke kitchen tertentu', ''),
    ('Role per-kitchen yang bisa dipilih: <code>head_sppg</code>, <code>nutritionist</code>, <code>accountant</code>, <code>aslap</code>, <code>head_kitchen</code>', ''),
    ('Untuk ganti role user existing: klik link <strong>Role</strong> di baris user', ''),
    ('Untuk reset password: klik <strong>Reset pw</strong> — sistem generate password baru', ''),
    ('Untuk hapus user: klik <strong>Delete</strong> (warna merah)', ''),
  ])}
  {warn('Setiap pengguna hanya bisa melihat data dari dapur (kitchen) yang sama. Untuk akses multi-dapur, gunakan role Superadmin.')}
""")}

{feature_box('🏢', 'Kitchens & All Kitchens (Superadmin)', f"""
  {steps([
    ('Login sebagai <strong>Superadmin</strong>', ''),
    ('Sidebar → ▼ ADMIN DAPUR → klik <strong>Kitchens</strong> (icon 🏠) untuk kelola dapur per org', ''),
    ('Sidebar → ▼ ADMIN DAPUR → klik <strong>All Kitchens</strong> (icon 🌐) untuk overview lintas dapur', ''),
    ('Platform Admin bonus: ▼ PLATFORM → <strong>Organizations</strong> (icon 🏢) untuk kelola organisasi/yayasan', ''),
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
    ['H-1 | 13:00', '💰 Akuntan', 'Cek price trends + buat PO ke supplier', '▼ PENERIMAAN BAHAN → Purchase Orders'],
    ['H-1 | 17:00', '🥗 Ahli Gizi', 'Build menu (manual atau planner) + cek AKG real-time', '▼ MENU & GIZI → Build Manual / Menu Planner'],
    ['H-1 | 18:00', '🥗 Ahli Gizi', 'Submit menu untuk review', '▼ MENU & GIZI → Approval Menu'],
    ['H-1 | 18:00', '👔 Kepala SPPG', 'Approve atau reject menu (tab Nunggu Review)', '▼ MENU & GIZI → Approval Menu'],
    ['04:00', '🦺 ASLAP', 'Buat inspeksi saat truk supplier tiba (klik + Mulai Inspeksi)', '▼ PENERIMAAN BAHAN → Joint Inspection'],
    ['04:00', '🥗 Ahli Gizi', 'Sign-off kualitas gizi di inspeksi', '▼ PENERIMAAN BAHAN → Joint Inspection'],
    ['04:00', '💰 Akuntan', 'Sign-off kuantitas di inspeksi', '▼ PENERIMAAN BAHAN → Joint Inspection'],
    ['04:30', '👔 Kepala SPPG', 'Login & cek Dashboard + notifikasi bell', '⊞ Dashboard → 🔔 bell'],
    ['05:30', '👨‍🍳 Kepala Chef', 'Mulai batch produksi + scan QR container (tablet)', '▼ PRODUKSI & DISTRIBUSI → Production'],
    ['06:00', '🦺 ASLAP', 'Isi Checklist Hari Ini + Water Quality', '▼ LAPANGAN & MONITORING → ASLAP Daily'],
    ['07:00', '🥗 Ahli Gizi', 'Approve QC + ambil food sample', '▼ PRODUKSI & DISTRIBUSI → Production'],
    ['08:00', '🦺 ASLAP', 'Dispatch Wave 1 (PAUD/TK/SD)', '▼ PRODUKSI & DISTRIBUSI → Distribusi → tab Wave 1 & 2'],
    ['10:00', '🦺 ASLAP', 'Dispatch Wave 2 (SMP)', '▼ PRODUKSI & DISTRIBUSI → Distribusi → tab Wave 1 & 2'],
    ['13:00', '💰 Akuntan', 'Catat pengeluaran hari ini', '▼ KEUANGAN → Akuntan Finance → tab Expense'],
    ['14:00', '👔 Kepala SPPG', 'Review KPI + Export BGN Compliance Bundle', '📈 Executive (pinned)'],
    ['Jumat', '🦺 ASLAP', 'Generate + submit Weekly Report', '▼ LAPANGAN & MONITORING → ASLAP Daily → tab Weekly Report'],
    ['2x/bulan', '💰 Akuntan', 'Generate + submit LRA biweekly', '▼ KEUANGAN → Akuntan Finance → tab LRA Biweekly'],
    ['Kapan saja', '👩‍🏫 Guru Sekolah', 'Konfirmasi terima makanan (via link WA)', 'Halaman publik /confirm/<token>'],
  ]
)}

<h3>Shortcut Penting</h3>
{data_table(
  ['Situasi', 'Yang Harus Dilakukan', 'Lokasi'],
  [
    ['Bahan ditolak saat inspeksi', 'Klik Tolak Bahan → Buat Dispute → Catat alasan', 'Joint Inspection'],
    ['Kamera QR tidak bisa scan', 'Pakai tombol Scan → kalau gagal, ketik kode BHN-XXXXXXXX manual', 'Production'],
    ['Sekolah tidak konfirmasi', 'Hubungi guru dan kirim ulang link konfirmasi', 'Distribusi → tab Aggregate Hari Ini'],
    ['Spike harga bahan ≥15%', 'Alert otomatis muncul di tab Spike Alerts — cari supplier alternatif', 'Akuntan Finance → Spike Alerts'],
    ['Air TDS >500 atau pH abnormal', 'Alert otomatis → laporkan ke Kepala SPPG segera', 'ASLAP Daily → Water Quality'],
    ['Menu ditolak (Ditolak)', 'Cek catatan alasan dari Kepala SPPG → revisi → submit ulang', 'Approval Menu → tab Ditolak'],
    ['Lupa password', 'Hubungi Kepala SPPG atau Superadmin untuk klik Reset pw', 'Users (/admin/users)'],
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

  <h3>Daftar Lengkap Role & Hak Akses (Match Sidebar)</h3>
  {data_table(
    ['Menu Sidebar', '👔 Kepala', '🥗 Gizi', '💰 Akun', '🦺 ASLAP', '👨‍🍳 Chef'],
    [
      ['⊞ Dashboard', '✅', '✅', '✅', '✅', '✅'],
      ['📈 Executive', '✅', '✅', '✅', '✅', '✅'],
      ['☰ Menu Planner', '✅', '✅', '', '', ''],
      ['✎ Build Manual', '✅', '✅', '', '', ''],
      ['✓ Approval Menu', '✅ (approve)', '✅ (submit)', '', '', ''],
      ['📊 Nutrisi Harian', '✅', '✅', '', '', ''],
      ['📋 Purchase Orders', '✅', '✅ (read)', '✅', '✅ (read)', ''],
      ['🤝 Joint Inspection', '✅ (all)', '✅ (Quality)', '✅ (Quantity)', '✅ (Physical)', ''],
      ['↓ Receiving (Quick)', '✅', '', '', '✅', ''],
      ['🍳 Production', '✅', '✅ (QC approve)', '', '✅ (observe)', '✅ (start/end)'],
      ['🚐 Distribusi', '✅', '✅ (audit)', '✅ (read)', '✅ (dispatch)', ''],
      ['📝 ASLAP Daily', '✅ (view)', '', '', '✅ (isi)', ''],
      ['⚠ Scan Errors', '✅', '', '✅', '✅', '✅'],
      ['📉 Variance Report', '✅', '', '✅', '✅', ''],
      ['💰 Akuntan Finance', '✅ (ttd LRA)', '✅ (price trends)', '✅ (full)', '', ''],
      ['🏫 Sekolah', '✅', '✅ (read)', '✅ (read)', '✅ (read)', '✅ (read)'],
      ['📦 Supplier', '✅', '✅ (read)', '✅ (manage)', '✅ (read)', ''],
      ['🌐 All Kitchens', 'superadmin only', '', '', '', ''],
      ['🏠 Kitchens', '✅', '', '', '', ''],
      ['👤 Users', '✅', '', '', '', ''],
      ['🏢 Organizations', 'platform_admin only', '', '', '', ''],
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


