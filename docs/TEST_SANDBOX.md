# Test Sandbox — DPMBG

Sandbox terisolasi penuh dari data produksi. Aman buat eksplorasi semua fitur.

## Kredensial

| Field | Value |
|---|---|
| URL | http://localhost:5173/ |
| Username | `testadmin` |
| Password | `testadmin123` |
| Org slug | `testsandbox` (optional; isi cuma kalau diminta) |
| Role | `superadmin` (akses semua fitur dalam org sandbox) |
| Org ID | 19 |
| Kitchen | `Test Sandbox Kitchen` (id=78) |

## Cara Re-seed (kalau data udah kacau / mau fresh)

```powershell
cd "D:\Downloads\coding project\_mbg\DPMBG_Project"
python -m backend.scripts.seed_test_sandbox
```

- **Master rows** (org, kitchen, user, schools, suppliers, food prices) — upsert (idempotent).
- **Operational rows** (menu, PO, inspection, batch, expense, dll) — append-only, di-tag tanggal hari ini, jadi lu bisa lihat history per-hari.

Wipe total (hapus org+kitchen+semua data sandbox):
```powershell
python -m backend.scripts.seed_test_sandbox --wipe
```

## Data yang Tersedia (per re-seed)

| Kategori | Isi |
|---|---|
| Sekolah (3) | TK Mawar (40 siswa), SD Tunas Bangsa (120 siswa), SMP Bina (90 siswa) |
| Supplier (3) | Toko Sayur, Pak Budi Daging, Beras Sehat |
| Food prices (8) | Beras, Ayam, Telur, Bayam, Wortel, Tomat, Tempe, Tahu |
| Menu | 1 menu approved per hari (Nasi Ayam Bayam) |
| PO | 1 PO sent per hari (3 line items) |
| Inspeksi | 1 inspection finalized per hari (3 sign-offs lengkap) |
| Production | 1 batch ended per hari (5 porsi, qc_passed) |
| ASLAP | Checklist + water quality + observation + comm log |
| Finance | 2 expenses + 1 volunteer payment per hari |
| Student request | 1 request alergi per hari |

---

# Fitur Lengkap — Group by Role

## 🔵 SEMUA ROLE

### Login & Dashboard
- **Akses:** http://localhost:5173/login
- **Cara:** Isi username + password → Sign In
- **Hasil:** Redirect ke `/` (Dashboard utama). Sidebar muncul, KPI hari ini terlihat.
- **Catat:** First login lambat ~17-20s (audit log ke remote DB). Selanjutnya cepat.

### Notifikasi (Bell)
- **Akses:** Icon bell pojok kanan atas (di setiap halaman)
- **Cara:** Klik bell → panel dropdown muncul → klik notif → diarahkan ke target
- **Hasil:** Notif real-time via SSE. Counter angka merah kalau ada unread.
- **Endpoint:** `GET /api/notifications`, `POST /api/notifications/{id}/read`

### Dashboard Eksekutif (View KPI)
- **Akses:** `/executive` (sidebar → "Eksekutif")
- **Cara:** Default tab "KPI" — pilih periode → liat compliance score 5-faktor
- **Hasil:** Skor 0-100, on-time delivery rate, leftover %, varians biaya
- **Endpoint:** `GET /api/executive/kpi`, `/compliance-score`, `/trend`

---

## 👑 PLATFORM_ADMIN (cross-org — vendor SaaS)

> **Note:** `testadmin` adalah `superadmin` testorg, BUKAN platform_admin. Buat test platform_admin perlu user terpisah.

### Manage Organizations (cross-tenant)
- **Akses:** `/admin/organizations`
- **Cara:** "Tambah Organisasi" → isi slug + name → Save
- **Hasil:** Org baru terlihat di list, bisa di-assign kitchens
- **Endpoint:** `GET/POST/PATCH/DELETE /api/organizations`

---

## 🏛️ SUPERADMIN (yayasan owner — multi-SPPG dalam 1 org)

