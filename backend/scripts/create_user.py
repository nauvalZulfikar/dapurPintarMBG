"""
Create a user in the database.

Usage:
    python -m backend.scripts.create_user <username> <password> [role]

Example:
    python -m backend.scripts.create_user admin mypassword
    python -m backend.scripts.create_user staff staffpass staff
"""

import sys
from sqlalchemy import select
from backend.core.database import engine, remote_users, remote_metadata
from backend.utils.auth import hash_password


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m backend.scripts.create_user <username> <password> [role]")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    role = sys.argv[3] if len(sys.argv) > 3 else "admin"

    # Create table if not exists
    remote_metadata.create_all(engine, tables=[remote_users])

    # Check if user already exists
    with engine.connect() as c:
        existing = c.execute(
            select(remote_users).where(remote_users.c.username == username)
        ).first()

    if existing:
        print(f"User '{username}' already exists.")
        sys.exit(1)

    # Insert user
    with engine.begin() as c:
        c.execute(remote_users.insert().values(
            username=username,
            password_hash=hash_password(password),
            role=role,
        ))

    print(f"User '{username}' created with role '{role}'.")


if __name__ == "__main__":
    main()
