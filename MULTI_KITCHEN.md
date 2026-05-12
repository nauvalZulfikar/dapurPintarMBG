# Multi-Kitchen Ops Guide

Guide untuk menambah dapur baru dan mengelola multi-user.

## 1. One-time migration (hanya dijalankan sekali per database)

```bash
python -m backend.scripts.inspect_schema          # read-only preview
python -m backend.scripts.migrate_multi_kitchen   # applies schema changes
```

Migration idempotent, aman di-run ulang. Yang terjadi:
- Buat tabel `kitchens`, seed id=1 "paseh" dari nilai `.env`
- Buat tabel `user_kitchens`, map user `admin` → kitchen 1 sebagai `kitchen_admin`
- Tambah `kitchen_id INTEGER` FK ke `items`, `trays`, `tray_items`, `scan_errors`, `print_jobs`, `food_prices`
- Backfill semua baris existing ke kitchen_id=1
- Ganti unique constraint `trays(tray_id)` → `(tray_id, kitchen_id)`, `food_prices(food_code)` → `(food_code, kitchen_id)`

## 2. Promote user ke superadmin

Superadmin bisa lihat & switch ke semua dapur, akses halaman `/admin/kitchens` & `/admin/users`.

```sql
UPDATE users SET role = 'superadmin' WHERE username = 'your-username';
```

Atau via UI (bila sudah ada superadmin lain):
- Login sebagai superadmin → `/admin/users` → klik "Role" pada user target

## 3. Tambah dapur baru

### Via UI (rekomendasi)
1. Login sebagai superadmin
2. Buka `/admin/kitchens` → "New kitchen"
3. Isi:
   - **Slug** (unik, e.g. `bandung-1`) — tidak bisa diubah setelah dibuat
   - **Name** (display, e.g. `DPMBG Bandung 1`)
   - **Printer name** (Windows device name, e.g. `DPMBGBdg1ZP550`)
   - **Printer lang** (ZPL atau TSPL)
   - **Scanner key** & **Cloud print key** — biarkan kosong untuk auto-generate
4. Save → catat kunci yang ter-generate (muncul di tabel setelah refresh)

### Via SQL
```sql
INSERT INTO kitchens (slug, name, printer_name, printer_lang, label_title,
                      scanner_key, cloud_print_key)
VALUES ('bandung-1', 'DPMBG Bandung 1', 'DPMBGBdg1ZP550', 'ZPL',
        'MBG Bandung 1',
        'GENERATED_WITH_token_urlsafe_24',
        'GENERATED_WITH_token_urlsafe_24');
```

## 4. Assign user ke dapur

- `/admin/users` → pilih user → dropdown "+ assign kitchen..." → pick role (`staff` | `kitchen_admin`)
- User bisa ter-assign ke >1 dapur; dropdown switcher di sidebar muncul otomatis

## 5. Deploy scanner & printer agent per dapur

### Scanner
Tiap dapur punya `scanner_key` sendiri. Update env scanner client di dapur itu:
```env
API_BASE_URL=https://dapurpintarmbg.aureonforge.com
SCANNER_KEY=<kitchen.scanner_key>
```
Backend resolve key → `kitchen_id`. Tidak perlu kirim kitchen_id di body.

### Printer agent
Tiap dapur punya mini-PC sendiri jalankan `printer_poller.py` / WS client dengan key dapurnya:
```env
API_BASE_URL=https://dapurpintarmbg.aureonforge.com
CLOUD_PRINT_KEY=<kitchen.cloud_print_key>
PRINTER_NAME=<kitchen.printer_name>
```
WS endpoint `/ws/printer?key=<cloud_print_key>` — backend route job hanya ke agent yang match `kitchen_id`.

## 6. Isolation test (recommended)

Sebelum production:
1. Create kitchen test `zz-test`
2. Create user test ter-assign ke `zz-test` saja
3. Login sebagai user test, verifikasi:
   - Dashboard hanya show data `zz-test` (tidak bocor dari kitchen lain)
   - `/api/items`, `/api/trays`, `/api/scan-errors` empty
   - Scanner key kitchen lain ditolak (403)

## 7. Legacy single-tenant compatibility

Untuk transisi mulus:
- `SCANNER_KEY`/`CLOUD_PRINT_KEY` env lama tetap valid → route ke kitchen id=1
- User role lama `admin` diperlakukan sebagai `superadmin`
- Setelah semua dapur onboard & semua scanner/printer pakai per-kitchen key: hapus env global

## 8. Schema reference

| Tabel | Kolom baru | Keterangan |
|---|---|---|
| `kitchens` | *new* | Tenant root |
| `user_kitchens` | *new* | User↔Kitchen M2M + per-kitchen role |
| `users` | — | `role` sekarang global (`superadmin`/`user`) |
| `items` | `kitchen_id` INT FK | scoping produksi |
| `trays` | `kitchen_id` INT FK | tray_id unik per (tray_id, kitchen_id) |
| `tray_items` | `kitchen_id` INT FK | registry tray per dapur |
| `scan_errors` | `kitchen_id` INT FK | log error per dapur |
| `print_jobs` | `kitchen_id` INT FK | queue print per dapur |
| `food_prices` | `kitchen_id` INT FK nullable | NULL=global, set=override per dapur |
