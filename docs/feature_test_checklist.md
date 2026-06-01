# DPMBG — Checklist Test Fitur (Non-Teknis)

> Login: `admin / admin123` di http://localhost:5173
> Role: platform_admin (bisa lihat semua fitur)

---

## 1. Login

| # | Test | Cara |
|---|------|------|
| 1.1 | Form login tampil | Buka app, pastikan ada field Username, Password, tombol Login |
| 1.2 | Salah password | Isi username "admin", password "salah123", klik Login. Harus muncul pesan error merah |
| 1.3 | Login berhasil | Isi "admin" / "admin123", klik Login. Harus redirect ke Dashboard |
| 1.4 | Logout | Klik "Logout" di sidebar bawah. Harus kembali ke halaman Login |

---

## 2. Dashboard

| # | Test | Cara |
|---|------|------|
| 2.1 | 4 KPI card tampil | Setelah login, lihat 4 kotak atas: ITEMS RECEIVED, ITEMS PROCESSED, TRAYS PACKED, TRAYS DELIVERED |
| 2.2 | Pipeline Funnel | Scroll ke bawah, harus ada 4 kotak warna (Received > Processed > Packed > Delivered) |
| 2.3 | Chart & grafik | Pastikan ada: Item Processing Rate, Tray Fill Rate, Avg Durations, Hourly Scan Activity |
| 2.4 | Delivery per sekolah | Scroll bawah, tabel "Delivery Status per School" tampil |
| 2.5 | Export Daily | Klik tombol biru "Export Daily" di kanan atas. Harus generate file/feedback |
| 2.6 | Export Range | Klik "Export Range", pilih tanggal dari-sampai, cek response |
| 2.7 | Date picker | Ganti tanggal di kanan atas, data harus refresh |

---

## 3. Executive Dashboard

| # | Test | Cara |
|---|------|------|
| 3.1 | 3 tab tampil | Klik "Executive" di sidebar. Harus ada 3 tab: Per Dapur, Multi-SPPG (Yayasan), Platform (Cross-Org) |
| 3.2 | Per Dapur | Klik tab "Per Dapur". Harus ada 8 stat card + Compliance score + Trend chart |
| 3.3 | Multi-SPPG | Klik tab "Multi-SPPG". Ada ranking (Best Compliance, Lowest Cost, Highest Defect) + tabel perbandingan |
| 3.4 | Platform | Klik "Platform (Cross-Org)". Ada 5 stat card + tabel organisasi |
| 3.5 | Export BGN | Klik tombol hijau "Export BGN Compliance Bundle". Harus minta date range lalu download |

---

## 4. Menu Planner

| # | Test | Cara |
|---|------|------|
| 4.1 | Halaman tampil | Klik "Menu Planner" di sidebar. Harus ada tabel makanan, parameter, tombol Scrape |
| 4.2 | Scrape harga | Klik "Scrape 50 Item". Progress bar jalan. Tunggu selesai |
| 4.3 | Cari makanan | Ketik nama bahan di kolom search tabel makanan, misal "nasi". Tabel filter otomatis |
| 4.4 | Atur parameter | Set Jumlah hari, Budget Min/Maks. Tambah kelompok umur via tombol + |
| 4.5 | Optimasi | Klik "Optimasi Menu". Tunggu hasil, harus muncul card per hari + nutrisi + biaya |
| 4.6 | Substitusi | Di hasil, klik "Sub" di salah satu bahan. Harus muncul popover pilihan pengganti |
| 4.7 | Simpan menu | Klik "Simpan Menu", beri nama, klik Save. Harus tersimpan |
| 4.8 | Buka tersimpan | Klik "Buka Tersimpan", pilih menu dari library. Klik Load, pastikan ter-load |

---

## 5. Build Menu Manual