`testadmin` punya role ini.

### Manage Kitchens
- **Akses:** `/admin/kitchens`
- **Cara:** "Tambah Kitchen" → isi name + slug + printer config → Save
- **Hasil:** Kitchen baru muncul, bisa di-assign user
- **Endpoint:** `GET/POST/PATCH/DELETE /api/kitchens`

### Switch Active Kitchen
- **Akses:** Dropdown nama kitchen di header
- **Cara:** Pilih kitchen lain → JWT auto-rotate
- **Hasil:** Semua data di-scope ke kitchen baru

### Multi-Kitchen Ranking
- **Akses:** `/executive` → tab "Ranking" (kalau >1 kitchen)
- **Cara:** Scroll ke bagian leaderboard
- **Hasil:** Tabel skor per-kitchen, GINI inequality coefficient

### Compliance Bundle Export (org-wide)
- **Akses:** `/executive` → tombol "Export Bundle"
- **Cara:** Pilih periode → Generate
- **Hasil:** ZIP file: LRA + sampel + sign-off + sertifikat (audit-ready)
- **Endpoint:** `GET /api/executive/compliance-bundle`

---

## 🧑‍💼 HEAD_SPPG / Kepala SPPG (admin 1 dapur)

`testadmin` punya semua permission ini juga (superadmin > head_sppg).

### Menu Approval
- **Akses:** `/menu-approval`
- **Cara:** 
  1. Liat list menu status `pending_review`
  2. Klik menu → review komposisi gizi + AKG compliance
  3. Klik **✅ Approve** atau **❌ Reject** (boleh kasih notes)
- **Hasil:** Status berubah → `approved` atau `rejected_by_head_sppg`. Notif ke Ahli Gizi.
- **Endpoint:** `POST /api/menu/saved/{id}/approve`, `/reject`
- **Test data:** Menu "Sandbox Menu YYYY-MM-DD" sudah approved (re-seed bikin baru tiap hari)

### Lock Menu Cycle
- **Akses:** `/menu-approval` → menu approved → tombol "🔒 Lock Cycle"
- **Cara:** Klik Lock → confirm
- **Hasil:** Status → `locked`. Cycle 20-hari nggak bisa di-edit lagi.

### Inspeksi — Sign-off Quality
- **Akses:** `/inspections`
- **Cara:** 
  1. Klik inspeksi `pending`
  2. Tab "Quality" → review bahan (kondisi, kebersihan)
  3. Tanda tangan digital (canvas signature) → Submit
- **Hasil:** 1 dari 3 TTD recorded. Setelah 3 lengkap, tombol "Finalize" aktif.
- **Endpoint:** `POST /api/inspections/{id}/signoff` (role=quality)
- **Test data:** Sudah ada 1 inspection finalized per hari.

### Finalize Inspection
- **Akses:** `/inspections/{id}` → tombol "Finalize" (muncul setelah 3 TTD)
- **Cara:** Klik → confirm
- **Hasil:** Inspection `accepted` (atau `partial`/`rejected`). Bahan masuk stock.

### LRA Sign-off
- **Akses:** `/finance` → tab "LRA"
- **Cara:** Pilih period → review draft Akuntan → "Sign-off"
- **Hasil:** LRA biweekly resmi, masuk Compliance Bundle.
- **Endpoint:** `POST /api/finance/lra/periods/{id}/submit`

### Manajemen Pengguna
- **Akses:** `/admin/users`
- **Cara:** 
  - Tambah: "Tambah User" → username + password + role → Save
  - Edit role: klik baris → ubah role → Save
  - Reset password: klik "Reset Password"
- **Hasil:** User CRUD, assign ke kitchen tertentu
- **Endpoint:** `GET/POST/PATCH/DELETE /api/users`

