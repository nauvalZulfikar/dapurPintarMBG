# Test Checklist — Fitur Terbaru DPMBG

Manual test guide untuk fitur Wave 1 + Wave 2. Setup: backend di `http://127.0.0.1:8001`, frontend di `http://localhost:5173`. Login awal pakai `admin` / `admin123` (platform_admin) untuk bikin user testing per role.

> **Format tiap fitur**: **Tujuan** (kenapa dites) → **Langkah** (klik apa) → **Expected** (apa yang harus kelihatan) → **Negative case** (apa yg ga boleh terjadi).

---

## 0. Setup (1× di awal)

- [ ] Backend hidup → buka http://127.0.0.1:8001/health harus `200`
- [ ] Frontend hidup → buka http://localhost:5173 tampil halaman login
- [ ] Login `admin`/`admin123` berhasil → redirect ke Dashboard
- [ ] Sidebar lengkap: Dashboard, Receiving, Menu Planner, Scan Errors, **Variance Report**, Admin (All Kitchens / Kitchens / Users), Platform (Organizations)
- [ ] Di `/admin/users` bikin 3 user testing via tombol **+ New user**:
  - `test_admin` / pw: `test1234` / Kitchen staff → DPMBG Paseh / role **Admin**
  - `test_gizi` / pw: `test1234` / Kitchen staff → DPMBG Paseh / role **Ahli Gizi**
  - `test_acc` / pw: `test1234` / Kitchen staff → DPMBG Paseh / role **Accountant**

---

## 1. Login flow (baseline)

**Tujuan**: Pastikan multi-role login ga regressi.

- [ ] Logout → login `test_admin` / `test1234` → sukses masuk Dashboard
- [ ] Logout → login `test_gizi` / `test1234` → sukses masuk Dashboard
- [ ] Logout → login `test_acc` / `test1234` → sukses masuk Dashboard
- [ ] Login dengan password salah → banner **"Invalid username or password"**
- [ ] Username benar, org ada 2 account nama sama → sistem perlu `org_slug` (kalau belum pernah terjadi, skip)
- [ ] Dark mode toggle (tombol `☾ Dark mode` di sidebar footer) — teks semua halaman tetap kebaca

---

## 2. Create User form (F0 — merged + dark mode + loading state)

**Tujuan**: Form bikin user 1-step harus: (a) reactive toggle dapur/role, (b) teks kebaca di dark mode, (c) ada feedback loading saat submit.

### 2a. Toggle behavior
- [ ] Login `admin` → `/admin/users` → klik **+ New user**
- [ ] Default **Access level = Kitchen staff** → muncul dropdown Kitchen + Role
- [ ] Pilih **Superadmin** → dropdown Kitchen + Role **hilang**
- [ ] Balik pilih Kitchen staff → dropdown muncul lagi

### 2b. Dark mode readability
- [ ] Toggle Dark mode (sidebar footer) — form tetap terbuka
- [ ] Ketik username → teks **putih** di background gelap (bukan abu-abu samar)
- [ ] Ketik password → dot (•••) terlihat jelas
- [ ] Dropdown Access level / Kitchen / Role in this kitchen — label options kebaca
- [ ] Balik ke Light mode — teks hitam di background putih

### 2c. Loading state saat Create
- [ ] Isi form lengkap (Kitchen staff + Paseh + Ahli Gizi)
- [ ] Klik **Create user**
- [ ] **Expected**: tombol berubah jadi "○ Creating…" (spinner + disabled), sebelah kiri muncul **"○ Membuat user..."**, seluruh fieldset form berubah opacity 60% (ga bisa diubah)
- [ ] Setelah ~1-3 detik (tergantung latency Supabase), form tertutup + tabel refresh + user baru muncul
- [ ] Double-click Create user saat masih loading → tidak membuat dobel entry (karena `if (saving) return` guard)

### 2d. Validation
- [ ] Kitchen staff tanpa pilih Kitchen → klik Create → error **"Pick a kitchen for this user, or promote them to superadmin."**
- [ ] Username kosong / password kosong → tombol tidak melakukan apa-apa (silent skip)
- [ ] Username yang sudah ada di org yang sama → error **"Username already exists in this organization"**