| # | Test | Cara |
|---|------|------|
| 5.1 | Halaman tampil | Klik "Build Manual" di sidebar. Ada panel kiri (search bahan) dan panel kanan (analisis gizi) |
| 5.2 | Cari & tambah bahan | Ketik "ayam" di search box, klik bahan dari hasil. Bahan masuk ke daftar |
| 5.3 | Atur gram | Ubah jumlah gram di bahan yang dipilih. Panel kanan harus update otomatis (nutrisi + biaya) |
| 5.4 | Lihat AKG | Panel kanan menunjukkan pil warna per nutrisi (hijau = aman, merah = kurang/lebih) |
| 5.5 | Simpan Draft | Isi nama menu + target tanggal, klik "Simpan Draft" |
| 5.6 | Submit Review | Klik "Simpan & Submit untuk Review". Menu pindah ke tab "Nunggu Review" di Approval |

---

## 6. Approval Menu

| # | Test | Cara |
|---|------|------|
| 6.1 | 7 tab status | Klik "Approval Menu". Pastikan ada tab: Nunggu Review, Draft, Disetujui, Terkunci, Ditolak, Arsip, Semua |
| 6.2 | Approve | Di tab "Nunggu Review", klik tombol Approve di salah satu menu. Isi catatan, submit. Menu pindah ke "Disetujui" |
| 6.3 | Reject | Di tab "Nunggu Review", klik Reject. Isi alasan. Menu pindah ke "Ditolak" |
| 6.4 | Lock | Di tab "Disetujui", klik Lock. Menu pindah ke "Terkunci" (siap produksi) |
| 6.5 | Revisi | Di tab "Ditolak", klik Revisi. Menu kembali ke "Draft" untuk diedit ulang |
| 6.6 | Forecast Bahan | Scroll ke bawah, pilih range tanggal, klik "Hitung". Tabel forecast (bahan, total gram, biaya) muncul |

---

## 7. Nutrisi Harian

| # | Test | Cara |
|---|------|------|
| 7.1 | Laporan Harian | Klik "Nutrisi Harian". Tab pertama = Laporan Harian. Tabel per sekolah: energi, protein, lemak, karbo + AKG% |
| 7.2 | Ganti tanggal | Ubah tanggal, data refresh |
| 7.3 | AKG Tracker | Klik tab "AKG Tracker Mingguan". Grid 7 hari x sekolah, warna: hijau (>=90%), kuning (70-89%), merah (<70%) |
| 7.4 | Klik cell | Klik salah satu kotak di grid. Tooltip muncul: detail nutrisi + top 5 sekolah |
| 7.5 | Navigasi minggu | Klik Prev/Next week. Grid ganti minggu |

---

## 8. Purchase Orders

| # | Test | Cara |
|---|------|------|
| 8.1 | 7 tab status | Klik "Purchase Orders". Ada tab: Semua, draft, sent, partial, received, closed, cancelled |
| 8.2 | Buat PO baru | Klik "+ PO Baru". Pilih supplier, tanggal kirim, tambah line item (bahan, berat, harga/kg). Klik Simpan |
| 8.3 | Tambah line | Di form PO, klik "Tambah Line" untuk nambah bahan lain. Total estimate update otomatis |
| 8.4 | Kirim PO | Di tab "draft", klik "Kirim" di PO yang baru dibuat. Status pindah ke "sent" |
| 8.5 | Lihat detail | Klik "Detail" di PO manapun. Modal muncul: info header + tabel line items |
| 8.6 | Hapus draft | Di tab "draft", klik "Hapus" di PO. Konfirmasi, PO terhapus |

---

## 9. Joint Inspection

| # | Test | Cara |
|---|------|------|
| 9.1 | 6 tab status | Klik "Joint Inspection". Tab: inspecting, pending, accepted, partial, rejected, Semua |
| 9.2 | Mulai inspeksi | Klik "+ Mulai Inspeksi". Pilih PO (status "sent"), isi catatan, klik Mulai |
| 9.3 | Buka detail | Klik "Buka" di inspeksi yang baru dibuat. Modal detail tampil |
| 9.4 | 3 sign-off | Di modal detail, ada 3 kolom sign-off: Kualitas (Ahli Gizi), Kuantitas (Akuntan), Fisik (ASLAP). Klik Approve/Reject per kolom |
| 9.5 | Accept bahan | Di tabel line items, klik Accept. Isi jumlah kontainer + berat aktual |
| 9.6 | Reject bahan | Klik Reject di bahan. Isi alasan + severity |
| 9.7 | Finalize | Setelah semua di-review, klik "Finalize" di bawah. Status pindah ke accepted/partial/rejected |