### Manajemen Sekolah
- **Akses:** `/admin/schools`
- **Cara:** "Tambah Sekolah" → name + level (PAUD/TK/SD/SMP/SMA) + age_group + student_count + distance + GPS
- **Hasil:** Sekolah masuk daftar penerima. Dipakai distribusi + wave classifier.
- **Endpoint:** `GET/POST/PATCH/DELETE /api/admin/schools`
- **Test data:** 3 sekolah seeded.

### Manajemen Supplier (read + manage)
- **Akses:** `/admin/suppliers`
- **Cara:** Sama dengan sekolah — CRUD form
- **Hasil:** Supplier list aktif untuk PO
- **Test data:** 3 supplier seeded.

### Approve Permintaan Khusus Siswa
- **Akses:** `/menu-approval` → tab "Permintaan Khusus"
- **Cara:** Klik request → "Resolve" + tulis solusi
- **Hasil:** Status → `fulfilled`. Notif ke pembuat request.
- **Endpoint:** `PATCH /api/student-requests/{id}`
- **Test data:** 1 request "alergi telur" per hari.

### ASLAP Report Sign-off
- **Akses:** `/aslap` → tab "Reports"
- **Cara:** Pilih draft report → "Sign-off"
- **Hasil:** Report resmi, masuk audit bundle.
- **Endpoint:** `POST /api/aslap/reports/{id}/submit`

---

## 🥗 NUTRITIONIST / Ahli Gizi

> Buat test sebagai role ini, bikin user baru via `/admin/users`: role `user`, kitchen role `nutritionist`.

### Build Menu Manual
- **Akses:** `/menu-manual`
- **Cara:**
  1. Pilih age_group (TK 4-6 / SD 7-9 / SD 10-12 / SMP / SMA)
  2. Drag-drop bahan dari katalog → kanan
  3. Set gram per bahan → totals + AKG compare update real-time
  4. Cek ✅ AKG compliance, biaya per porsi
  5. Save → status `draft`
- **Hasil:** Menu draft dengan komposisi gizi (kalori, protein, lemak, karbo) + cost
- **Endpoint:** `POST /api/menu/calc`, `POST /api/menu/saved`

### Reverse Optimizer
- **Akses:** `/menu-manual` → tombol "⚡ Auto-Optimize"
- **Cara:** Set target AKG + budget → Generate
- **Hasil:** Menu kombinasi terbaik dari bahan yang tersedia
- **Endpoint:** `POST /api/menu/optimize`

### Cek Siklus 20 Hari
- **Akses:** `/menu-manual` → tombol "🔄 Cek Siklus"
- **Cara:** Klik
- **Hasil:** Warning kalo ada bahan repetitive di siklus 20 hari (BGN compliance)
- **Endpoint:** `GET /api/menu/cycle-check?days=20`

### Forecast Kebutuhan Bahan
- **Akses:** `/menu-manual` → tombol "Forecast"
- **Cara:** Pilih range tanggal
- **Hasil:** List bahan + total grams yang harus dibeli
- **Endpoint:** `GET /api/menu/forecast?from=...&to=...`

### Submit Menu for Review
- **Akses:** `/menu-manual` → menu saved → tombol "Submit for Review"
- **Cara:** Klik → confirm
- **Hasil:** Status → `pending_review`. Notif ke Kepala SPPG.
- **Endpoint:** `POST /api/menu/saved/{id}/submit`

### Laporan Gizi (Nutrition Report)
- **Akses:** `/nutrisi`
- **Cara:** Pilih periode → Generate
- **Hasil:** Tabel/chart compliance AKG per menu/per minggu
- **Endpoint:** `GET /api/nutrition/report`

### Inspeksi — Sign-off Quality
Sama seperti head_sppg di atas (TTD quality).

### QC Approve Produksi
- **Akses:** `/production` → batch status `qc_pending`
- **Cara:** 
  1. Klik batch → review samples
  2. Input lokasi sampel ("Kulkas QC rak X")
  3. Klik "QC Approve"
