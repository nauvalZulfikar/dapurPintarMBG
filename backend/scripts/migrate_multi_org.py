"""Idempotent migration: add multi-organization (entity) layer.

Sits on top of the existing multi-kitchen schema. What it does:
  1. Create `organizations` table; seed id=1 "dpmbg" (existing data belongs to DPMBG).
  2. Add `org_id` to `kitchens` and `users`.
  3. Backfill all existing rows to org_id=1.
  4. Replace `kitchens.slug` unique constraint with (org_id, slug).
  5. Replace `users.username` unique constraint with (org_id, username).
     Without this two orgs could not both have a user named "admin".
  6. Promote the single existing admin to `platform_admin` *only if* the user
     explicitly says so by running with `--promote-admin`; otherwise leave role
     alone (existing "admin" role still behaves as superadmin via legacy
     handling in auth.py).

Usage:
    python -m backend.scripts.migrate_multi_org
    python -m backend.scripts.migrate_multi_org --promote-admin
"""
from __future__ import annotations

import sys
from sqlalchemy import text

from backend.core.database import engine, REMOTE_DB_URL

DEFAULT_ORG_ID = 1


def _exec(sql: str, **params):
    with engine.begin() as c:
        c.execute(text(sql), params)


def _scalar(sql: str, **params):
    with engine.connect() as c:
        return c.execute(text(sql), params).scalar()


def _has_constraint(name: str) -> bool:
    return bool(_scalar("SELECT 1 FROM pg_constraint WHERE conname = :n", n=name))


def _has_column(table: str, column: str) -> bool:
    return bool(_scalar(
        "SELECT 1 FROM information_schema.columns WHERE table_name=:t AND column_name=:c",
        t=table, c=column,
    ))


# ── Step 1: organizations table + seed ─────────────────────────────────────

def create_orgs_table():
    print("[1/5] Creating organizations table...")
    _exec("""
        CREATE TABLE IF NOT EXISTS organizations (
            id         SERIAL PRIMARY KEY,
            slug       VARCHAR(50)  NOT NULL UNIQUE,
            name       VARCHAR(150) NOT NULL,
            active     BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    exists = _scalar("SELECT 1 FROM organizations WHERE id = :id", id=DEFAULT_ORG_ID)
    if exists:
        print("      org id=1 already present — skipping seed")
        return
    _exec(
        "INSERT INTO organizations (id, slug, name) VALUES (:id, :slug, :name)",
        id=DEFAULT_ORG_ID, slug="dpmbg", name="DPMBG",
    )
    _exec(
        "SELECT setval('organizations_id_seq', GREATEST(COALESCE(MAX(id), 0), :min)) FROM organizations",
        min=DEFAULT_ORG_ID,
    )
    print(f"      seeded org id={DEFAULT_ORG_ID} (slug=dpmbg)")


# ── Step 2: org_id columns + FK + index ────────────────────────────────────

def add_org_id_columns():
    print("[2/5] Adding org_id to kitchens & users...")
    for table in ("kitchens", "users"):
        if not _has_column(table, "org_id"):
            _exec(f"ALTER TABLE {table} ADD COLUMN org_id INTEGER")
            print(f"      + {table}.org_id")
        else:
            print(f"      = {table}.org_id already present")

        fk_name = f"fk_{table}_org"
        if not _has_constraint(fk_name):
            _exec(f"""
                ALTER TABLE {table}
                ADD CONSTRAINT {fk_name}
                FOREIGN KEY (org_id) REFERENCES organizations(id)
            """)
        idx_name = f"ix_{table}_org_id"
        _exec(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}(org_id)")


# ── Step 3: backfill ───────────────────────────────────────────────────────

def backfill_org():
    print("[3/5] Backfilling org_id = 1 on kitchens & users...")
    for table in ("kitchens", "users"):
        with engine.begin() as c:
            res = c.execute(
                text(f"UPDATE {table} SET org_id = :id WHERE org_id IS NULL"),
                {"id": DEFAULT_ORG_ID},
            )
            print(f"      {table}: {res.rowcount} rows updated")


# ── Step 4: kitchens.slug becomes unique per org ───────────────────────────

def fix_kitchens_slug_uniqueness():
    print("[4/5] Moving kitchens.slug unique to (org_id, slug)...")
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT c.conname
            FROM   pg_constraint c
            JOIN   pg_class      t ON t.oid = c.conrelid
            JOIN   pg_attribute  a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
            WHERE  t.relname = 'kitchens' AND c.contype = 'u'
            GROUP  BY c.conname, c.conkey
            HAVING array_agg(a.attname::text ORDER BY a.attnum) = ARRAY['slug']::text[]
        """)).fetchall()
    for r in rows:
        _exec(f'ALTER TABLE kitchens DROP CONSTRAINT "{r[0]}"')
        print(f"      dropped kitchens unique: {r[0]}")
    if not _has_constraint("uq_kitchens_org_slug"):
        _exec("ALTER TABLE kitchens ADD CONSTRAINT uq_kitchens_org_slug UNIQUE (org_id, slug)")
        print("      + uq_kitchens_org_slug")


# ── Step 5: users.username becomes unique per org ──────────────────────────

def fix_users_username_uniqueness():
    print("[5/5] Moving users.username unique to (org_id, username)...")
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT c.conname
            FROM   pg_constraint c
            JOIN   pg_class      t ON t.oid = c.conrelid
            JOIN   pg_attribute  a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
            WHERE  t.relname = 'users' AND c.contype = 'u'
            GROUP  BY c.conname, c.conkey
            HAVING array_agg(a.attname::text ORDER BY a.attnum) = ARRAY['username']::text[]
        """)).fetchall()
    for r in rows:
        _exec(f'ALTER TABLE users DROP CONSTRAINT "{r[0]}"')
        print(f"      dropped users unique: {r[0]}")
    if not _has_constraint("uq_users_org_username"):
        _exec("ALTER TABLE users ADD CONSTRAINT uq_users_org_username UNIQUE (org_id, username)")
        print("      + uq_users_org_username")


# ── Optional: promote existing admin ───────────────────────────────────────

def promote_admin_to_platform():
    print("[+] Promoting user 'admin' to platform_admin...")
    with engine.begin() as c:
        res = c.execute(text("UPDATE users SET role='platform_admin' WHERE username='admin'"))
        print(f"      {res.rowcount} row(s) promoted")


def verify():
    print("[✓] Verification")
    with engine.connect() as c:
        o = c.execute(text("SELECT COUNT(*) FROM organizations")).scalar()
        k_null = c.execute(text("SELECT COUNT(*) FROM kitchens WHERE org_id IS NULL")).scalar()
        u_null = c.execute(text("SELECT COUNT(*) FROM users WHERE org_id IS NULL")).scalar()
        users = c.execute(text("SELECT id, username, role, org_id FROM users ORDER BY id")).fetchall()
    print(f"      organizations={o}")
    print(f"      kitchens with NULL org_id: {k_null}")
    print(f"      users with NULL org_id:    {u_null}")
    for u in users:
        print(f"      user id={u[0]} username={u[1]} role={u[2]} org={u[3]}")


def main():
    if not REMOTE_DB_URL:
        raise SystemExit("DATABASE_URL is not set — cannot run.")
    print(f"Connected to: {REMOTE_DB_URL.split('@')[-1]}")
    create_orgs_table()
    add_org_id_columns()
    backfill_org()
    fix_kitchens_slug_uniqueness()
    fix_users_username_uniqueness()
    if "--promote-admin" in sys.argv:
        promote_admin_to_platform()
    verify()
    print("Done.")


if __name__ == "__main__":
    main()
