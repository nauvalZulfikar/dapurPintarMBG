# Permission Matrix — DPMBG (Phase 0)

Single source of truth for the 7-role RBAC introduced in Babak 0.

## Role hierarchy

```
platform_admin                    ← LU (IT dev / vendor SaaS). Cross-org.
  └─ superadmin                   ← Yayasan owner. 1 org, multi-SPPG.
       └─ head_sppg               ← Kepala SPPG. Pimpinan 1 SPPG. Inherits admin.
            ├─ nutritionist       ← Ahli Gizi (BGN: Pengawas Gizi/Produksi)
            ├─ accountant         ← Akuntan (BGN: Pengawas Keuangan)
            ├─ aslap              ← Asisten Lapangan (field ops enforcer)
            └─ head_kitchen       ← Kepala Chef (production lead)
```

Cross-org = 2 roles (`platform_admin`, `superadmin`).
Per-kitchen = 5 canonical roles (above) + 2 backward-compat aliases.

## Backward-compat aliases

| Legacy role  | Canonical role  | Notes                                    |
|--------------|-----------------|------------------------------------------|
| `admin`      | `head_sppg`     | Same permission set; UI displays new label |
| `ahli_gizi`  | `nutritionist`  | Renamed for BGN terminology               |

Existing users keep working without re-assignment. Both identifiers accepted by `VALID_KITCHEN_ROLES`.

## Deprecated

| Role            | Status                                              |
|-----------------|-----------------------------------------------------|
| `kitchen_staff` | Legacy fallback from prototype. No active user. No new assignments. |

## Permission matrix (per-kitchen)

| Permission              | head_sppg | nutritionist | accountant | aslap | head_kitchen |
|-------------------------|-----------|--------------|------------|-------|--------------|
| `dashboard.view`        | ✅        | ✅           | ✅         | ✅    | ✅           |
| `items.view`            | ✅        | ✅           | ✅         | ✅    | ✅           |
| `items.create`          | ✅        |              |            | ✅    |              |
| `items.edit`            | ✅        |              |            |       | ✅           |
| `trays.view`            | ✅        | ✅           | ✅         | ✅    | ✅           |
| `menu.view`             | ✅        | ✅           | ✅         |       | ✅           |
| `menu.optimize`         | ✅        | ✅           |            |       |              |
| `menu.scrape`           | ✅        | ✅           |            |       |              |
| `menu.save`             | ✅        | ✅           |            |       |              |
| `foods.edit`            | ✅        | ✅           |            |       |              |
| `nutrition.report`      | ✅        | ✅           |            |       |              |
| `prices.override`       | ✅        |              | ✅         |       |              |
| `prices.history`        | ✅        |              | ✅         |       |              |
| `reports.variance`      | ✅        |              | ✅         | ✅    |              |
| `scan_errors.view`      | ✅        |              | ✅         | ✅    | ✅           |
| `export.daily`          | ✅        |              | ✅         |       |              |
| `export.range`          | ✅        |              | ✅         |       |              |
| `admin.kitchens`        | ✅        |              |            |       |              |
| `admin.users`           | ✅        |              |            |       |              |
| `school.view`           | ✅        | ✅           | ✅         | ✅    | ✅           |
| `school.manage`         | ✅        |              |            |       |              |
| `supplier.view`         | ✅        | ✅           | ✅         | ✅    |              |
| `supplier.manage`       | ✅        |              | ✅         |       |              |

`platform_admin` and `superadmin` (org-level) automatically receive **all** permissions for any kitchen they administer; they bypass the per-kitchen matrix.

## Future permissions (not yet implemented — added per phase)

These are placeholder identifiers. They'll be added to `ROLE_PERMS` as the corresponding endpoints land.