- **Hasil:** Status → `qc_passed`. Sample auto-saved 24-48 jam.
- **Endpoint:** `POST /api/production/batches/{id}/qc`

### Manajemen Sampel
- **Akses:** `/production` → tab "Sampel"
- **Cara:** Liat daftar sampel + expire_at countdown
- **Hasil:** Bisa marking discard kalo expired

---

## 💰 ACCOUNTANT / Akuntan

### Purchase Order
- **Akses:** `/purchase-orders`
- **Cara:**
  1. Klik "PO Baru" → modal muncul
  2. Pilih supplier → tambah item lines (item_name, weight, unit_price)
  3. Total auto-calculate
  4. Save → status `draft`
  5. Klik PO → "Mark Sent" → status `sent` (kirim ke supplier)
- **Hasil:** PO terbit, masuk daftar inspeksi nanti
- **Endpoint:** `GET/POST/PATCH /api/purchase-orders`
- **Test data:** 1 PO sent per hari (3 line items, supplier "Pak Budi Daging").

### Auto-Generate PO dari Forecast
- **Akses:** `/purchase-orders` → "Generate from Forecast"
- **Cara:** Pilih tanggal target → supplier → Submit
- **Hasil:** PO otomatis ngikutin forecast Ahli Gizi
- **Endpoint:** `POST /api/finance/po/generate-from-forecast`

### Tren Harga & Spike Alert
- **Akses:** `/finance` → tab "Trends"
- **Cara:** Pilih bahan → liat chart 30 hari
- **Hasil:** Line chart harga, alert merah kalo >20% spike
- **Endpoint:** `GET /api/finance/price-trends`, `/spike-alerts`

### Expense Tracker
- **Akses:** `/finance` → tab "Expense"
- **Cara:** "Tambah Expense" → category (utility/transport/dll) + amount + description → Save
- **Hasil:** Expense tercatat, masuk LRA aggregate
- **Endpoint:** `POST /api/finance/expenses`
- **Test data:** 2 expenses per hari (PLN + transport).

### LRA Generate
- **Akses:** `/finance` → tab "LRA" → "Generate Period"
- **Cara:** Pilih start/end date → Generate
- **Hasil:** Draft LRA biweekly. Kirim ke Kepala SPPG buat sign-off.
- **Endpoint:** `POST /api/finance/lra/generate`

### Pembayaran Relawan
- **Akses:** `/finance` → tab "Volunteer"
- **Cara:** "Tambah" → name + role + honor + tanggal → Save
- **Hasil:** Volunteer payment tercatat
- **Endpoint:** `POST /api/finance/volunteers`
- **Test data:** 1 volunteer "Bu Yani" per hari.

### Inspeksi — Sign-off Quantity
- **Akses:** `/inspections/{id}` → tab "Quantity"
- **Cara:** Sama dengan quality, beda role
- **Hasil:** TTD quantity recorded
- **Endpoint:** `POST /api/inspections/{id}/signoff` (role=quantity)

### Resolve Dispute
- **Akses:** `/inspections` → klik dispute (kalo ada)
- **Cara:** Liat detail → tulis resolution → "Resolve"
- **Hasil:** Status → `resolved`
- **Endpoint:** `POST /api/disputes/{id}/resolve`

---

## 🦺 ASLAP / Asisten Lapangan

### Buat Inspeksi Baru
- **Akses:** `/inspections`
- **Cara:**
  1. Klik "Inspeksi Baru" → pilih PO yang status `sent`
  2. Modal muncul → review lines auto-loaded dari PO
  3. Save → inspection `pending`
- **Hasil:** Inspection terbuka, siap diisi
- **Endpoint:** `POST /api/inspections`

### Container Split
- **Akses:** `/inspections/{id}` → expand line item
- **Cara:**
  1. Klik "Split Containers" → input jumlah container
  2. Set weight per container (atau auto-distribute)
  3. Submit
