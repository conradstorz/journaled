"""add parent_id to accounts

Revision ID: 20250910_0004
Revises: 20250910_0003
Create Date: 2025-09-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250910_0004"
down_revision = "20250910_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch mode for SQLite compatibility (adds FK/index safely)
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_accounts_parent_id", ["parent_id"])
        batch_op.create_foreign_key(
            "fk_accounts_parent_id_accounts",
            "accounts",
            ["parent_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_constraint("fk_accounts_parent_id_accounts", type_="foreignkey")
        batch_op.drop_index("ix_accounts_parent_id")
        batch_op.drop_column("parent_id")
