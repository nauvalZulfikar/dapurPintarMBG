"""Idempotent migration to multi-kitchen schema.

Run once after pulling the multi-kitchen refactor. Safe to re-run.

What it does:
  1. Creates `kitchens` table and seeds kitchen id=1 ("paseh") using values
     from the existing single-tenant .env (PRINTER_NAME, SCANNER_KEY,
     CLOUD_PRINT_KEY, LABEL_TITLE, TZ_REGION).
  2. Creates `user_kitchens` M2M table.
  3. Ensures every domain table has an Integer kitchen_id column.
     For items & trays the previous column was VARCHAR — we drop/recast.
  4. Backfills kitchen_id = 1 on every row where it is NULL.
  5. Adds indexes on kitchen_id for query perf.
  6. Adds a composite unique (tray_id, kitchen_id) on trays and tray_items;
     drops the old single-column unique index on tray_id if present.
  7. Replaces food_prices unique (food_code) with (food_code, kitchen_id).
  8. Assigns every existing user to kitchen 1 as "kitchen_admin".

Usage:
    python -m backend.scripts.migrate_multi_kitchen
"""
from __future__ import annotations

import os
import secrets
from sqlalchemy import text

from backend.core.database import engine, remote_metadata, REMOTE_DB_URL


DEFAULT_KITCHEN_ID = 1


def _gen_key(n: int = 24) -> str:
    return secrets.token_urlsafe(n)


def _exec(sql: str, **params):
    with engine.begin() as c:
        c.execute(text(sql), params)


def _scalar(sql: str, **params):
    with engine.connect() as c:
        return c.execute(text(sql), params).scalar()


def _column_type(table: str, column: str) -> str | None:
    return _scalar(
        """
        SELECT data_type FROM information_schema.columns
        WHERE table_name = :t AND column_name = :c
        """,
        t=table, c=column,
    )


def _has_column(table: str, column: str) -> bool:
    return _column_type(table, column) is not None


def _has_index(name: str) -> bool:
    return bool(_scalar(
        "SELECT 1 FROM pg_indexes WHERE indexname = :n",
        n=name,
    ))


def _has_constraint(name: str) -> bool:
    return bool(_scalar(
        "SELECT 1 FROM pg_constraint WHERE conname = :n",
        n=name,
    ))


# ── Step 1: create kitchens table + seed default ────────────────────────────

def create_kitchens_table():
    print("[1/8] Creating kitchens table...")
    _exec("""
        CREATE TABLE IF NOT EXISTS kitchens (
            id              SERIAL PRIMARY KEY,
            slug            VARCHAR(50) NOT NULL UNIQUE,
            name            VARCHAR(100) NOT NULL,
            printer_name    VARCHAR(100),
            printer_lang    VARCHAR(10) DEFAULT 'ZPL',
            label_title     VARCHAR(100) DEFAULT 'MBG Kitchen',
            scanner_key     VARCHAR(64) NOT NULL UNIQUE,
            cloud_print_key VARCHAR(64) NOT NULL UNIQUE,
            address         TEXT,
            timezone        VARCHAR(50) DEFAULT 'Asia/Jakarta',
            active          BOOLEAN DEFAULT TRUE,
            created_at      TIMESTAMP DEFAULT NOW()
        )
    """)

    exists = _scalar("SELECT 1 FROM kitchens WHERE id = :id", id=DEFAULT_KITCHEN_ID)
    if exists:
        print("      kitchen id=1 already present — skipping seed")
        return

    _exec(
        """
        INSERT INTO kitchens (
            id, slug, name, printer_name, printer_lang, label_title,
            scanner_key, cloud_print_key, timezone, active
        ) VALUES (
            :id, :slug, :name, :printer_name, :printer_lang, :label_title,
            :scanner_key, :cloud_print_key, :tz, TRUE
        )
        """,
        id=DEFAULT_KITCHEN_ID,
        slug="paseh",
        name="DPMBG Paseh",
        printer_name=os.getenv("PRINTER_NAME") or None,
        printer_lang=os.getenv("PRINTER_LANG", "ZPL"),
        label_title=os.getenv("LABEL_TITLE", "MBG Kitchen"),
        scanner_key=os.getenv("SCANNER_KEY") or _gen_key(),
        cloud_print_key=os.getenv("CLOUD_PRINT_KEY") or _gen_key(),
        tz=os.getenv("TZ_REGION", "Asia/Jakarta"),
    )
    # reset the SERIAL so future inserts continue after seeded id
    _exec("SELECT setval('kitchens_id_seq', GREATEST(COALESCE(MAX(id), 0), :min)) FROM kitchens",
          min=DEFAULT_KITCHEN_ID)
    print(f"      seeded kitchen id={DEFAULT_KITCHEN_ID} (slug=paseh)")


