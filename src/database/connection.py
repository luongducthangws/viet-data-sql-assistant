"""
src/database/connection.py - SQLAlchemy engine and session factory.
"""

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/northwind"
DATABASE_URL = (os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL).strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_db():
    """Context manager used as `with get_db() as db:`."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> bool:
    """Return True when the database connection is usable."""
    ok, _ = check_connection_detail()
    return ok


def check_connection_detail() -> tuple[bool, str | None]:
    """Return database health and a sanitized error message."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc).splitlines()[0][:240]