- **Hasil:** N containers ter-generate dengan ID `BHN-XXXXX` masing-masing. Label print queue.
- **Endpoint:** `POST /api/inspections/{id}/lines/{line_id}/accept`

### Inspeksi — Sign-off Physical
- **Akses:** `/inspections/{id}` → tab "Physical"
- **Cara:** Centang kondisi fisik (kemasan, kebersihan) → Submit
- **Hasil:** TTD physical recorded
- **Endpoint:** `POST /api/inspections/{id}/signoff` (role=physical)

### Distribusi — Dispatch
- **Akses:** `/distributions`
- **Cara:** 
  1. Liat wave 1 (PAUD/TK/SD-low) di pagi, wave 2 (SD-high/SMP/SMA) di siang
  2. Klik wave → review delivery
  3. "Dispatch" → status `dispatched`
- **Hasil:** Sopir berangkat, status tracking aktif
- **Endpoint:** `POST /api/distributions/{id}/dispatch`

### Distribusi — Input Leftover
- **Akses:** `/distributions` → tab "Leftover"
- **Cara:** Pilih sekolah → input porsi sisa + reason (absent/over-portion/dll) → Save
- **Hasil:** Leftover tercatat, masuk waste report
- **Endpoint:** `POST /api/distributions/leftovers`
- **Test data:** 4 porsi leftover per hari.

### ASLAP — Checklist Harian
- **Akses:** `/aslap` → tab "Checklist"
- **Cara:** Centang tiap item daily ops (kebersihan dapur, suhu kulkas, dll) → Submit
- **Hasil:** Checklist tersave, dipakai laporan mingguan
- **Endpoint:** `POST /api/aslap/checklists/submit`
- **Test data:** Checklist all-pass tiap hari.

### Log Kualitas Air
- **Akses:** `/aslap` → tab "Water"
- **Cara:** Input pH + TDS + sumber (kran_dapur/galon/dll) → Save
- **Hasil:** Data tersimpan, alert kalo out-of-spec (pH <6.5 atau >8.5, TDS >500)
- **Endpoint:** `POST /api/aslap/water-quality`
- **Test data:** pH 7.2, TDS 180.

### Observasi Produksi
- **Akses:** `/aslap` → tab "Obs"
- **Cara:** Kategori (kebersihan/suhu/SOP) + severity (low/med/high) + deskripsi → Save
- **Hasil:** Catatan produksi, masuk laporan mingguan
- **Endpoint:** `POST /api/aslap/observations`

### Komunikasi Sekolah
- **Akses:** `/aslap` → tab "Communication"
- **Cara:** Pilih sekolah + channel (WA/telp/visit) + summary → Save
- **Hasil:** History komunikasi guru sekolah
- **Endpoint:** `POST /api/aslap/comm-logs`

### Generate Laporan Mingguan
- **Akses:** `/aslap` → tab "Reports" → "Generate Laporan"
- **Cara:** Pilih week → Generate → preview → Submit (kirim ke Kepala SPPG)
- **Hasil:** Draft report PDF-ready, status `pending_signoff`
- **Endpoint:** `POST /api/aslap/reports/generate`

### Permintaan Khusus Siswa (Capture)
- **Akses:** `/menu-approval` → tab "Permintaan Khusus" → "Tambah"
- **Cara:** Pilih sekolah + kelas + nama + request_text (alergi/halal/dll) → Save
- **Hasil:** Request `open`, notif ke Ahli Gizi
- **Endpoint:** `POST /api/student-requests`

---

## 🍳 HEAD_KITCHEN / Kepala Chef

### Mulai Batch Produksi
- **Akses:** `/production`
- **Cara:**
  1. Klik "Mulai Batch" → pilih menu approved hari ini
  2. Set target_porsi
  3. (Opsional) klik "Dry Run" buat preview stock yang akan terpakai
  4. "Start Batch"
- **Hasil:** Batch `started`, timer 4-6 jam SOP mulai. Stock auto-debit FIFO.
- **Endpoint:** `POST /api/production/batches`
- **Test data:** 1 batch ended (5 porsi) per hari.

