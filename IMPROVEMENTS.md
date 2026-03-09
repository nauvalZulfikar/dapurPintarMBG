# DPMBG Project — Improvement Ideas

| # | Prioritas | Status | Ide | Penjelasan |
|---|-----------|--------|-----|------------|
| 1 | 🔴 Critical | ⏳ Pending | **Export TKPI CSV** | Menu optimizer belum bisa jalan sama sekali. Perlu export sheet TKPI 2020 dari Excel ke `data/tkpi.csv` |
| 2 | 🔴 Critical | ✅ Done | **Render wake-up ping** | Daftar UptimeRobot (gratis), ping `dapurpintarmbg.onrender.com` setiap 5 menit biar server ga tidur |
| 3 | 🟠 High | ✅ Done | **Printer name auto-detect** | Mini PC register daftar printer Windows-nya ke FastAPI saat startup via `POST /api/printer/register`. Frontend bisa ambil via `GET /api/printer/list` |
| 4 | 🟠 High | ✅ Done | **Export laporan harian** | Tombol "Export Excel" di dashboard menghasilkan file `.xlsx` 3 sheet: Ringkasan, Item Bahan, Tray. Endpoint: `GET /api/export/daily?date=` |
| 5 | 🟠 High | ⏳ Pending | **Notifikasi WhatsApp** | Alert otomatis ke driver kalau tray siap dikirim, atau ke admin kalau ada scan error. Bisa pakai Fonnte/WA Gateway |
| 6 | 🟡 Medium | ⏳ Pending | **History menu optimizer** | Hasil optimize menu hilang setiap refresh. Perlu tabel `menu_plans` di DB biar bisa lihat rencana menu minggu lalu |
| 7 | 🟡 Medium | ⏳ Pending | **Input harga bahan manual** | Staff bisa update harga bahan makanan dari UI, disimpan ke DB, dipakai optimizer. Lebih fleksibel dari harga TKPI yang statis |
| 8 | 🟡 Medium | ⏳ Pending | **Scan error retry** | Kalau scan gagal, sekarang cuma masuk log. Tambah tombol "retry" atau "manual resolve" di halaman Scan Errors |
| 9 | 🟡 Medium | ⏳ Pending | **Role-based access** | Semua user bisa akses semua fitur. Tambah role: `admin`, `operator`, `driver` — driver cuma lihat delivery, operator cuma bisa scan |
| 10 | 🟢 Nice | ⏳ Pending | **PWA / offline support** | Jadiin web app installable di HP Android buat scanner/driver. Pakai service worker biar bisa jalan meski sinyal lemah. Berguna buat driver di jalan atau scanner di area gudang yang sinyal lemah |
| 11 | 🟢 Nice | ✅ Done (partial) | **Multi-dapur** | Kolom `kitchen_id` (nullable) sudah ditambah ke schema `items` dan `trays`. Perlu jalankan ALTER TABLE di Supabase, dan tambah UI filter per dapur |
| 12 | 🟢 Nice | ⏳ Pending | **QR countdown di label** | Label stiker sekarang cuma barcode ID. Bisa tambah QR code kecil yang link ke halaman countdown freshness — tapi butuh label lebih besar (min 50×30mm) |

---

## Catatan Implementasi

### No.2 — UptimeRobot
1. Daftar gratis di https://uptimerobot.com
2. Add New Monitor → HTTP(s)
3. URL: `https://dapurpintarmbg.onrender.com/api/overview`
4. Interval: 5 minutes

### No.3 — Printer Auto-detect
- Mini PC kirim daftar printer saat `printer_poller.py` startup
- API: `POST /api/printer/register` (X-Print-Key header)
- Lihat daftar: `GET /api/printer/list`
- Data disimpan in-memory (reset saat Render restart — cukup untuk use case ini)

### No.4 — Export Excel
- Tombol "Export Excel" ada di pojok kanan atas Dashboard
- Download file: `laporan_mbg_YYYY-MM-DD.xlsx`
- 3 sheet: Ringkasan, Item Bahan, Tray

### No.11 — Multi-dapur (partial)
- Kolom `kitchen_id` sudah ada di SQLAlchemy schema (nullable)
- Jalankan di Supabase SQL editor:
  ```sql
  ALTER TABLE items ADD COLUMN IF NOT EXISTS kitchen_id TEXT;
  ALTER TABLE trays ADD COLUMN IF NOT EXISTS kitchen_id TEXT;
  ```
- UI filter per dapur dan `KITCHEN_ID` env var belum diimplementasi

---

## Urutan Rekomendasi Pengerjaan Selanjutnya

1. **No.1** — Export TKPI CSV (biar menu planner bisa dipakai)
2. **No.5** — Notifikasi WhatsApp
3. **No.6** — History menu optimizer
4. **No.9** — Role-based access
