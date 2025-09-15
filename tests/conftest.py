# tests/conftest.py
"""
Pytest fixtures for running your CLI from tests, correctly, under `uv run`.

- `run_cli()` runs `python -m journaled_app.cli ...` with the SAME interpreter
  pytest is using (the one uv bootstrapped).
- `cli_bin()` resolves the console-script shim (if you want to test the
    installed entry point named `journaled`).
- `temp_workdir` gives an isolated CWD.
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Mapping

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config
import logging
from loguru import logger
import pytest


def _merge_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a copy of os.environ with optional overrides."""
    env = os.environ.copy()
    if extra:
        env.update(extra)
    return env


@pytest.fixture
def run_cli():
    """
    Run your CLI as a Python module to avoid PATH/console-script issues.

    Example:
        res = run_cli("init-db", "--path", str(tmp_path/"app.db"))
        assert res.returncode == 0, res.stderr
    """
    def _runner(
        *args: str,
    module: str = "journaled_app.cli",          # change if your entry module differs
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = 60,
        check: bool = False,                      # set True to raise on nonzero exit
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        cmd: list[str] = [sys.executable, "-m", module, *args]
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=_merge_env(env),
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # we raise manually so we can include stdout on failure
        )
        if check and result.returncode != 0:
            raise AssertionError(
                f"CLI exited with {result.returncode}\n"
                f"CMD: {' '.join(cmd)}\n"
                f"--- STDOUT ---\n{result.stdout}\n"
                f"--- STDERR ---\n{result.stderr}\n"
            )
        return result
    return _runner


@pytest.fixture
def cli_bin() -> Path:
    """
    Resolve the installed console script (e.g., `journaled`) from PATH.

    Works as long as you run pytest via `uv run -m pytest` so uv injects
    the env's Scripts/bin dir into PATH.
    """
    exe = shutil.which("journaled")  # rename if your script is named differently
    if not exe:
        pytest.skip("Console script 'journaled' not found on PATH (run tests via `uv run -m pytest`).")
    return Path(exe)


@pytest.fixture
def temp_workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Isolated working directory for tests that touch the filesystem.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


def assert_ok(proc: subprocess.CompletedProcess[str], *, msg: str | None = None) -> None:
    """
    Helper assertion that prints stdout/stderr on failure for easier debugging.
    """
    if proc.returncode != 0:
        details = (
            (msg + "\n") if msg else ""
        ) + f"Exit code: {proc.returncode}\n--- STDOUT ---\n{proc.stdout}\n--- STDERR ---\n{proc.stderr}"
        raise AssertionError(details)



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
