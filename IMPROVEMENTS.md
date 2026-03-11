# DPMBG Project — Improvement Ideas

## Status Legenda
- ✅ Done — sudah diimplementasi
- ⏳ Pending — belum dikerjakan
- 🚧 Partial — sebagian sudah ada

---

## Tabel Improvement

| # | Prioritas | Status | Ide | Penjelasan | Risk | Yang Perlu Dilakukan |
|---|-----------|--------|-----|------------|------|----------------------|
| 1 | 🔴 Critical | ✅ Done | **Export TKPI CSV** | Menu optimizer butuh `data/tkpi.csv` untuk jalan | Tanpa ini optimizer 500 error | Export sheet TKPI 2020 dari Excel → simpan ke `data/tkpi.csv` |
| 2 | 🔴 Critical | ✅ Done | **Render wake-up ping** | Render free tier tidur setelah 15 menit idle, bikin semua request timeout | Server "cold start" 30+ detik | Daftar UptimeRobot gratis, ping `/api/overview` tiap 5 menit |
| 3 | 🔴 Critical | ⏳ Pending | **Playwright di Render** | Price scraper pakai Playwright, tapi Render tidak otomatis install Chromium | Scraper gagal semua di production | Tambahkan `playwright install chromium` ke Render build command |
| 4 | 🔴 Critical | ⏳ Pending | **`difflib` missing import di price_scraper** | `_best_match_score()` di `price_scraper.py:64` memanggil `difflib.SequenceMatcher` tapi `import difflib` tidak ada di file | `NameError` saat fungsi ini dipanggil | Tambah `import difflib` di bagian atas `backend/services/price_scraper.py` |
| 5 | 🔴 Critical | ⏳ Pending | **`db_upsert_food_price` PostgreSQL-only** | Pakai `sqlalchemy.dialects.postgresql.insert` — crash kalau engine adalah SQLite (dev tanpa DATABASE_URL) | Error saat develop lokal tanpa Postgres | Buat fallback generic upsert: `try pg_insert except ImportError → delete+insert` |
| 6 | 🟠 High | ✅ Done | **Printer name auto-detect** | Mini PC daftarkan printer Windows-nya ke FastAPI saat startup | — | ✅ Sudah ada di printer poller |
| 7 | 🟠 High | ✅ Done | **Export laporan harian** | Tombol "Export Excel" di dashboard → file `.xlsx` 3 sheet: Ringkasan, Item Bahan, Tray | — | ✅ `GET /api/export/daily` |
| 8 | 🟠 High | ⏳ Pending | **JWT token expiry di frontend** | Token disimpan di `localStorage` dan tidak ada handling kalau expired. API akan 401 tapi UI tidak re-direct ke login — user stuck | User tidak bisa pakai app sampai clear storage manual | Intercept 401 di `api/client.js`, hapus token + redirect ke `/login` |
| 9 | 🟠 High | ⏳ Pending | **Rate limiting price scraper** | `POST /api/menu/prices/scrape` bisa dipanggil berkali-kali parallel, memicu ratusan Playwright subprocesses | Server OOM / crash di Render | Tambah flag `_scrape_running` global di scheduler, tolak request kalau sedang berjalan |
| 10 | 🟠 High | ⏳ Pending | **History menu optimizer** | Hasil optimize menu hilang setiap refresh. Tidak ada persistensi | Staff harus optimize ulang tiap buka halaman | Buat tabel `menu_plans` di DB + endpoint `GET /api/menu/plans` + halaman history di frontend |
| 11 | 🟠 High | ⏳ Pending | **Input harga bahan manual** | Staff bisa koreksi harga scraper yang salah dari UI | Harga Sayurbox untuk beberapa bahan tidak akurat (berat tidak dikenali) | Buat halaman admin harga: tabel food_prices + form edit harga per item |
| 12 | 🟠 High | ⏳ Pending | **Notifikasi WhatsApp** | Alert otomatis ke driver kalau tray siap dikirim, atau ke admin kalau scan error | Butuh WA gateway berbayar | Daftar Fonnte/WA Gateway → integrate ke `apply_delivery()` dan `log_scan_error()` |
| 13 | 🟡 Medium | ⏳ Pending | **Scan error retry / resolve** | Scan Errors tidak bisa di-mark resolved. Error menumpuk dan tidak ada cara membersihkan | Log jadi noise | Tambah kolom `resolved` + `resolved_at` di tabel `scan_errors` + tombol "Mark Resolved" di UI |
| 14 | 🟡 Medium | ⏳ Pending | **Role-based access control** | Semua user role `admin` bisa akses semua endpoint. Tidak ada pembatasan per role | Driver bisa lihat/edit data yang seharusnya admin-only | Tambah middleware check `user["role"]` per route, role: `admin`, `operator`, `driver` |
| 15 | 🟡 Medium | ⏳ Pending | **Scraper fallback source** | Jika Sayurbox down atau ganti DOM structure, scraper berhenti total | Semua harga tidak bisa di-update | Tambah scraper alternatif (Tokopedia search, HargaPangan.id) sebagai fallback |
| 16 | 🟡 Medium | ⏳ Pending | **DB connection pool habis** | Render free tier: engine pakai `NullPool` (tiap request buka koneksi baru). Di traffic tinggi bisa timeout | DB overload saat banyak scan serentak | Ganti ke `QueuePool` dengan `pool_size=3, max_overflow=5` di production |
| 17 | 🟡 Medium | ⏳ Pending | **Menu optimizer timeout** | LP solve 5 hari bisa lambat kalau food pool besar (ratusan item). Tidak ada timeout | Request hanging > 30 detik di Render | Tambah `PULP_CBC_CMD(msg=0, timeLimit=10)` + jalankan `optimize_week` di thread dengan timeout |
| 18 | 🟡 Medium | ⏳ Pending | **Schools dari DB, bukan JSON** | `data/schools.json` hardcoded. Tambah sekolah baru butuh deploy ulang | Non-technical admin tidak bisa update | Buat tabel `schools` di DB + CRUD endpoint + halaman admin sekolah |
| 19 | 🟡 Medium | ⏳ Pending | **Export menu optimizer ke PDF/Excel** | Hasil menu planner mingguan hanya bisa di-screenshot | Staff butuh format cetak untuk dibawa ke supplier | Tambah tombol export → generate `.xlsx` menu plan (satu sheet per hari) |
| 20 | 🟡 Medium | 🚧 Partial | **Multi-dapur support** | Kolom `kitchen_id` sudah ada di schema. Belum ada UI/filter/pemisahan data antar dapur | Data semua dapur tercampur jadi satu | Jalankan ALTER TABLE di Supabase + tambah `kitchen_id` filter ke semua API + UI dropdown |
| 21 | 🟡 Medium | ⏳ Pending | **Scan error: duplicate log** | Kalau scanner gagal kirim + retry, `log_scan_error` bisa nulis entry ganda untuk satu kejadian | Error count inflated | Tambah `idempotency_key` (hash dari `code+step+minute`) di `scan_errors` |
| 22 | 🟢 Nice | ✅ Done | **PWA / offline support** | Web bisa di-install di HP Android, service worker cache API 5 menit | — | ✅ Sudah via vite-plugin-pwa |
| 23 | 🟢 Nice | ⏳ Pending | **QR countdown di label** | QR code di stiker → scan → halaman countdown freshness | Butuh label min 50×30mm | Konfirmasi ukuran label baru → update ZPL di `generate_label()` |
| 24 | 🟢 Nice | ⏳ Pending | **Dark mode preference persist** | Dark mode toggle sudah ada tapi pakai `localStorage`. Seharusnya sync ke user preference di DB | Setting hilang kalau ganti device | Simpan preference di `users.settings` JSON column |
| 25 | 🟢 Nice | ⏳ Pending | **Pagination sekolah di delivery** | `DeliverySchoolStatus` show/hide pakai state lokal, bukan pagination proper | UX kurang baik kalau sekolah > 20 | Ganti ke pagination component yang sudah ada (`<Pagination />`) |
| 26 | 🟢 Nice | ⏳ Pending | **Search di Scan Errors** | Halaman Scan Errors tidak bisa filter by `step` atau `reason` | Sulit cari error spesifik | Tambah filter dropdown `step` + search input `code/reason` ke `GET /api/scan-errors` dan UI |
| 27 | 🟢 Nice | ⏳ Pending | **Audit log** | Tidak ada trail "siapa yang input apa kapan". Semua create/update tidak dicatat user-nya | Tidak bisa investigasi kalau ada data salah | Tambah kolom `created_by` (username) ke tabel `items` dan `trays` |
| 28 | 🟢 Nice | ⏳ Pending | **Tooltip nutrisi di menu planner** | NutrBar hanya tampil persentase angka, tidak ada konteks AKG target | User tidak tahu angka 600 kcal itu apa | Tambah tooltip on-hover yang tampilkan "X kcal dari target Y kcal" |
| 29 | 🟢 Nice | ⏳ Pending | **Scrape progress via SSE** | `POST /api/menu/prices/scrape` jalan di background tapi frontend hanya bisa poll status. Tidak ada live progress | UX: user tidak tahu sudah berapa persen | Push progress tiap N items via SSE channel yang sudah ada |
| 30 | 🟢 Nice | ⏳ Pending | **Unit test backend** | Tidak ada test sama sekali. Logic kritis seperti `_scan_allocations`, `optimize_day`, `_extract_grams` tidak ter-cover | Regresi tidak ketahuan saat refactor | Tambah `pytest` + test untuk fungsi kritis di `backend/services/` |