---

## 3. Kitchen Admin — scoped management (Wave 1 / F1)

**Tujuan**: Per-kitchen admin dapat mengelola dapur dan staff-nya sendiri, tapi tidak bisa menyentuh dapur/user lain atau melakukan aksi destructive.

**Login**: `test_admin`

### 3a. Sidebar scoping
- [ ] Sidebar tampil menu **Kitchens** & **Users** (tadinya hanya superadmin)
- [ ] **Tidak** tampil "All Kitchens" (superadmin only)
- [ ] **Tidak** tampil section "Platform"
- [ ] Tampil **Variance Report** (karena role admin juga punya reports.variance)

### 3b. /admin/kitchens — lihat hanya dapur sendiri
- [ ] Buka `/admin/kitchens` → tabel **hanya 1 row** `DPMBG Paseh`
- [ ] Di API langsung (DevTools → Network → `/api/admin/kitchens`) → response `kitchens.length === 1`
- [ ] Klik **Edit** di row → modal terbuka dengan semua field kecuali Slug (disabled)

### 3c. Edit kitchen label + rotate keys
- [ ] Di modal edit, ubah **Label title** → `UAT Test Label` → klik Save → sukses, tabel refresh
- [ ] Refresh page → label masih `UAT Test Label` (ter-persist)
- [ ] Kembalikan label ke semula (`MBG Kitchen` atau yg asli)
- [ ] Scroll modal → lihat **Scanner key** + **Cloud print key** dengan tombol **Rotate** di kanan label
- [ ] Klik **Rotate** Scanner key → confirm dialog → OK → field auto-isi key baru (±32 char random)
- [ ] Klik **Rotate** Cloud print key → confirm → key baru
- [ ] Tutup modal → refresh page → buka edit lagi → key sudah yang baru (ter-persist)

### 3d. Negative: destructive ops blocked
- [ ] Uncheck **Active** checkbox → klik Save → error **"Only superadmin can change kitchen active status"**
- [ ] Tidak ada tombol **Deactivate** pada baris tabel (hanya tampil untuk superadmin)

### 3e. /admin/users — scoped
- [ ] Buka `/admin/users` → tabel hanya user yang assigned ke DPMBG Paseh (+ dirinya sendiri)
- [ ] Tidak tampil user dari org lain (di realistic 2-org scenario)

### 3f. Invite sub-staff
- [ ] Klik **+ New user** → bikin `test_invited` role **Ahli Gizi** kitchen Paseh → sukses
- [ ] User baru muncul di tabel dengan badge `ahli_gizi`

### 3g. Reset password
- [ ] Di row `test_invited`, klik **Reset pw** → modal prompt → masukkan password baru ≥6 char → alert **"Password updated"**
- [ ] Logout → login `test_invited` pakai password baru → berhasil

### 3h. Negative: role changes / delete / kitchen-admin promotion
- [ ] Klik **Role** → masukkan `superadmin` → error **"Only superadmin can change user's global role"**
- [ ] Klik **Delete** → error **403** di toast/banner (kitchen admin tidak bisa delete)
- [ ] Di row `test_invited`, dropdown kitchen → pilih Paseh → role **Admin** → Add → error **"Only superadmin can grant kitchen-admin role"**
- [ ] Ganti ke **Ahli Gizi** atau **Accountant** → Add → sukses

**Cleanup 3**: login `admin` → hapus `test_invited` dari `/admin/users`.

---

## 4. Accountant — Manual Price Override (Wave 1 / F2a)

**Tujuan**: Accountant bisa ganti harga hasil scrape dengan harga invoice asli, tanpa menunggu rescrape.

**Login**: `test_acc`

### 4a. Tombol edit tampil hanya untuk accountant/admin
- [ ] Buka `/menu-planner` → scroll ke tabel "Daftar Bahan Makanan TKPI"
- [ ] Klik **Tampilkan Tabel** kalau belum auto-load
- [ ] Kolom **Harga/100g** tiap row punya 2 mini-button: **hist** dan **edit**
- [ ] Login `test_gizi` (ahli_gizi) → buka menu planner → **tidak ada** tombol edit / hist pada kolom harga

