# tests/conftest.py
from __future__ import annotations
import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session")
def test_db_url(tmp_path_factory) -> str:
    """
    Use a file-based SQLite DB so Alembic and the Session see the same database.
    """
    db_file = tmp_path_factory.mktemp("db") / "test.db"
    url = f"sqlite:///{db_file}"
    # Make it discoverable by code that reads DATABASE_URL (optional)
    os.environ["DATABASE_URL"] = url
    return url


@pytest.fixture(scope="session")
def alembic_upgrade(test_db_url: str):
    """
    Upgrade the test database to the latest migration.
    """
    cfg = Config("alembic.ini")
    # Force Alembic to target the test DB file
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(cfg, "head")


@pytest.fixture()
def session_from_url(test_db_url: str, alembic_upgrade):
    """
    Provide a SQLAlchemy Session bound to the same file DB that Alembic upgraded.
    """
    # echo=True is handy while debugging; flip to False later
    engine = create_engine(test_db_url, future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
