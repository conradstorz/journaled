# tests/conftest.py
from __future__ import annotations

import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from alembic import command
from alembic.config import Config

@pytest.fixture(scope="function")
def test_db_url(tmp_path: Path) -> str:
    """
    Create a brand-new file-based SQLite DB for EACH TEST.
    Also set DATABASE_URL so any code that reads it gets the same DB.
    """
    db_file = tmp_path / "test.db"
    url = f"sqlite:///{db_file}"
    os.environ["DATABASE_URL"] = url
    return url

@pytest.fixture(scope="function")
def alembic_upgrade(test_db_url: str):
    """
    Run Alembic migrations against the per-test database.
    """
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    # ensure src is importable if env.py relies on it
    cfg.set_main_option("prepend_sys_path", ".;./src")
    command.upgrade(cfg, "head")

@pytest.fixture(scope="function")
def session_from_url(test_db_url: str, alembic_upgrade):
    """
    Return a SQLAlchemy Session bound to the per-test DB.
    """
    engine = create_engine(test_db_url, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