---

## 10. Receiving (Quick)

| # | Test | Cara |
|---|------|------|
| 10.1 | Mode Bahan Masuk | Klik "Receiving (Quick)". Mode default = "Bahan Masuk". Isi Nama, Berat, Unit, centang QC checklist, klik Submit |
| 10.2 | Test Print | Klik "Test Print" untuk print label barcode (jika printer terhubung) |
| 10.3 | Daftar bahan | Scroll ke bawah, tabel "Daftar Bahan Diterima" tampil. Search by nama, filter by tanggal |
| 10.4 | Edit bahan | Klik Edit di salah satu bahan. Modal edit muncul, ubah data, simpan |
| 10.5 | Hapus bahan | Klik Hapus, konfirmasi. Bahan terhapus dari tabel |
| 10.6 | Mode Defect | Switch ke mode "Defect / Reject". Pilih sumber (dari BHN existing / reject sebelum cetak) |
| 10.7 | Catat defect | Isi alasan defect, upload foto (opsional), klik Submit |
| 10.8 | Lihat foto | Di tabel Defect, klik "Lihat" di kolom Foto. Gambar tampil di modal |

---

## 11. Production

| # | Test | Cara |
|---|------|------|
| 11.1 | Halaman tampil | Klik "Production". Ada 3 section: Menu Approved Hari Ini, Batch Aktif, Tablet Scan |
| 11.2 | Mulai batch | Di "Menu Approved Hari Ini", klik "Confirm & Mulai Produksi" di salah satu menu. Preview dry-run muncul, konfirmasi |
| 11.3 | Lihat batch aktif | Tabel batch: ID, Menu, Porsi, Status, Timer. Timer berjalan (warna merah jika >6 jam = SOP breach) |
| 11.4 | QC approve | Klik "QC OK" di batch yang sedang berjalan. Isi sample location + notes |
| 11.5 | Selesai batch | Klik "Selesai" di batch. Konfirmasi, batch selesai |
| 11.6 | Detail batch | Klik "Detail". Modal: consumed items, food samples |
| 11.7 | Scan QR | Klik tombol "Scan" di section Tablet Scan. Scanner aktif, scan QR code item |

---

## 12. Distribusi

| # | Test | Cara |
|---|------|------|
| 12.1 | 4 tab tampil | Klik "Distribusi". Tab: Aggregate Hari Ini, Wave 1 & 2, Sisa Porsi, Vehicle & Driver |
| 12.2 | Aggregate | Tab pertama: 4 stat card (Target, Dispatched, Confirmed, Scans) + tabel per sekolah |
| 12.3 | Wave classifier | Klik "Wave 1 & 2". 2 card: Wave 1 (PAUD/TK/SD) dan Wave 2 (SMP). Masing-masing list sekolah + jumlah siswa |
| 12.4 | Catat sisa porsi | Klik tab "Sisa Porsi", lalu "+ Catat Sisa Porsi". Pilih sekolah, qty, kategori (return/extra/disposal), catatan |
| 12.5 | Vehicle & Driver | Klik tab terakhir. Ada daftar kendaraan + driver. Klik "+ Tambah" untuk menambah |
| 12.6 | Status per sekolah | Di tab Aggregate, cek kolom Status: Lengkap (centang hijau), Sebagian (~), Belum (—) |

---

## 13. ASLAP — Operasi Harian

| # | Test | Cara |
|---|------|------|
| 13.1 | 5 tab tampil | Klik "ASLAP Daily". Tab: Checklist Hari Ini, Water Quality, Production Obs, Komunikasi Sekolah, Weekly Report |
| 13.2 | Isi checklist | Tab "Checklist Hari Ini": list item checklist, klik OK/NO per item. Klik "Submit" atau "Save Draft" |
| 13.3 | Tes air | Tab "Water Quality", klik "+ Tes Air Sekarang". Isi TDS, pH, bau, warna. Submit. Auto-alert jika di luar ambang |
| 13.4 | Observasi produksi | Tab "Production Obs", klik "+ Catat Observasi". Isi batch, suhu, waktu, kebersihan, catatan |
| 13.5 | Komunikasi sekolah | Tab "Komunikasi Sekolah", klik "+ Catat Komunikasi". Pilih sekolah, channel (WA/telepon/visit), topik, response |
| 13.6 | Laporan mingguan | Tab "Weekly Report", klik "+ Generate Laporan Mingguan". Summary grid 4 kotak muncul |
| 13.7 | Submit laporan | Di weekly report, klik "Submit ke Yayasan". Status berubah jadi "submitted" |

