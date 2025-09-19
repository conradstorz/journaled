
# tests/conftest.py
"""
Pytest fixtures and helpers for reliable, isolated testing of the Journaled CLI and database.

Key features:
- Creates a canonical test database and runs Alembic migrations ONCE per test session.
- Clones the canonical DB for each test, ensuring isolation and repeatability.
- Provides helpers to run CLI commands as subprocesses with correct environment.
- Silences noisy SQLAlchemy logging for cleaner test output.
"""


# Import future annotations for type hints
from __future__ import annotations

# Standard library imports
import os  # For environment variables and file operations
import sys  # For Python interpreter path
import shutil  # For file copying and removal
import subprocess  # For running CLI commands as subprocesses
from pathlib import Path  # For filesystem path manipulations
from typing import Iterable, Mapping  # For type hints

# SQLAlchemy and Alembic imports for DB and migrations
from sqlalchemy import create_engine  # For creating DB engine
from sqlalchemy.orm import sessionmaker  # For session factory
from alembic import command  # For running Alembic migrations
from alembic.config import Config  # For Alembic config
import logging  # For controlling log output
from loguru import logger  # For structured logging
import pytest  # For pytest fixtures



# Project root and canonical test DB setup

# Get the project root directory (one level up from tests/)
PROJECT_ROOT = Path(__file__).parent.parent
# Define the path for the canonical test DB (created once per session)
CANONICAL_DB_PATH = PROJECT_ROOT / "test_canonical.db"
# Build the SQLAlchemy URL for the canonical DB
CANONICAL_DB_URL = f"sqlite:///{CANONICAL_DB_PATH}"

# Helper to assert subprocess success
def assert_ok(proc, *, msg: str = None, cmd: list = None):
    """
    Helper to assert that a subprocess completed successfully.
    Raises AssertionError with detailed output if the process failed.
    """
    if proc is None:
        raise AssertionError("Subprocess result is None. The CLI may have failed to launch or returned no result.")
    if proc.returncode != 0:
        details = []
        if msg:
            details.append(msg)
        if cmd:
            details.append(f"Command: {' '.join(map(str, cmd))}")
        details.append(f"Exit code: {proc.returncode}")
        details.append("--- STDOUT ---")
        details.append(proc.stdout if proc.stdout else "(empty)")
        details.append("--- STDERR ---")
        details.append(proc.stderr if proc.stderr else "(empty)")
        raise AssertionError("\n".join(details))


def pytest_configure():
    """
    Pytest hook: runs once per test session.
    Creates the canonical test DB and applies all Alembic migrations.
    Sets DATABASE_URL to point to the canonical DB.
    """
    import time
    # Remove any previous canonical test DB to start fresh
    if CANONICAL_DB_PATH.exists():
        try:
            CANONICAL_DB_PATH.unlink()
        except Exception as e:
            logger.error(f"Failed to remove old canonical DB: {e}")
            raise
    # Try to create and migrate the canonical DB
    try:
        from sqlalchemy import create_engine
        engine = create_engine(CANONICAL_DB_URL, future=True)
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", CANONICAL_DB_URL)
        command.upgrade(alembic_cfg, "head")
        # Optional: delay to ensure migrations complete (for slow FS or concurrent runs)
        time.sleep(1)
        engine.dispose()
        os.environ["DATABASE_URL"] = str(CANONICAL_DB_URL)
        logger.info(f"Canonical test DB created and migrated: {CANONICAL_DB_PATH}")
    except Exception as e:
        logger.error(f"Failed to create or migrate canonical test DB: {e}")
        raise

def _merge_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """
    Helper to merge environment variables for subprocesses.
    Returns a copy of os.environ with optional overrides.

    Parameters:
    - extra: An optional Mapping (like a dict) of environment variable names (str) to values (str).
      If provided, these will override or add to the current environment.

    Returns:
    - A dictionary containing the merged environment variables.
    """
    # Copy current environment variables from the OS
    env = os.environ.copy()
    # If 'extra' is provided and is not None or empty, update 'env' with its key-value pairs.
    # This means any variable in 'extra' will override the same variable in 'env', or add new ones.
    if extra:
        env.update(extra)
    # Return the merged environment dictionary
    return env


@pytest.fixture
def run_cli():
    """
    Fixture to run the Journaled CLI as a Python module.
    Ensures correct interpreter and PYTHONPATH for subprocesses.
    Returns a function that runs the CLI and returns the CompletedProcess.
    """
    # Define the runner function for CLI commands
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
        # Build the CLI command as a Python module
        cmd: list[str] = [sys.executable, "-m", module, *args]
        # Merge environment variables
        merged_env = _merge_env(env)
        # Ensure PYTHONPATH includes src directory for imports
        src_path = str(Path(__file__).parent.parent / "src")
        merged_env["PYTHONPATH"] = src_path + os.pathsep + merged_env.get("PYTHONPATH", "")
        # Print the command and environment for debugging
        print(f"Running CLI command: {cmd}\nCWD: {cwd}\nENV: {merged_env}")
        # Run the subprocess and capture output
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=merged_env,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # Manual error handling below
        )
        # Print the result for debugging
        print(f"Subprocess result: {result}")
        # Raise error if check=True and process failed
        if check and result.returncode != 0:
            raise AssertionError(
                f"CLI exited with {result.returncode}\n"
                f"CMD: {' '.join(cmd)}\n"
                f"--- STDOUT ---\n{result.stdout}\n"
                f"--- STDERR ---\n{result.stderr}\n"
            )
        # Return the CompletedProcess result
        return result
    # Return the runner function as the fixture value
    return _runner



def _migrate(url: str) -> None:
    """
    Helper to run Alembic migrations for a given DB URL.
    Used for manual migration in tests if needed.
    """
    # Log migration start
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
    Fixture to provide a fresh, isolated test DB for each test function.
    - Clones the canonical DB to a temp file
    - Sets DATABASE_URL to the clone
    - Yields a SQLAlchemy session
    - Cleans up the DB file after the test
    """
    # Generate a unique temp file path for the cloned DB
    """
    Clone the canonical test DB for each test, set DATABASE_URL, and clean up after.
    """
    import time
    # Wait for canonical DB to exist (in case of slow creation)
    max_wait = 5
    waited = 0
    while not CANONICAL_DB_PATH.exists() and waited < max_wait:
        logger.warning(f"Waiting for canonical DB to be created...")
        time.sleep(1)
        waited += 1
    if not CANONICAL_DB_PATH.exists():
        raise FileNotFoundError(f"Canonical test DB not found after waiting {max_wait} seconds: {CANONICAL_DB_PATH}")
    # Generate a unique temp file path for the cloned DB
    clone_path = Path(tempfile.gettempdir()) / f"test_clone_{uuid.uuid4().hex}.db"
    try:
        shutil.copy(CANONICAL_DB_PATH, clone_path)
    except Exception as e:
        logger.error(f"Failed to clone canonical DB: {e}")
        raise
    # Build the DB URL for the clone
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
            try:
                clone_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete cloned test DB: {e}")

@pytest.fixture(autouse=True, scope='session')
def silence_sqlalchemy_logging():
    """
    Fixture to silence SQLAlchemy logging for cleaner test output.
    Automatically applied to all tests in the session.
    """
    # Set SQLAlchemy logger to CRITICAL to suppress output
    logging.getLogger('sqlalchemy').setLevel(logging.CRITICAL)

# End of tests/conftest.py