### 4b. Edit harga inline
- [ ] Login `test_acc` → klik **edit** pada row BERAS → muncul input numeric + save/x
- [ ] Isi `15000` → tekan **Enter** → row refresh, harga jadi `Rp 15.000` (format Indonesia)
- [ ] Klik **edit** lagi → tekan **Esc** → batal, kembali ke tampilan display
- [ ] Klik **edit** → kosongkan input → **save** → override cleared, harga kembali ke harga scrape asli
- [ ] Coba isi `-500` → alert **"Harga harus angka >= 0"**
- [ ] Coba isi huruf (`abc`) → alert atau input tidak accept (type=number)

### 4c. Override diterapkan ke optimizer
- [ ] Set harga BERAS = `99999` (sengaja ekstrim)
- [ ] Scroll ke atas, isi form Optimize (group SD, 100 students) → klik **Optimize**
- [ ] Expected: hasil menu cost-per-serving naik signifikan karena BERAS jadi mahal
- [ ] Kembalikan override (klik edit → kosongkan → save)

### 4d. Manual override persisten lintas session
- [ ] Set harga BERAS = `20000`
- [ ] Logout → login ulang `test_acc` → buka menu planner → harga BERAS tetap `Rp 20.000`
- [ ] Kolom source mungkin menunjukkan `manual_source`: "manual override"
- [ ] Clear override untuk bersih-bersih

---

## 5. Price History (Wave 2 / F4)

**Tujuan**: Accountant dapat melihat jejak semua perubahan harga (audit trail).

**Login**: `test_acc`

### 5a. Auto-log setiap override
- [ ] Di menu planner, klik **edit** pada row BERAS → isi `10000` → save
- [ ] Klik **edit** lagi → isi `12000` → save
- [ ] Klik **edit** lagi → kosongkan → save (clear)
- [ ] Klik **hist** pada row BERAS → modal **"Riwayat Harga"** terbuka
- [ ] Expected tabel berisi **3 entri** terbaru di paling atas:
  | Waktu | Source | Harga |
  |---|---|---|
  | baru saja | `manual_clear` (abu-abu) | — |
  | baru saja | `manual` (amber) | Rp 12.000 |
  | baru saja | `manual` (amber) | Rp 10.000 |

### 5b. UI behavior
- [ ] Klik tombol **×** atau klik area gelap → modal tertutup
- [ ] Buka hist untuk food yang belum pernah diubah → tabel kosong atau pesan **"Belum ada perubahan harga yang tercatat."**

### 5c. Negative: role boundary
- [ ] Login `test_gizi` → menu planner → tombol **hist** tidak muncul
- [ ] Akses langsung `GET /api/menu/prices/BERAS/history` via DevTools Console:
  ```js
  fetch('/api/menu/prices/BERAS/history', { headers: { Authorization: 'Bearer ' + localStorage.token } }).then(r => r.status)
  ```
  → `403`
- [ ] Login `test_admin` → hist tersedia (admin union)

---

## 6. Variance / Waste Report (Wave 2 / F5)

**Tujuan**: Accountant dapat melihat % waste antara items diterima → diproses → packed → dikirim, per hari + summary.

**Login**: `test_acc`

### 6a. Akses halaman
- [ ] Sidebar tampil **📉 Variance Report**
- [ ] Klik → halaman terbuka, default range **30 hari ke belakang**
- [ ] Header **"Laporan Variance & Waste"**
- [ ] 4 kartu summary: Items Diterima / Diproses / Packed / Dikirim (angka + sub label)
- [ ] 2 kartu waste: Processing waste + Delivery waste (warna **hijau** jika 0%, **amber** jika <10%, **merah** jika ≥10%)
- [ ] Tabel per-hari: Tanggal / Diterima / Diproses / % / Packed / Dikirim / %

