"""add parent_id to accounts (SQLite-safe)

Revision ID: 20250910_0004
Revises: 20250910_0003
Create Date: 2025-09-10
"""
from alembic import op
import sqlalchemy as sa
from alembic import context

# revision identifiers, used by Alembic.
revision = "20250910_0004"
down_revision = "20250910_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add the column plainly (no batch; avoids SQLite table-recreate ordering issues)
    op.add_column("accounts", sa.Column("parent_id", sa.Integer(), nullable=True))

    # 2) Index is fine on SQLite
    op.create_index("ix_accounts_parent_id", "accounts", ["parent_id"])

    # 3) Only add FK on engines that can ALTER TABLE ADD CONSTRAINT sanely
    bind = context.get_bind()
    dialect = bind.dialect.name if bind is not None else ""
    if dialect not in ("sqlite",):
        op.create_foreign_key(
            "fk_accounts_parent_id_accounts",
            "accounts",
            "accounts",
            local_cols=["parent_id"],
            remote_cols=["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    # Drop FK if it exists (no-op on SQLite)
    bind = context.get_bind()
    dialect = bind.dialect.name if bind is not None else ""
    if dialect not in ("sqlite",):
        op.drop_constraint("fk_accounts_parent_id_accounts", "accounts", type_="foreignkey")

    op.drop_index("ix_accounts_parent_id", table_name="accounts")
    op.drop_column("accounts", "parent_id")