# ── Step 2: user_kitchens M2M ───────────────────────────────────────────────

def create_user_kitchens():
    print("[2/8] Creating user_kitchens table...")
    _exec("""
        CREATE TABLE IF NOT EXISTS user_kitchens (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kitchen_id INTEGER NOT NULL REFERENCES kitchens(id) ON DELETE CASCADE,
            role       VARCHAR(20) DEFAULT 'staff',
            created_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_user_kitchen UNIQUE (user_id, kitchen_id)
        )
    """)
    _exec("CREATE INDEX IF NOT EXISTS ix_user_kitchens_user    ON user_kitchens(user_id)")
    _exec("CREATE INDEX IF NOT EXISTS ix_user_kitchens_kitchen ON user_kitchens(kitchen_id)")


# ── Step 3: normalize kitchen_id columns on domain tables ──────────────────

DOMAIN_TABLES = ("items", "trays", "tray_items", "scan_errors", "print_jobs", "food_prices")


def ensure_kitchen_id_columns():
    print("[3/8] Normalizing kitchen_id columns to INTEGER...")
    for table in DOMAIN_TABLES:
        # Ensure the parent table exists. If not (e.g. migration ran on a
        # fresh DB before any rows were written), skip — SQLAlchemy's
        # init_remote_db on app startup will create it with the right type.
        if not _scalar("SELECT 1 FROM information_schema.tables WHERE table_name = :t", t=table):
            print(f"      skip {table} (table not present yet)")
            continue

        col_type = _column_type(table, "kitchen_id")
        if col_type is None:
            _exec(f"ALTER TABLE {table} ADD COLUMN kitchen_id INTEGER")
            print(f"      + {table}.kitchen_id (integer)")
        elif col_type != "integer":
            # existing VARCHAR column — drop and re-add as integer.
            # This wipes the prior value, which is fine because values were
            # never populated in the single-tenant era.
            _exec(f"ALTER TABLE {table} DROP COLUMN kitchen_id")
            _exec(f"ALTER TABLE {table} ADD COLUMN kitchen_id INTEGER")
            print(f"      ~ {table}.kitchen_id recast {col_type} → integer")
        else:
            print(f"      = {table}.kitchen_id already integer")

        # FK + index
        fk_name = f"fk_{table}_kitchen"
        if not _has_constraint(fk_name):
            _exec(f"""
                ALTER TABLE {table}
                ADD CONSTRAINT {fk_name}
                FOREIGN KEY (kitchen_id) REFERENCES kitchens(id)
            """)
        idx_name = f"ix_{table}_kitchen_id"
        if not _has_index(idx_name):
            _exec(f"CREATE INDEX {idx_name} ON {table}(kitchen_id)")


# ── Step 4: backfill kitchen_id = 1 on existing rows ────────────────────────

def backfill_kitchen_id():
    print("[4/8] Backfilling kitchen_id = 1 on existing rows...")
    for table in DOMAIN_TABLES:
        if not _has_column(table, "kitchen_id"):
            continue
        with engine.begin() as c:
            res = c.execute(
                text(f"UPDATE {table} SET kitchen_id = :id WHERE kitchen_id IS NULL"),
                {"id": DEFAULT_KITCHEN_ID},
            )
            print(f"      {table}: {res.rowcount} rows updated")


# ── Step 5: trays uniqueness moves to (tray_id, kitchen_id) ────────────────

