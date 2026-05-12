"""Versioned schema migrations (Phase 0+).

Currently the project relies on `_online_migrate()` in `database.py` for
catch-all idempotent ALTER TABLE statements. This package is the placeholder
for future per-phase migration files when the project outgrows that approach.

Convention (when populated):
  001_initial.py
  002_kitchen_id_integrity.py
  003_audit_log_expansion.py
  ...

Each file exports `up()` and (when feasible) `down()` callables. The applied
state is tracked in the `schema_migrations` table via
`backend.core.database.db_record_migration()`.
"""