---

## Bug Aktif (Perlu Segera Fix)

| # | Bug | File | Baris | Impact | Fix |
|---|-----|------|-------|--------|-----|
| B1 | `difflib` tidak di-import | `backend/services/price_scraper.py` | 64 | `NameError` saat `_best_match_score()` dipanggil | Tambah `import difflib` di bagian atas file |
| B2 | `db_upsert_food_price` crash di SQLite | `backend/core/database.py` | 253 | Error di dev environment tanpa PostgreSQL | Fallback ke delete+insert kalau bukan Postgres |
| B3 | Scraper bisa dijalankan paralel | `backend/app.py` | 78 | OOM / crash kalau user klik scrape berkali-kali | Tambah `_scrape_running` flag + 409 response kalau busy |

---

## Yang Belum Diimplementasi (Prioritas Tinggi)

| # | Ide | Yang Perlu Dilakukan |
|---|-----|----------------------|
| 3 | Playwright di Render | Tambah `playwright install chromium` ke build command Render |
| 8 | JWT 401 handling | Intercept 401 di `frontend/src/api/client.js`, clear token + redirect login |
| 9 | Rate limiting scraper | Flag `_scrape_running` di `price_scheduler.py`, return 409 kalau busy |
| 10 | History menu | Tabel `menu_plans` + `GET/POST /api/menu/plans` + halaman frontend |
| 11 | Input harga manual | Halaman admin harga bahan, edit `food_prices` dari UI |
| 12 | Notifikasi WhatsApp | Daftar Fonnte → integrate ke `log_scan_error()` dan `apply_delivery()` |
| 13 | Scan error resolve | Kolom `resolved` di scan_errors + tombol "Mark Resolved" di UI |
| 20 | Multi-dapur | ALTER TABLE + filter `kitchen_id` di API + UI dropdown |

