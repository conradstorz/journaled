import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"

@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    dbfile = tmp_path / "test.db"
    return f"sqlite:///{dbfile}"

@pytest.fixture
def alembic_upgrade(sqlite_url: str):
    """Apply alembic migrations to a fresh SQLite file DB and yield the URL."""
    cfg = Config(str(ALEMBIC_INI))
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = sqlite_url
    try:
        command.upgrade(cfg, "head")
        yield sqlite_url
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old

@pytest.fixture
def session_from_url(alembic_upgrade):
    """Yield a SQLAlchemy session bound to the migrated DB."""
    engine = create_engine(alembic_upgrade, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
