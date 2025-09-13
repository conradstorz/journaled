# tests/conftest.py
from __future__ import annotations

import logging
import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


from alembic import command
from alembic.config import Config
from loguru import logger

def _migrate(url: str) -> None:
    logger.info(f"Starting Alembic migration for DB URL: {url}")
    try:
        cfg = Config("alembic.ini")
        logger.debug(f"Alembic config loaded from alembic.ini: {cfg}")
        # ensure Alembic uses THIS DB
        cfg.set_main_option("sqlalchemy.url", url)
        logger.debug(f"Set sqlalchemy.url in Alembic config: {url}")
        # ensure your app package is importable in env.py
        cfg.set_main_option("prepend_sys_path", ".;./src")
        logger.debug("Set prepend_sys_path in Alembic config: .;./src")
        logger.info("Running Alembic upgrade to head...")
        command.upgrade(cfg, "head")
        logger.info("Alembic migration complete.")
    except Exception as e:
        logger.exception(f"Alembic migration failed for DB URL: {url}")
        raise

@pytest.fixture(scope="function", autouse=True)
def _isolate_db_per_test(tmp_path: Path):
    """
    Autouse: EVERY test gets its own SQLite file DB + fresh Alembic schema.
    Even tests that don't request a session will still run against a clean DB
    because DATABASE_URL is set before imports.
    """
    logger.info(f"Creating test DB in temporary path: {tmp_path}")
    db_file = tmp_path / "test.db"
    logger.debug(f"Test DB file path: {db_file}")
    url = f"sqlite:///{db_file}"
    logger.info(f"Test DB URL: {url}")
    prev = os.environ.get("DATABASE_URL")
    logger.debug(f"Previous DATABASE_URL: {prev}")

    try:
        os.environ["DATABASE_URL"] = url
        logger.info(f"Set DATABASE_URL to: {url}")
        _migrate(url)
    except Exception as e:
        logger.exception("Exception during DB setup and migration in _isolate_db_per_test.")
        raise
    try:
        logger.info("Yielding to test with fresh DB and schema.")
        yield
    except Exception as e:
        logger.exception("Exception during test execution in _isolate_db_per_test.")
        raise
    finally:
        # restore env to avoid leakage into outer shell
        try:
            if prev is None:
                logger.info("Restoring DATABASE_URL to unset (removing from environment).")
                os.environ.pop("DATABASE_URL", None)
            else:
                logger.info(f"Restoring DATABASE_URL to previous value: {prev}")
                os.environ["DATABASE_URL"] = prev
        except Exception as e:
            logger.exception("Exception while restoring DATABASE_URL in _isolate_db_per_test.")

@pytest.fixture(scope="function")
def session_from_url() -> "Session":
    """
    Handy session fixture for tests that want a DB session.
    """
    try:
        url = os.environ["DATABASE_URL"]
        logger.info(f"Creating SQLAlchemy engine for URL: {url}")
        engine = create_engine(url, future=True)
        logger.debug(f"Engine created: {engine}")
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        logger.debug(f"SessionLocal factory created: {SessionLocal}")
        db = SessionLocal()
        logger.info(f"Session created: {db}")
    except Exception as e:
        logger.exception("Exception during session/engine creation in session_from_url.")
        raise
    try:
        logger.info("Yielding DB session to test.")
        yield db
    except Exception as e:
        logger.exception("Exception during test execution in session_from_url.")
        raise
    finally:
        try:
            logger.info("Closing DB session and disposing engine.")
            db.close()
            engine.dispose()
        except Exception as e:
            logger.exception("Exception during DB session close/engine dispose in session_from_url.")

@pytest.fixture(autouse=True, scope='session')
def silence_sqlalchemy_logging():
    logging.getLogger('sqlalchemy').setLevel(logging.CRITICAL)