def fix_trays_uniqueness():
    print("[5/8] Moving trays/tray_items unique to (tray_id, kitchen_id)...")
    # drop any single-column unique on tray_id for each table
    for table in ("trays", "tray_items"):
        rows = []
        with engine.connect() as c:
            rows = c.execute(text("""
                SELECT c.conname
                FROM   pg_constraint c
                JOIN   pg_class      t ON t.oid = c.conrelid
                JOIN   pg_attribute  a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
                WHERE  t.relname = :t
                  AND  c.contype = 'u'
                GROUP BY c.conname, c.conkey
                HAVING array_agg(a.attname::text ORDER BY a.attnum) = ARRAY['tray_id']::text[]
            """), {"t": table}).fetchall()
        for r in rows:
            cname = r[0]
            _exec(f'ALTER TABLE {table} DROP CONSTRAINT "{cname}"')
            print(f"      dropped {table} unique: {cname}")

    for table, cname in (("trays", "uq_trays_tray_kitchen"), ("tray_items", "uq_tray_items_tray_kitchen")):
        if not _has_constraint(cname):
            _exec(f"ALTER TABLE {table} ADD CONSTRAINT {cname} UNIQUE (tray_id, kitchen_id)")
            print(f"      + {cname}")


# ── Step 6: food_prices unique (food_code) → (food_code, kitchen_id) ───────

def fix_food_prices_uniqueness():
    print("[6/8] Migrating food_prices unique to (food_code, kitchen_id)...")
    # drop any unique constraint whose only column is food_code
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT c.conname
            FROM   pg_constraint c
            JOIN   pg_class      t ON t.oid = c.conrelid
            JOIN   pg_attribute  a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
            WHERE  t.relname = 'food_prices'
              AND  c.contype = 'u'
            GROUP BY c.conname, c.conkey
            HAVING array_agg(a.attname::text ORDER BY a.attnum) = ARRAY['food_code']::text[]
        """)).fetchall()
    for r in rows:
        _exec(f'ALTER TABLE food_prices DROP CONSTRAINT "{r[0]}"')
        print(f"      dropped food_prices unique: {r[0]}")

    if not _has_constraint("uq_food_prices_code_kitchen"):
        _exec("ALTER TABLE food_prices ADD CONSTRAINT uq_food_prices_code_kitchen UNIQUE (food_code, kitchen_id)")
        print("      + uq_food_prices_code_kitchen")


# ── Step 7: promote / map existing users ────────────────────────────────────

def map_users_to_default_kitchen():
    print("[7/8] Mapping existing users to kitchen id=1 as kitchen_admin...")
    with engine.begin() as c:
        res = c.execute(text("""
            INSERT INTO user_kitchens (user_id, kitchen_id, role)
            SELECT u.id, :kid, 'kitchen_admin'
            FROM   users u
            WHERE  NOT EXISTS (
                SELECT 1 FROM user_kitchens uk
                WHERE  uk.user_id = u.id AND uk.kitchen_id = :kid
            )
        """), {"kid": DEFAULT_KITCHEN_ID})
        print(f"      mapped {res.rowcount} user(s) to kitchen 1")


# ── Step 8: verify ──────────────────────────────────────────────────────────

def verify():
    print("[8/8] Verification")
    with engine.connect() as c:
        kc = c.execute(text("SELECT COUNT(*) FROM kitchens")).scalar()
        uc = c.execute(text("SELECT COUNT(*) FROM users")).scalar()
        ukc = c.execute(text("SELECT COUNT(*) FROM user_kitchens")).scalar()
        print(f"      kitchens={kc}  users={uc}  user_kitchens={ukc}")
        for table in DOMAIN_TABLES:
            null_count = c.execute(text(f"SELECT COUNT(*) FROM {table} WHERE kitchen_id IS NULL")).scalar()
            print(f"      {table}: {null_count} rows with NULL kitchen_id")


def main():
    if not REMOTE_DB_URL:
        raise SystemExit("DATABASE_URL is not set — cannot migrate local SQLite with this script.")
    print(f"Connected to: {REMOTE_DB_URL.split('@')[-1]}")
    create_kitchens_table()
    create_user_kitchens()
    ensure_kitchen_id_columns()
    backfill_kitchen_id()
    fix_trays_uniqueness()
    fix_food_prices_uniqueness()
    map_users_to_default_kitchen()
    verify()
    print("Done.")


if __name__ == "__main__":
    main()
