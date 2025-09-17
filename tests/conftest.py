# Canonical test DB path (project root)
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


PROJECT_ROOT = Path(__file__).parent.parent
CANONICAL_DB_PATH = PROJECT_ROOT / "test.db"
CANONICAL_DB_URL = f"sqlite:///{CANONICAL_DB_PATH}"

# Helper to assert subprocess success
def assert_ok(proc, *, msg: str = None):
    if proc is None:
        raise AssertionError("Subprocess result is None. The CLI may have failed to launch or returned no result.")
    if proc.returncode != 0:
        details = (
            (msg + "\n") if msg else ""
        ) + f"Exit code: {proc.returncode}\n--- STDOUT ---\n{proc.stdout}\n--- STDERR ---\n{proc.stderr}"
        raise AssertionError(details)


def pytest_configure():
    # Create canonical DB and run migrations ONCE
    if CANONICAL_DB_PATH.exists():
        CANONICAL_DB_PATH.unlink()
    from sqlalchemy import create_engine
    engine = create_engine(CANONICAL_DB_URL, future=True)
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", CANONICAL_DB_URL)
    command.upgrade(alembic_cfg, "head")
    engine.dispose()
    os.environ["DATABASE_URL"] = str(CANONICAL_DB_URL)

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
        merged_env = _merge_env(env)
        # Ensure PYTHONPATH includes src directory
        src_path = str(Path(__file__).parent.parent / "src")
        merged_env["PYTHONPATH"] = src_path + os.pathsep + merged_env.get("PYTHONPATH", "")
        print(f"Running CLI command: {cmd}\nCWD: {cwd}\nENV: {merged_env}")
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=merged_env,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # we raise manually so we can include stdout on failure
        )
        print(f"Subprocess result: {result}")
        if check and result.returncode != 0:
            raise AssertionError(
                f"CLI exited with {result.returncode}\n"
                f"CMD: {' '.join(cmd)}\n"
                f"--- STDOUT ---\n{result.stdout}\n"
                f"--- STDERR ---\n{result.stderr}\n"
            )
        return result
    return _runner



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


import tempfile
import shutil
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="function")
def cloned_test_db():
    """
    Clone the canonical test DB for each test, set DATABASE_URL, and clean up after.
    """
    clone_path = Path(tempfile.gettempdir()) / f"test_clone_{uuid.uuid4().hex}.db"
    shutil.copy(CANONICAL_DB_PATH, clone_path)
    url = f"sqlite:///{clone_path}"
    os.environ["DATABASE_URL"] = url
    logger.info(f"Cloned test DB for test: {clone_path}")
    engine = create_engine(url, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
        if clone_path.exists():
            clone_path.unlink()

@pytest.fixture(autouse=True, scope='session')
def silence_sqlalchemy_logging():
    logging.getLogger('sqlalchemy').setLevel(logging.CRITICAL)