| Permission                       | Phase | Owners                                     |
|----------------------------------|-------|--------------------------------------------|
| `school.manage`                  | 1     | head_sppg                                  | ✅ shipped
| `supplier.manage`                | 1     | head_sppg, accountant                      | ✅ shipped
| `menu.calc`                      | 2     | head_sppg, nutritionist                    | ✅ shipped
| `menu.build_manual`              | 2     | nutritionist                               | ✅ shipped
| `menu.submit_for_review`         | 2     | nutritionist                               | ✅ shipped
| `menu.approve`                   | 2     | head_sppg                                  | ✅ shipped
| `menu.lock`                      | 2     | head_sppg                                  | ✅ shipped
| `menu.cycle_check`               | 2     | head_sppg, nutritionist, accountant        | ✅ shipped
| `menu.forecast`                  | 2     | head_sppg, nutritionist, accountant        | ✅ shipped
| `student_request.view`           | 2     | head_sppg, nutritionist, aslap             | ✅ shipped
| `student_request.create`         | 2     | nutritionist, aslap                        | ✅ shipped
| `student_request.resolve`        | 2     | head_sppg, nutritionist                    | ✅ shipped
| `po.view`                        | 3     | head_sppg, nutritionist, accountant, aslap | ✅ shipped
| `po.create`                      | 3     | head_sppg, accountant                      | ✅ shipped
| `po.edit`                        | 3     | head_sppg, accountant                      | ✅ shipped
| `po.delete`                      | 3     | head_sppg, accountant                      | ✅ shipped
| `inspection.view`                | 3     | head_sppg, nutritionist, accountant, aslap | ✅ shipped
| `inspection.create`              | 3     | head_sppg, accountant, aslap               | ✅ shipped
| `inspection.signoff_quality`     | 3     | head_sppg, nutritionist                    | ✅ shipped
| `inspection.signoff_quantity`    | 3     | head_sppg, accountant                      | ✅ shipped
| `inspection.signoff_physical`    | 3     | head_sppg, aslap                           | ✅ shipped
| `inspection.reject_bahan`        | 3     | head_sppg, nutritionist                    | ✅ shipped
| `inspection.finalize`            | 3     | head_sppg, aslap                           | ✅ shipped
| `container.split`                | 3     | head_sppg, aslap                           | ✅ shipped
| `dispute.view`                   | 3     | head_sppg, nutritionist, accountant, aslap | ✅ shipped
| `dispute.resolve`                | 3     | head_sppg, accountant                      | ✅ shipped
| `production.view`                | 4     | head_sppg, head_kitchen, nutritionist, aslap | ✅ shipped
| `production.start_batch`         | 4     | head_sppg, head_kitchen                    | ✅ shipped
| `production.end_batch`           | 4     | head_sppg, head_kitchen                    | ✅ shipped
| `production.processing_scan`     | 4     | head_sppg, head_kitchen                    | ✅ shipped (also gates JWT-auth on /api/scans Processing step) |
| `production.qc_approve`          | 4     | head_sppg, nutritionist                    | ✅ shipped
| `sample.view`                    | 4     | head_sppg, head_kitchen, nutritionist, aslap | ✅ shipped
| `sample.manage`                  | 4     | head_sppg, nutritionist                    | ✅ shipped
| `distribution.view`              | 5     | head_sppg, nutritionist, accountant, aslap | ✅ shipped
| `distribution.dispatch`          | 5     | head_sppg, aslap                           | ✅ shipped
| `distribution.leftover`          | 5     | head_sppg, aslap                           | ✅ shipped
| `distribution.confirm_receipt`   | 5     | (public — guru sekolah, no role required)  | ✅ shipped
| `vehicle.manage`                 | 5     | head_sppg, accountant                      | ✅ shipped
| `driver.manage`                  | 5     | head_sppg, accountant                      | ✅ shipped
| `finance.view`                   | 6     | head_sppg, accountant                      | ✅ shipped
| `finance.price_trends`           | 6     | head_sppg, accountant, nutritionist        | ✅ shipped
| `expense.view`                   | 6     | head_sppg, accountant                      | ✅ shipped
| `expense.create`                 | 6     | head_sppg, accountant                      | ✅ shipped
| `expense.edit`                   | 6     | head_sppg, accountant                      | ✅ shipped
| `volunteer.manage`               | 6     | head_sppg, accountant                      | ✅ shipped
| `lra.view`                       | 6     | head_sppg, accountant                      | ✅ shipped
| `lra.generate`                   | 6     | head_sppg, accountant                      | ✅ shipped
| `lra.signoff`                    | 6     | head_sppg                                  | ✅ shipped
| `checklist.view`                 | 7     | head_sppg, aslap                           | ✅ shipped
| `checklist.daily`                | 7     | aslap                                      | ✅ shipped
| `checklist.template_manage`      | 7     | head_sppg                                  | ✅ shipped
| `water_quality.view`             | 7     | head_sppg, aslap                           | ✅ shipped
| `water_quality.log`              | 7     | aslap                                      | ✅ shipped
| `production_observation.view`    | 7     | head_sppg, aslap                           | ✅ shipped
| `production_observation.create`  | 7     | aslap                                      | ✅ shipped
| `school_comm_log.view`           | 7     | head_sppg, aslap                           | ✅ shipped
| `school_comm_log.create`         | 7     | aslap                                      | ✅ shipped
| `aslap_report.view`              | 7     | head_sppg, aslap                           | ✅ shipped
| `aslap_report.generate`          | 7     | aslap                                      | ✅ shipped
| `aslap_report.signoff`           | 7     | head_sppg                                  | ✅ shipped
| `notification.view`              | 8     | all roles                                  | ✅ shipped
| `notification.subscribe`         | 8     | all roles                                  | ✅ shipped
| `executive.kpi_view`             | 9     | all roles                                  | ✅ shipped
| `compliance.bundle_export`       | 9     | head_sppg, accountant                      | ✅ shipped
| `menu.approve`                   | 2     | head_sppg                                  |
| `menu.submit_for_review`         | 2     | nutritionist                                |
| `menu.build_manual`              | 2     | nutritionist                                |
| `student_request.capture`        | 2     | nutritionist, aslap                         |
| `inspection.signoff_quality`     | 3     | nutritionist                                |
| `inspection.signoff_quantity`    | 3     | accountant                                  |
| `inspection.signoff_physical`    | 3     | aslap                                       |
| `inspection.reject_bahan`        | 3     | nutritionist                                |
| `container.split`                | 3     | aslap                                       |
| `production.start_batch`         | 4     | head_kitchen                                |
| `production.processing_scan`     | 4     | head_kitchen                                |
| `production.qc_approve`          | 4     | nutritionist                                |
| `sample.manage`                  | 4     | nutritionist                                |
| `distribution.dispatch`          | 5     | aslap                                       |
| `distribution.confirm_receipt`   | 5     | (public — guru sekolah, no role required)   |
| `po.create`                      | 6     | accountant                                  |
| `expense.create`                 | 6     | accountant                                  |
| `lra.generate`                   | 6     | accountant                                  |
| `lra.signoff`                    | 6     | head_sppg                                   |
| `checklist.daily`                | 7     | aslap                                       |
| `water_quality.log`              | 7     | aslap                                       |
| `notification.subscribe`         | 8     | all                                         |
| `executive.dashboard.view`       | 9     | head_sppg, superadmin, platform_admin       |
| `compliance.bundle.export`       | 9     | head_sppg, accountant                       |

## Design notes

- Permissions are strings, not enums — trivially serialisable to JSON for the UI.
- `platform_admin` / `superadmin` get `ALL_PERMS` short-circuit; per-kitchen lookup happens only for `users.role == "user"`.
- New permission ids should follow `<domain>.<action>` convention.
- When a phase adds a new endpoint, also: (a) add the permission id to the relevant role set, (b) extend the matrix table above, (c) add a test in `backend/scripts/test_roles.py` exercising allow + deny.
