# DPMBG Project — Improvement Ideas

| # | Prioritas | Status | Ide | Penjelasan |
|---|-----------|--------|-----|------------|
| 1 | 🔴 Critical | ⏳ Pending | **Export TKPI CSV** | Menu optimizer belum bisa jalan sama sekali. Perlu export sheet TKPI 2020 dari Excel ke `data/tkpi.csv` |
| 2 | 🔴 Critical | ✅ Done | **Render wake-up ping** | Daftar UptimeRobot (gratis), ping `dapurpintarmbg.onrender.com` setiap 5 menit biar server ga tidur |
| 3 | 🟠 High | ✅ Done | **Printer name auto-detect** | Mini PC register daftar printer Windows-nya ke FastAPI saat startup via `POST /api/printer/register` |
| 4 | 🟠 High | ✅ Done | **Export laporan harian** | Tombol "Export Excel" di dashboard → file `.xlsx` 3 sheet: Ringkasan, Item Bahan, Tray |
| 5 | 🟠 High | ⏳ Pending | **Notifikasi WhatsApp** | Alert otomatis ke driver kalau tray siap dikirim, atau ke admin kalau ada scan error |
| 6 | 🟡 Medium | ⏳ Pending | **History menu optimizer** | Hasil optimize menu hilang setiap refresh. Perlu tabel `menu_plans` di DB |
| 7 | 🟡 Medium | ⏳ Pending | **Input harga bahan manual** | Staff bisa update harga bahan makanan dari UI, disimpan ke DB, dipakai optimizer |
| 8 | 🟡 Medium | ⏳ Pending | **Scan error retry** | Tambah tombol "Mark Resolved" di halaman Scan Errors |
| 9 | 🟡 Medium | ⏳ Pending | **Role-based access** | Tambah role: `admin`, `operator`, `driver` — driver cuma lihat delivery |
| 10 | 🟢 Nice | ✅ Done | **PWA / offline support** | Web bisa di-install di HP Android. Service worker cache API calls 5 menit |
| 11 | 🟢 Nice | ✅ Done (partial) | **Multi-dapur** | Kolom `kitchen_id` (nullable) sudah di schema. Perlu ALTER TABLE di Supabase |
| 12 | 🟢 Nice | ⏳ Pending | **QR countdown di label** | QR code di stiker → scan → halaman countdown freshness. Butuh label min 50×30mm |

---

## Yang Belum Diimplement

| # | Ide | Yang Perlu Dilakukan |
|---|-----|----------------------|
| 1 | Export TKPI CSV | Lo export sheet TKPI dari Excel → simpan ke `data/tkpi.csv` |
| 5 | Notifikasi WhatsApp | Daftar Fonnte/WA Gateway → gw integrate ke kode |
| 6 | History menu optimizer | Gw buat tabel `menu_plans` + halaman history di frontend |
| 7 | Input harga bahan manual | Gw buat halaman admin harga bahan |
| 8 | Scan error retry | Gw tambah tombol "Mark Resolved" di Scan Errors |
| 9 | Role-based access | Gw tambah kolom `role` + middleware per route |
| 12 | QR countdown di label | Lo konfirmasi ukuran label baru (min 50×30mm) → gw update ZPL |

---

## Catatan Implementasi

### No.2 — UptimeRobot
1. Daftar gratis di https://uptimerobot.com
2. Add New Monitor → HTTP(s)
3. URL: `https://dapurpintarmbg.onrender.com/api/overview`
4. Interval: 5 minutes

### No.10 — PWA
- Setelah Render deploy, buka di Chrome Android → menu ⋮ → "Add to Home Screen"
- Auto-update saat ada versi baru
- API `/api/*` di-cache NetworkFirst (5 menit)

### No.11 — Multi-dapur (partial)
Jalankan di Supabase SQL editor:
```sql
ALTER TABLE items ADD COLUMN IF NOT EXISTS kitchen_id TEXT;
ALTER TABLE trays ADD COLUMN IF NOT EXISTS kitchen_id TEXT;
```
