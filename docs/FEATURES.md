# DPMBG — Daftar Fitur per Role

Sistem manajemen dapur sekolah multi-tenant (MBG). Akses fitur diatur per-role
lewat Role Access Matrix. Hierarki tenant:

```
platform_admin → superadmin (org) → head_sppg → (nutritionist / accountant / aslap / head_kitchen) per dapur
```

7 role: `platform_admin`, `superadmin`, `head_sppg`, `nutritionist`, `accountant`, `aslap`, `head_kitchen`.

---

## 🔵 platform_admin — Pemilik platform (21 fitur)

Akses **semua** fitur superadmin di bawah, **plus**:

| Fitur | Deskripsi |
|---|---|
| Organizations | Kelola multi-organisasi (SPPG/Yayasan/PT) lintas platform |

---

## 🟣 superadmin — Admin organisasi (20 fitur)

| Fitur | Deskripsi |
|---|---|
| Dashboard | KPI harian, pipeline funnel, chart produksi, export |
| Executive | Dashboard eksekutif 3 tab (per dapur, multi-SPPG, platform) + export BGN |
| Menu Planner | Optimizer menu otomatis: scrape harga, budget, AKG, substitusi bahan |
| Build Manual | Susun menu manual, analisis gizi real-time, submit review |
| Approval Menu | Alur approve/reject/lock menu (7 status) + forecast bahan |
| Nutrisi Harian | Laporan nutrisi per sekolah + AKG tracker mingguan |
| Purchase Orders | Buat & kelola PO ke supplier (multi-line, kirim, detail) |
| Joint Inspection | Inspeksi bahan masuk dengan 3 sign-off |
| Receiving (Quick) | Terima bahan + QC checklist, print barcode, catat defect |
| Production | Mulai batch produksi, timer SOP, QC, food sample, scan QR |
| Distribusi | Aggregate distribusi, wave classifier, sisa porsi, kendaraan/driver |
| ASLAP Daily | Operasi harian lapangan: checklist, tes air, observasi, weekly report |
| Scan Errors | Log error scan QR di tiap tahap |
| Variance Report | Laporan variance & waste (diterima→dikirim) + export Excel |
| Akuntan Finance | Cost-per-porsi, price trends, expense, LRA, PO generator |
| Master Sekolah | Master data sekolah binaan (CRUD) |
| Master Supplier | Master data supplier (CRUD) |
| Users | Kelola user, role, assign ke dapur |
| Kitchens | Kelola dapur, rotate key scanner/printer, deactivate |
| All Kitchens | Overview lintas dapur + chart 7 hari |

❌ tidak ke: Organizations

---

## 🟢 head_sppg — Kepala SPPG (17 fitur)

| Fitur | Deskripsi |
|---|---|
| Dashboard | KPI harian, pipeline funnel, chart produksi, export |
| Executive | Dashboard eksekutif 3 tab + export BGN compliance |
| Menu Planner | Optimizer menu otomatis (scrape harga, budget, AKG) |
| Build Manual | Susun menu manual + analisis gizi real-time |
| Approval Menu | Approve/reject/lock menu + forecast bahan |
| Nutrisi Harian | Laporan nutrisi per sekolah + AKG tracker |
| Purchase Orders | Buat & kelola PO ke supplier |
| Joint Inspection | Inspeksi bahan masuk dengan 3 sign-off |
| Receiving (Quick) | Terima bahan + QC, barcode, defect |
| Production | Batch produksi, timer SOP, QC, scan QR |
| Distribusi | Aggregate, wave, sisa porsi, kendaraan |
| ASLAP Daily | Operasi harian lapangan |
| Scan Errors | Log error scan |
| Variance Report | Laporan variance & waste |
| Akuntan Finance | Keuangan: cost-per-porsi, trends, LRA |
| Master Sekolah | Master data sekolah binaan |
| Master Supplier | Master data supplier |

❌ tidak ke: Users, Kitchens, All Kitchens, Organizations

---

## 🍎 nutritionist / ahli_gizi — Ahli Gizi (6 fitur)

| Fitur | Deskripsi |
|---|---|
| Dashboard | KPI harian & pipeline produksi |
| Menu Planner | Optimizer menu otomatis (budget + AKG + substitusi) |
| Build Manual | Susun menu manual, analisis gizi real-time |
| Approval Menu | Ajukan & kelola status menu |
| Nutrisi Harian | Laporan nutrisi per sekolah + AKG tracker mingguan |
| Joint Inspection | Sign-off **Kualitas** bahan masuk |

---

## 💰 accountant / akuntan — Akuntan (5 fitur)

| Fitur | Deskripsi |
|---|---|
| Dashboard | KPI harian & pipeline produksi |
| Purchase Orders | Buat & kelola PO ke supplier |
| Joint Inspection | Sign-off **Kuantitas** bahan masuk |
| Variance Report | Laporan variance & waste + export Excel |
| Akuntan Finance | Cost-per-porsi, price trends, expense, LRA, PO generator |

---

## 🛡️ aslap — Asisten Lapangan (5 fitur)

| Fitur | Deskripsi |
|---|---|
| Dashboard | KPI harian & pipeline produksi |
| Joint Inspection | Sign-off **Fisik** bahan masuk |
| Distribusi | Aggregate, wave, sisa porsi, kendaraan/driver |
| ASLAP Daily | Checklist harian, tes air, observasi, komunikasi sekolah, weekly report |
| Scan Errors | Log error scan QR |

---

## 👨‍🍳 head_kitchen / kepala dapur — Operasional dapur (7 fitur)

| Fitur | Deskripsi |
|---|---|
| Dashboard | KPI harian & pipeline produksi |
| Build Manual | Susun menu manual + analisis gizi |
| Joint Inspection | Inspeksi bahan masuk |
| Receiving (Quick) | Terima bahan + QC, print barcode, catat defect |
| Production | Mulai batch produksi, timer SOP, QC, scan QR |
| Distribusi | Aggregate distribusi, wave, sisa porsi |
| Scan Errors | Log error scan QR |