---

## 14. Scan Errors

| # | Test | Cara |
|---|------|------|
| 14.1 | Tabel error | Klik "Scan Errors" di sidebar. Tabel: ID, Code, Step, Reason, Time |
| 14.2 | Navigasi halaman | Jika banyak data, cek pagination berfungsi |

---

## 15. Variance Report

| # | Test | Cara |
|---|------|------|
| 15.1 | Halaman tampil | Klik "Variance Report". Judul "Laporan Variance & Waste" |
| 15.2 | Pilih range | Set tanggal dari-sampai, klik Refresh. 4 summary card tampil + 2 waste % card |
| 15.3 | Warna indikator | Waste %: hijau (0%), kuning (<10%), merah (>=10%) |
| 15.4 | Tabel harian | Scroll ke bawah, tabel detail per hari: Diterima > Diproses > Packed > Dikirim |
| 15.5 | Export Excel | Klik link "Export Excel" (muncul setelah data ter-load) |

---

## 16. Akuntan Finance

| # | Test | Cara |
|---|------|------|
| 16.1 | 6 tab tampil | Klik "Akuntan Finance". Tab: Cost-per-porsi, Price Trends, Spike Alerts, Expense, LRA Biweekly, PO Generator |
| 16.2 | Cost-per-porsi | Tab pertama: pilih date range, klik Update. 4 stat card + breakdown tabel per kategori |
| 16.3 | Price Trends | Tab kedua: tabel bahan + harga sekarang vs 7 hari lalu + perubahan WoW % |
| 16.4 | Spike Alerts | Tab ketiga: tabel bahan yang harganya naik di atas threshold |
| 16.5 | Tambah Expense | Tab "Expense", klik "+ Expense". Isi kategori, jumlah (Rp), tanggal, catatan. Submit |
| 16.6 | Honor Relawan | Klik "+ Honor Relawan". Isi nama, tanggal, jumlah |
| 16.7 | Generate LRA | Tab "LRA Biweekly", klik "+ Generate LRA Periode Baru". Isi periode + revenue |
| 16.8 | Submit LRA | Klik "Submit ke BGN" di LRA yang sudah generated. Status berubah |
| 16.9 | PO Generator | Tab terakhir: klik "Generate PO". Pilih date range + supplier. PO otomatis terbuat dari forecast |

---

## 17. Master Sekolah Binaan

| # | Test | Cara |
|---|------|------|
| 17.1 | Tabel sekolah | Klik "Sekolah" di sidebar group MASTER DATA. Tabel daftar sekolah binaan |
| 17.2 | Tambah sekolah | Klik "+ Tambah Sekolah". Isi data (nama, alamat, jumlah siswa, dll). Simpan |
| 17.3 | Non-aktif | Centang "Tampilkan non-aktif" untuk lihat sekolah yang dinonaktifkan |

---

## 18. Master Supplier

| # | Test | Cara |
|---|------|------|
| 18.1 | Tabel supplier | Klik "Supplier". Daftar supplier aktif tampil |
| 18.2 | Tambah supplier | Klik "+ Tambah Supplier". Isi nama, kontak, alamat. Simpan |
| 18.3 | Non-aktif | Centang "Tampilkan non-aktif" untuk lihat supplier non-aktif |

---

## 19. Users

| # | Test | Cara |
|---|------|------|
| 19.1 | Tabel user | Klik "Users" di sidebar group ADMIN DAPUR. Tabel: ID, USERNAME, ROLE, KITCHENS |
| 19.2 | Tambah user | Klik "+ New user". Isi username, password, pilih role, assign kitchen. Simpan |

