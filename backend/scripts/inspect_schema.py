"""Read-only inspection before migration. Shows current schema & data state."""
from sqlalchemy import text
from backend.core.database import engine, REMOTE_DB_URL


def main():
    print(f"DB: {REMOTE_DB_URL.split('@')[-1]}")
    with engine.connect() as c:
        print("\n── Tables ──")
        rows = c.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name"
        )).fetchall()
        for r in rows:
            print(f"  {r[0]}")

        print("\n── kitchen_id columns ──")
        rows = c.execute(text("""
            SELECT table_name, data_type, is_nullable
            FROM   information_schema.columns
            WHERE  column_name = 'kitchen_id'
            ORDER  BY table_name
        """)).fetchall()
        for r in rows:
            print(f"  {r[0]:15s}  type={r[1]:12s}  nullable={r[2]}")

        print("\n── non-NULL kitchen_id counts (safety check before recast) ──")
        for table in ("items", "trays"):
            exists = c.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name=:t AND column_name='kitchen_id'"
            ), {"t": table}).scalar()
            if not exists:
                print(f"  {table}: no kitchen_id column")
                continue
            non_null = c.execute(text(f"SELECT COUNT(*) FROM {table} WHERE kitchen_id IS NOT NULL")).scalar()
            total = c.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table}: {non_null} / {total} rows have non-NULL kitchen_id")
            if non_null:
                sample = c.execute(text(f"SELECT DISTINCT kitchen_id FROM {table} LIMIT 20")).fetchall()
                print(f"    sample values: {[s[0] for s in sample]}")

        print("\n── users ──")
        rows = c.execute(text("SELECT id, username, role FROM users ORDER BY id")).fetchall()
        for r in rows:
            print(f"  id={r[0]:3d}  {r[1]:20s}  role={r[2]}")

        print("\n── row counts ──")
        for table in ("items", "trays", "tray_items", "scan_errors", "print_jobs", "food_prices"):
            try:
                n = c.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"  {table}: {n}")
            except Exception as e:
                print(f"  {table}: ERR {e}")


if __name__ == "__main__":
    main()
