# tests/conftest.py
from __future__ import annotations

import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from alembic import command
from alembic.config import Config

def _migrate(url: str) -> None:
    cfg = Config("alembic.ini")
    # ensure Alembic uses THIS DB
    cfg.set_main_option("sqlalchemy.url", url)
    # ensure your app package is importable in env.py
    cfg.set_main_option("prepend_sys_path", ".;./src")
    command.upgrade(cfg, "head")

@pytest.fixture(scope="function", autouse=True)
def _isolate_db_per_test(tmp_path: Path):
    """
    Autouse: EVERY test gets its own SQLite file DB + fresh Alembic schema.
    Even tests that don't request a session will still run against a clean DB
    because DATABASE_URL is set before imports.
    """
    db_file = tmp_path / "test.db"
    url = f"sqlite:///{db_file}"
    prev = os.environ.get("DATABASE_URL")

    os.environ["DATABASE_URL"] = url
    _migrate(url)
    try:
        yield
    finally:
        # restore env to avoid leakage into outer shell
        if prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev

@pytest.fixture(scope="function")
def session_from_url() -> "Session":
    """
    Handy session fixture for tests that want a DB session.
    """
    url = os.environ["DATABASE_URL"]
    engine = create_engine(url, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
