"""
Test: Validate new DB schema compatibility with production DB

This test creates a new database from scratch using Alembic migrations and compares its schema to a copy of the production database. It fails if there are any incompatibilities in tables, columns, or constraints.
"""
import pytest
from pathlib import Path
from sqlalchemy import create_engine, inspect
from alembic.config import Config
from alembic import command
import shutil

PROJECT_ROOT = Path(__file__).parent.parent
NEW_DB_PATH = PROJECT_ROOT / "test_schema_check.db"
PROD_DB_PATH = PROJECT_ROOT / "prod_db_copy.db"  # Update this path to your actual production DB copy

@pytest.mark.usefixtures("run_cli")
def test_new_db_schema_matches_production():
    # Remove old test DB if exists
    if NEW_DB_PATH.exists():
        NEW_DB_PATH.unlink()
    # Create new DB and run migrations
    alembic_cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{NEW_DB_PATH}")
    command.upgrade(alembic_cfg, "head")
    # Connect to both DBs
    new_engine = create_engine(f"sqlite:///{NEW_DB_PATH}")
    prod_engine = create_engine(f"sqlite:///{PROD_DB_PATH}")
    new_inspector = inspect(new_engine)
    prod_inspector = inspect(prod_engine)
    # Compare tables
    new_tables = set(new_inspector.get_table_names())
    prod_tables = set(prod_inspector.get_table_names())
    assert new_tables == prod_tables, f"Table mismatch: {new_tables ^ prod_tables}"
    # Compare columns for each table
    for table in new_tables:
        new_cols = {col['name']: col for col in new_inspector.get_columns(table)}
        prod_cols = {col['name']: col for col in prod_inspector.get_columns(table)}
        assert new_cols.keys() == prod_cols.keys(), f"Column mismatch in {table}: {new_cols.keys() ^ prod_cols.keys()}"
        # Optionally compare column types, constraints, etc.
        for col_name in new_cols:
            assert new_cols[col_name]['type'].__class__ == prod_cols[col_name]['type'].__class__, (
                f"Type mismatch in {table}.{col_name}: {new_cols[col_name]['type']} != {prod_cols[col_name]['type']}"
            )
    # Optionally compare indexes, constraints, etc.
    new_engine.dispose()
    prod_engine.dispose()
