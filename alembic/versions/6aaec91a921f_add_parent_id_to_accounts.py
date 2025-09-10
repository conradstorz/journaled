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
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1) Add column if missing
    cols = {c["name"] for c in insp.get_columns("accounts")}
    if "parent_id" not in cols:
        op.add_column("accounts", sa.Column("parent_id", sa.Integer(), nullable=True))

    # 2) Add index if missing
    idx_names = {ix["name"] for ix in insp.get_indexes("accounts")}
    if "ix_accounts_parent_id" not in idx_names:
        op.create_index("ix_accounts_parent_id", "accounts", ["parent_id"])

    # 3) Add FK on non-SQLite engines only (and only if not present)
    dialect = bind.dialect.name
    if dialect != "sqlite":
        fks = {fk["name"] for fk in insp.get_foreign_keys("accounts") if fk.get("name")}
        if "fk_accounts_parent_id_accounts" not in fks:
            op.create_foreign_key(
                "fk_accounts_parent_id_accounts",
                "accounts",
                "accounts",
                local_cols=["parent_id"],
                remote_cols=["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    dialect = bind.dialect.name
    if dialect != "sqlite":
        fks = {fk["name"] for fk in insp.get_foreign_keys("accounts") if fk.get("name")}
        if "fk_accounts_parent_id_accounts" in fks:
            op.drop_constraint("fk_accounts_parent_id_accounts", "accounts", type_="foreignkey")

    idx_names = {ix["name"] for ix in insp.get_indexes("accounts")}
    if "ix_accounts_parent_id" in idx_names:
        op.drop_index("ix_accounts_parent_id", table_name="accounts")

    cols = {c["name"] for c in insp.get_columns("accounts")}
    if "parent_id" in cols:
        op.drop_column("accounts", "parent_id")