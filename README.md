# MBG Dapur Pintar – Phase 1 (Minimal Bot)

## Features

### Wave 1: Kitchen Admin & Price Management
- Kitchen-scoped admin dashboard (per-kitchen staff management)
- Manual price override (accountant can correct scraped prices)

### Wave 2: Compliance & Nutrition Foundation
- Price history audit trail (track all price changes)
- Variance & waste report (daily received/processed/packed/delivered tracking)
- Food nutrition override (ahli_gizi can adjust TKPI nutrition per-kitchen)

### Ahli Gizi Feature Pack: Nutrition & Menu Library
- **Laporan Nutrisi Harian** — daily nutrition report per school (`/nutrition`, date picker, AKG comparison)
- **AKG Compliance Tracker** — weekly calendar view with green/amber/red status per day
- **Simpan Menu** — save optimizer results to personal menu library; load/manage saved menus
- **Substitusi Bahan** — inline food substitution popover with cosine-similarity-ranked candidates

## 1) Setup
```bash
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
python init_db.py
cp .env.example .env   # fill in tokens/IDs
 