### 6b. Filter tanggal
- [ ] Ubah From → `2026-04-01`, To → `2026-04-10` → klik **Refresh** → tabel update (10 baris max)
- [ ] Tombol **Export Excel** tersedia, klik → download `laporan_paseh_2026-04-01_to_2026-04-10.xlsx`
- [ ] Buka Excel → sheet Ringkasan dengan tabel 10 hari + baris TOTAL di bawah

### 6c. Validation
- [ ] Ubah From jadi > To (misal From=2026-05-01, To=2026-04-01) → Refresh → banner merah **"'from' must be <= 'to'"**
- [ ] Range > 1 tahun → error **"Range cannot exceed 366 days"**

### 6d. Negative: role boundary
- [ ] Login `test_gizi` → sidebar **tidak tampil** Variance Report
- [ ] Ketik URL `/reports/variance` langsung → redirect ke `/` (PermissionRoute)
- [ ] API langsung: `GET /api/reports/variance?from=...&to=...` → `403`
- [ ] Login `test_admin` → akses oke

### 6e. Data accuracy sanity check
- [ ] Pilih range yang pasti punya data (mis. 30 hari terakhir)
- [ ] Summary `received` = jumlah row di tabel `items` untuk range & kitchen tsb (cross-check via DevTools `fetch('/api/items?page_size=500').then(...)` atau via DB langsung)
- [ ] `delivered` ≤ `packed` ≤ expected (kalau > packed = bug data)
- [ ] Waste % = (received - processed) / received × 100

---

## 7. Food Nutrition Override (Wave 2 / F3)

**Tujuan**: Ahli gizi dapat mengoreksi nilai nutrisi TKPI default per-dapur (karena bahan supplier tiap dapur bisa beda sedikit), dan perubahan diterapkan ke optimizer.

**Login**: `test_gizi`

### 7a. Pencil ✎ tampil di kolom Energi & Protein
- [ ] Buka `/menu-planner` → tabel bahan makanan → pencil **✎** tampil pojok kanan setiap angka Energi + Protein
- [ ] Login `test_acc` → **tidak ada** pencil (accountant tidak punya `foods.edit`)
- [ ] Login `test_admin` → pencil tampil (admin punya `foods.edit`)

### 7b. Edit inline
- [ ] Login `test_gizi`
- [ ] Cari row BERAS → klik ✎ di kolom Energi → input muncul dengan nilai current
- [ ] Ubah ke `145` → **Enter** → row refresh, angka jadi `145`
- [ ] **Indicator titik amber ●** muncul di sebelah nama "Beras" (tanda ada override)
- [ ] Klik ✎ di Protein row BERAS → ubah ke `8.5` → Enter → update

### 7c. Override diterapkan ke optimizer
- [ ] Set energy BERAS = `500` (ekstrim biar kelihatan impact)
- [ ] Scroll ke form Optimize → Optimize → hasil menu + rata-rata nutrisi muncul
- [ ] Cek avg_nutrition energy — kalau BERAS masuk menu, average energy naik
- [ ] Kembalikan override via API (karena UI belum ada clear button untuk nutrition):
  ```js
  fetch('/api/menu/foods/BERAS/override', { method: 'DELETE', headers: { Authorization: 'Bearer ' + localStorage.token } }).then(r => r.status)
  ```
  → `200`, indicator ● hilang setelah refresh

### 7d. Validation & whitelist
- [ ] Coba input angka negatif (`-5`) → alert `"Angka >= 0"`
- [ ] Via API coba kirim key aneh `{"overrides": {"evil_key": 1, "energy": 100}}`:
  ```js
  fetch('/api/menu/foods/BERAS/override', {
    method: 'PATCH',
    headers: { 'Authorization': 'Bearer ' + localStorage.token, 'Content-Type': 'application/json' },
    body: JSON.stringify({ overrides: { evil_key: 999, energy: 200 } })
  }).then(r => r.json())
  ```
  → response `overrides: {energy: 200}` (evil_key drop, hanya whitelisted yang disimpan)
- [ ] Body tanpa key valid → 400 **"No valid override fields..."**