### QR Scan Container
- **Akses:** Tablet kitchen (mobile-optimized) — `/scan`
- **Cara:**
  1. Buka kamera → scan QR `BHN-XXXXX` di container
  2. Pilih step (Receiving/Processing/Packing/Delivery)
- **Hasil:** Stock auto-update, audit trail per scan
- **Endpoint:** `POST /api/scans`

### Akhiri Batch
- **Akses:** `/production` → batch aktif → "End Batch"
- **Cara:** Klik → confirm
- **Hasil:** Batch `ended`. Kirim ke QC (Ahli Gizi).
- **Endpoint:** `POST /api/production/batches/{id}/end`

### Edit Item Master
- **Akses:** `/items` (kalau ada perm `items.edit`)
- **Cara:** CRUD bahan master
- **Endpoint:** `PUT /api/items/{id}`

---

## 🏫 PUBLIC (guru sekolah, TANPA LOGIN)

### Konfirmasi Terima Makanan
- **Akses:** Buka link `http://localhost:5173/countdown/<tray_id>` (dari QR/SMS/WA)
- **Cara:** 
  1. Halaman publik tanpa login
  2. Input: nama guru + jumlah ompreng diterima + notes
  3. Submit
- **Hasil:** Delivery → `received`. Masuk dashboard agregat distribusi.
- **Endpoint:** `POST /api/countdown/{tray_id}/confirm-receipt` (no auth)

---

# Constants Per Hari

Semua data operasional di-tag tanggal hari ini (`DATE_TAG = today`):

| Field | Value |
|---|---|
| Menu name | `Sandbox Menu YYYY-MM-DD — Nasi Ayam Bayam` |
| PO notes | `Sandbox PO YYYY-MM-DD` |
| Inspection notes | `Sandbox inspection YYYY-MM-DD` |
| Expense desc | `Sandbox PLN YYYY-MM-DD`, `Sandbox transport YYYY-MM-DD` |
| Volunteer date | `YYYY-MM-DD` |
| Leftover date | `YYYY-MM-DD` (4 porsi, reason=absent) |

Re-run hari berikutnya → set baru muncul, set lama tetap (history). Bagus buat test trend chart, LRA biweekly, weekly report.

---

# Quick Test Scenarios

## Scenario 1: Sehari Penuh sebagai Kepala SPPG
1. Login → Dashboard
2. `/menu-approval` → liat menu pending → Approve
3. `/inspections` → buka inspection → tab Quality → TTD → Finalize
4. `/finance` → tab LRA → review draft → Sign-off
5. `/aslap` → tab Reports → review weekly → Sign-off
6. `/executive` → cek KPI hari ini

## Scenario 2: Verifikasi Audit Compliance
1. Login → `/executive`
2. Klik "Compliance Bundle Export" → download ZIP
3. Cek: ada LRA, sample retention, sign-offs, ASLAP report

## Scenario 3: Public Confirm-Receipt
1. Bukan login dulu. Buka tab incognito.
2. Cari tray_id dari `/distributions` (login dulu sebagai admin, ambil tray ID, lalu buka public link)
3. Buka `http://localhost:5173/countdown/<tray_id>`
4. Submit confirmation → cek di dashboard distributions ada update

---

# Troubleshooting

| Problem | Fix |
|---|---|
| Login lambat (>20s) | Wajar — audit log ke remote Supabase. Tunggu sampai selesai. |
| "Bahan kurang" saat start batch | Re-run seeder → inspection baru accept semua line → stock penuh. |
| Frontend ga reload | Hard refresh (Ctrl+Shift+R) — service worker kadang stuck. |
| Port 8001/5173 in use | Kill process Python/Node lama dulu. |
| Re-seed error "duplicate key" | Sudah idempotent — kalau tetap error, `--wipe` lalu re-seed. |
