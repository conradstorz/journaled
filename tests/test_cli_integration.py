
import subprocess
import os
import sys
import tempfile
import pytest
from sqlalchemy import create_engine, inspect
from loguru import logger

# Configure loguru to write logs to a file as well as stdout
logger.remove()  # Remove default handler
logger.add("test_cli_integration.log", rotation="1 MB", level="DEBUG")
logger.add(sys.stderr, level="INFO")

@pytest.mark.integration
def test_cli_init_db_creates_schema():
    """
    Test that the CLI 'init-db' command applies migrations and creates tables in a fresh test database.
    """
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    db_path = project_root / "test.db"
    db_url = f"sqlite:///{db_path}"
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url

    logger.info(f"Testing CLI init-db with DATABASE_URL={db_url}")
    logger.debug(f"DB path: {db_path}")
    logger.debug(f"Environment: {env}")

    # Use uv run for CLI invocation per project rules
    cmd = ["uv", "run", "src/journaled_app/cli.py", "init-db"]
    result = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True
    )
    logger.info(f"CLI return code: {result.returncode}")
    logger.debug(f"CLI stdout: {result.stdout}")
    logger.debug(f"CLI stderr: {result.stderr}")
    # Connect to the DB and check that at least one Alembic or app table exists
    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"Tables found in DB: {tables}")
    assert tables, "No tables created by init-db CLI command"
    # Optionally, check for a specific table, e.g. 'alembic_version'
    assert 'alembic_version' in tables, "Alembic version table not found after init-db"