---

## 20. Kitchens

| # | Test | Cara |
|---|------|------|
| 20.1 | Tabel kitchen | Klik "Kitchens". Tabel: ID, Slug, Name, Printer, Lang, Active |
| 20.2 | Tambah kitchen | Klik "+ New kitchen". Isi slug, name, label title, timezone, printer settings. Simpan |
| 20.3 | Edit | Klik Edit. Ubah data, simpan |
| 20.4 | Rotate keys | Di edit modal, klik "Rotate" di Scanner Key atau Cloud Print Key |
| 20.5 | Deactivate | Klik "Deactivate" di kitchen yang aktif |

---

## 21. All Kitchens (Overview)

| # | Test | Cara |
|---|------|------|
| 21.1 | Overview | Klik "All Kitchens". Lihat summary: total kitchens, received, processed, packed, delivered |
| 21.2 | Tabel kitchen | Tabel per kitchen: nama, slug, stats, errors (merah jika >0), status (active/silent) |
| 21.3 | Chart 7 hari | Grafik stacked bar 7 hari terakhir per kitchen |
| 21.4 | Ganti tanggal | Ubah date picker, data refresh |

---

## 22. Organizations (Platform Admin)

| # | Test | Cara |
|---|------|------|
| 22.1 | Tabel organisasi | Klik "Organizations" di sidebar group PLATFORM. Daftar organisasi tampil |

---

## 23. Notifikasi (Bell)

| # | Test | Cara |
|---|------|------|
| 23.1 | Badge count | Lihat ikon Bell di kiri atas sidebar, angka merah = jumlah notif belum dibaca |
| 23.2 | Buka panel | Klik ikon Bell. Panel notifikasi tampil |
| 23.3 | Tandai dibaca | Klik notifikasi untuk tandai sudah dibaca. Badge count berkurang |

---

## 24. Fitur Tambahan

| # | Test | Cara |
|---|------|------|
| 24.1 | Dark mode | Klik "Dark mode" di sidebar bawah. Tampilan berubah gelap |
| 24.2 | Switch kitchen | Klik dropdown kitchen di sidebar (misal "DPMBG Paseh"). Ganti ke kitchen lain jika ada |
| 24.3 | Responsive sidebar | Sidebar menunjukkan group nama: MENU & GIZI, PENERIMAAN BAHAN, PRODUKSI & DISTRIBUSI, LAPANGAN & MONITORING, KEUANGAN, MASTER DATA, ADMIN DAPUR, PLATFORM |

---

## Role Access Matrix

| Fitur | platform_admin | superadmin | head_sppg | nutritionist | accountant | aslap | head_kitchen |
|-------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Dashboard | Y | Y | Y | Y | Y | Y | Y |
| Executive | Y | Y | Y | - | - | - | - |
| Menu Planner | Y | Y | Y | Y | - | - | - |
| Build Manual | Y | Y | Y | Y | - | - | Y |
| Approval Menu | Y | Y | Y | Y | - | - | - |
| Nutrisi Harian | Y | Y | Y | Y | - | - | - |
| Purchase Orders | Y | Y | Y | - | Y | - | - |
| Joint Inspection | Y | Y | Y | Y | Y | Y | Y |
| Receiving (Quick) | Y | Y | Y | - | - | - | Y |
| Production | Y | Y | Y | - | - | - | Y |
| Distribusi | Y | Y | Y | - | - | Y | Y |
| ASLAP Daily | Y | Y | Y | - | - | Y | - |
| Scan Errors | Y | Y | Y | - | - | Y | Y |
| Variance Report | Y | Y | Y | - | Y | - | - |
| Akuntan Finance | Y | Y | Y | - | Y | - | - |
| Master Sekolah | Y | Y | Y | - | - | - | - |
| Master Supplier | Y | Y | Y | - | - | - | - |
| Users | Y | Y | - | - | - | - | - |
| Kitchens | Y | Y | - | - | - | - | - |
| All Kitchens | Y | Y | - | - | - | - | - |
| Organizations | Y | - | - | - | - | - | - |