### 7e. Negative: role boundary
- [ ] `test_acc` klik PATCH override via API → `403`
- [ ] `test_gizi` `/menu/foods/overrides` → `200` list override milik kitchen-nya

---

## 8. Platform admin sanity (ga regressi)

**Login**: `admin` (platform_admin)

- [ ] Semua sidebar items muncul termasuk **Organizations**, **All Kitchens**
- [ ] `/admin/overview` → cross-kitchen metrics (hanya berarti kalau org punya >1 dapur aktif)
- [ ] `/admin/organizations` → bisa CRUD org
- [ ] Akses semua fitur Wave 1 + Wave 2 (admin tier = union of all perms)
- [ ] Dapat menyentuh kitchen dari org LAIN (cross-org access)

---

## 9. Dark mode — halaman baru

**Tujuan**: semua halaman baru/modal yang ditambah Wave 1 + Wave 2 kebaca di dark mode.

Toggle Dark mode, buka satu per satu:

- [ ] `/menu-planner` — tabel bahan makanan (nama, angka, badge kategori, tombol edit/hist/✎), form optimize, hasil chart
- [ ] `/reports/variance` — summary cards, waste pct (warna otomatis), tabel per-hari
- [ ] `/admin/kitchens` edit modal — field label, scanner key row, rotate buttons
- [ ] `/admin/users` — tabel utama, form **+ New user** (username/password inputs, semua dropdown)
- [ ] Price history modal drawer — header, tabel Waktu/Source/Harga, badge source
- [ ] Kembali ke Light mode — semua tetap kebaca (tidak terlalu pucat)

---

## 10. Edge cases & error states

- [ ] Backend mati saat UI terbuka (stop uvicorn) → request gagal → banner merah muncul, app tidak crash, reload setelah backend balik → recover
- [ ] Token expired (edit `localStorage.token` jadi invalid → refresh) → redirect ke `/login`
- [ ] Akses URL tanpa permission (role=ahli_gizi → `/admin/users`) → redirect `/`
- [ ] Refresh saat di `/reports/variance` → data re-load, range tetap (karena dari date picker state, bukan URL)
- [ ] Logout → seluruh localStorage cleared (`token`, `active_kitchen_id`)

---

## 11. Cleanup akhir

- [ ] Login `admin` → `/admin/users` → hapus semua user test: `test_admin`, `test_gizi`, `test_acc`, `test_invited` (kalau masih ada)
- [ ] (Opsional) Bersihin override + history buat fresh state:
  ```sql
  DELETE FROM food_nutrition_overrides WHERE kitchen_id = 1;
  DELETE FROM food_prices_history      WHERE kitchen_id = 1 AND source LIKE 'manual%';
  UPDATE food_prices SET manual_price=NULL, manual_source=NULL, manual_set_by=NULL, manual_set_at=NULL
  WHERE kitchen_id = 1;
  ```

---

## 12. Laporan Nutrisi Harian (Ahli Gizi Feature Pack)

**Tujuan**: Ahli gizi dapat melihat total nutrisi terdelivery per hari, per sekolah, dan membanding dengan target AKG.

**Login**: `test_gizi`

### 12a. Akses halaman & date picker
- [ ] Sidebar tampil **🥗 Nutrisi** (atau sejenisnya)
- [ ] Klik → halaman `/nutrition` terbuka, default date hari ini
- [ ] Form date picker tersedia di atas tabel, bisa ubah ke tanggal lain
- [ ] Ubah ke tanggal sebelumnya (misal 3 hari lalu) → klik **Refresh** → tabel update (kalau ada data)

### 12b. Tabel nutrisi per sekolah
- [ ] Kolom: Sekolah / Energi (kcal) / % AKG / Protein (g) / % AKG / Lemak (g) / % AKG / Karbo (g) / % AKG
- [ ] Tiap row = 1 sekolah yang menerima tray pada tanggal itu
- [ ] Baris TOTAL di bawah = sum semua sekolah
- [ ] Angka % AKG = (actual / target) × 100%, warna: hijau ≥90%, amber 70-89%, merah <70%