---

## Catatan Implementasi

### No.2 — UptimeRobot
1. Daftar gratis di https://uptimerobot.com
2. Add New Monitor → HTTP(s)
3. URL: `https://dapurpintarmbg.onrender.com/api/overview`
4. Interval: 5 minutes

### No.3 — Playwright di Render
Di Render dashboard → your service → Settings → Build Command:
```
pip install -r requirements.txt && playwright install chromium
```

### No.10 — PWA
- Setelah Render deploy, buka di Chrome Android → menu ⋮ → "Add to Home Screen"
- Auto-update saat ada versi baru
- API `/api/*` di-cache NetworkFirst (5 menit)

### No.20 — Multi-dapur (partial)
Jalankan di Supabase SQL editor:
```sql
ALTER TABLE items ADD COLUMN IF NOT EXISTS kitchen_id TEXT;
ALTER TABLE trays ADD COLUMN IF NOT EXISTS kitchen_id TEXT;
```

### No.B1 — Fix `difflib` import
```python
# Tambah di baris 1-25 backend/services/price_scraper.py
import difflib
```

### No.9 — Rate limiting scraper (contoh implementasi)
```python
# Di backend/services/price_scheduler.py
_scrape_running = False

def run_price_scrape(...):
    global _scrape_running
    if _scrape_running:
        return {"error": "already_running"}
    _scrape_running = True
    try:
        ...
    finally:
        _scrape_running = False
```
