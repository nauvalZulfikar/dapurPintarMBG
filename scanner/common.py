# common.py

import os
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Set up the DATABASE_URL for PostgreSQL (or SQLite as fallback)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scans.db')}")

# SQLAlchemy engine setup
engine_kwargs = {"future": True, "pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite:///"):
    # SQLite-specific setup
    engine_kwargs["connect_args"] = {"check_same_thread": False}

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, **engine_kwargs)

# Create metadata object to track schema (tables, columns)
metadata = MetaData()

# SessionLocal - Session maker for database interaction
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Function to get a database session (yielding the session to be used in the code)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create all tables (useful on first run or migrations)
def create_tables():
    # Create all tables defined by metadata
    metadata.create_all(engine)

