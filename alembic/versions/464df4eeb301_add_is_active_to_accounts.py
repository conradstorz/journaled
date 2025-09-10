"""add is_active to accounts

Revision ID: 20250910_0003
Revises: 20250908_0002
Create Date: 2025-09-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250910_0003"
down_revision = "20250908_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # For SQLite, use integer default "1"; for others, sa.true() also works.
    op.add_column(
        "accounts",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
    )
    # If there are existing rows and some engines don’t backfill server_default immediately:
    op.execute("UPDATE accounts SET is_active=1 WHERE is_active IS NULL")
    # Drop the server default so future inserts must provide a value or use app-layer default
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.alter_column("is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("accounts", "is_active")
