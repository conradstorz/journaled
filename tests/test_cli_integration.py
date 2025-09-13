import subprocess
import os
import tempfile
import pytest
from sqlalchemy import create_engine, inspect

@pytest.mark.integration
def test_cli_init_db_creates_schema():
    """
    Test that the CLI 'init-db' command applies migrations and creates tables in a fresh test database.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db_url = f'sqlite:///{db_path}'
        env = os.environ.copy()
        env['DATABASE_URL'] = db_url

        # Run the CLI command as a subprocess
        result = subprocess.run(
            ['python', '-m', 'src.ledger_app.cli', 'init-db'],
            env=env,
            capture_output=True,
            text=True
        )
        # This will fail if the CLI or migration is not working
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        # Connect to the DB and check that at least one Alembic or app table exists
        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert tables, "No tables created by init-db CLI command"
        # Optionally, check for a specific table, e.g. 'alembic_version'
        assert 'alembic_version' in tables, "Alembic version table not found after init-db"