### 12c. Tanpa data
- [ ] Ubah ke tanggal yang pasti tidak ada delivery (misal 1 Januari 2020) → tabel kosong atau pesan **"Tidak ada data"**

### 12d. Negative: role boundary
- [ ] Login `test_acc` → sidebar tidak tampil Nutrisi
- [ ] Ketik `/nutrition` langsung → redirect ke `/`
- [ ] API: `GET /api/nutrition/daily?date=2026-04-25` → `403`
- [ ] Login `test_admin` → akses oke (admin = super)

---

## 13. AKG Compliance Tracker (Ahli Gizi Feature Pack)

**Tujuan**: Ahli gizi dapat melihat 7-day calendar dengan status kepatuhan nutrisi per hari.

**Login**: `test_gizi`

### 13a. Akses halaman & week navigation
- [ ] Sidebar tampil **📅 AKG Tracker** (atau sejenisnya)
- [ ] Klik → halaman terbuka, default minggu ini
- [ ] Header tampil: "Minggu [start] — [end]"
- [ ] Tombol **< Minggu Sebelumnya** dan **Minggu Depan >**

### 13b. Color-coded cells
- [ ] 7 cell untuk Mon–Sun
- [ ] Tiap cell warna:
  - **Hijau**: ≥90% AKG met untuk semua 4 nutrisi (rata-rata all schools)
  - **Amber**: 70–89%
  - **Merah**: <70% atau tidak ada data
- [ ] Tiap cell menampilkan tanggal + "% AKG" (angka)

### 13c. Hover/popover detail
- [ ] Hover atau klik cell → popover menampilkan per-school breakdown untuk hari itu
  - School name / Energy % AKG / Protein % AKG / Fat % AKG / Carbs % AKG
- [ ] Klik area gelap → popover tutup

### 13d. Week navigation
- [ ] Klik **Minggu Sebelumnya** → calendar update untuk minggu lalu (7 hari sebelumnya)
- [ ] Data akurat (cross-check dengan `/nutrition` page di tanggal-tanggal itu)
- [ ] Klik **Minggu Depan** → bisa navigate ke future, tampil "Tidak ada data" (kalau belum ada delivery)

### 13e. Negative: role boundary
- [ ] Login `test_acc` → sidebar tidak tampil AKG Tracker
- [ ] Ketik `/akg-tracker` langsung → redirect ke `/`
- [ ] API: `GET /api/nutrition/weekly-compliance?week_start=2026-04-21` → `403`

---

## 14. Simpan Menu (Ahli Gizi Feature Pack)

**Tujuan**: Ahli gizi dapat save optimizer result ke personal library, dan load/delete dengan mudah.

**Login**: `test_gizi`

### 14a. Save button & dialog
- [ ] Buka `/menu-planner` → isi form Optimize (misal 7 hari, SD 100 siswa) → klik **Optimize**
- [ ] Result muncul (chart + tabel) → tombol **💾 Simpan Menu** muncul
- [ ] Klik **Simpan Menu** → dialog prompt nama menu
- [ ] Isi `Menu Minggu 1 - April` → klik **Simpan**
- [ ] Toast sukses: **"Menu saved!"**

### 14b. Menu library page
- [ ] Sidebar tampil **📚 Simpan Menu** atau di halaman menu planner sendiri ada tab **Library**
- [ ] Klik → halaman `/menu/saved` (atau modal/drawer) terbuka
- [ ] Tabel: Nama / Tanggal / Pembuat / Action (load/delete)
- [ ] Minimal 1 row untuk menu yang baru disimpan: `Menu Minggu 1 - April / [today] / test_gizi / [load] [delete]`

### 14c. Load menu
- [ ] Di library, klik tombol **Muat** pada row menu yang disimpan
- [ ] Expected: navigate ke menu planner form, semua field pre-filled:
  - Num days (dari saved payload)
  - Groups + quantities
  - Budget
  - Excluded foods
  - Constraints
- [ ] Bisa klik **Optimize** lagi untuk refresh result dengan nilai yang sama

### 14d. Delete menu
- [ ] Di library, klik **Hapus** pada row menu → confirm dialog **"Yakin hapus menu ini?"**
- [ ] Klik **OK** → menu dihapus dari tabel, toast **"Menu deleted"**
- [ ] Refresh page → menu tidak ada

### 14e. Multi save & isolation
- [ ] Save menu kedua: `Menu Backup` → library update dengan 2 rows
- [ ] Login `test_acc` → `/menu/saved` → **403** atau redirect (accountant tidak punya `menu.save`)
- [ ] Login `test_admin` → `/menu/saved` → akses oke, bisa lihat & manage (admin = super)

### 14f. Negative: role boundary
- [ ] Login `test_acc` → menu planner tidak tampil **Simpan Menu** button
- [ ] API: `POST /api/menu/saved` dengan nama + payload → `403`
- [ ] API: `DELETE /api/menu/saved/{id}` → `403`

---

## 15. Substitusi Bahan (Ahli Gizi Feature Pack)

**Tujuan**: Ahli gizi dapat melihat daftar substitute bahan dengan similarity score, dan swap inline di hasil optimizer.

**Login**: `test_gizi`

### 15a. Sub button di hasil optimizer
- [ ] Buka `/menu-planner` → optimize → result tampil tabel per-day foods
- [ ] Tiap row makanan punya tombol **Sub** (atau icon 🔄)
- [ ] Hover → tooltip **"Substitusi Bahan"**
- [ ] Login `test_acc` → tombol **Sub** tetap ada (accountant punya `menu.view`)
- [ ] Login `test_admin` → tombol ada

### 15b. Substitution popover
- [ ] Klik **Sub** pada row BERAS (misal) → popover terbuka
- [ ] Header: **"Substitusi untuk: Beras"**
- [ ] Tabel candidate: Nama Bahan / Similarity / Action (swap)
- [ ] Top 5 hasil, sorted by similarity score descending, 2 decimal place (misal `0.95`, `0.87`, `0.76`, ...)
- [ ] Prefer same `food_category` (protein vs protein, atau carb vs carb); fallback to cross-category jika kurang 5

### 15c. Swap action
- [ ] Klik **Swap** pada 1 candidate (misal "Nasi Putih" dengan sim=0.93) → popover close, tabel row BERAS berubah jadi "Nasi Putih"
- [ ] Hanya UI change (ephemeral), tidak save ke DB
- [ ] Bisa swap lagi di row baru sesuai kebutuhan

### 15d. User dapat swap multiple
- [ ] Di row lain (misal AYAM) → klik Sub → swap ke candidate yang berbeda
- [ ] Semua substitution hanya di memory; jika **reload** tanpa **Simpan Menu**, hilang
- [ ] Klik **Simpan Menu** → save hasil final dengan substitusi yang sudah di-swap

### 15e. Negative: role boundary & boundary test
- [ ] User tanpa `menu.view` tidak bisa akses → tidak ada Sub button
- [ ] API: `GET /api/menu/substitutes?food_name=BERAS` dengan user tanpa `menu.view` → `403`
- [ ] Backend filter: hanya sama kategori top 5, atau cross-kategori fallback — cross-check via API response

---

## Automated tests (verify otomatis, tidak manual)

Jalankan dari `D:\Downloads\coding project\DPMBG_Project`:

```bash
set PYTHONPATH=. && set PYTHONIOENCODING=utf-8
python backend/scripts/test_wave1.py            # 27 checks F1 + F2
python backend/scripts/test_wave2.py            # 24 checks F3 + F4 + F5
python backend/scripts/test_roles.py            # 27 checks permission matrix
python backend/scripts/test_isolation.py        # 22 checks multi-kitchen isolation
python backend/scripts/test_two_orgs_realistic.py  # 34 checks 2-org scenario
python backend/scripts/browser_wave1_test.py    # 3 UI hooks (playwright)
python backend/scripts/browser_wave2_test.py    # 5 UI hooks (playwright)
python backend/scripts/browser_newuser_form_test.py  # contrast probe + loading spinner
```

Expected: semua **[DONE]** / `===== PASSED =====`, no red `[FAIL]` lines.
