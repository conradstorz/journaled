

# Alembic migration template

"""create transactions and splits (idempotent)

Revision ID: bd510c4dd1c4
Revises: 20250910_0004
Create Date: 2025-09-10 16:04:47.261765

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250910_0005"
down_revision = "20250910_0004"
branch_labels = None
depends_on = None


def _table_exists(bind, name: str) -> bool:
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    # transactions
    if not _table_exists(bind, "transactions"):
        op.create_table(
            "transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
        )

    # splits
    if not _table_exists(bind, "splits"):
        op.create_table(
            "splits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("transaction_id", sa.Integer(), nullable=False, index=True),
            sa.Column("account_id", sa.Integer(), nullable=False, index=True),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("memo", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        )

    # indices for splits (SQLite won’t auto-create index=True here)
    insp = sa.inspect(bind)
    existing_idx = {ix["name"] for ix in insp.get_indexes("splits")} if _table_exists(bind, "splits") else set()
    if "ix_splits_transaction_id" not in existing_idx:
        op.create_index("ix_splits_transaction_id", "splits", ["transaction_id"])
    if "ix_splits_account_id" not in existing_idx:
        op.create_index("ix_splits_account_id", "splits", ["account_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "ix_splits_transaction_id" in {ix["name"] for ix in insp.get_indexes("splits")}:
        op.drop_index("ix_splits_transaction_id", table_name="splits")
    if "ix_splits_account_id" in {ix["name"] for ix in insp.get_indexes("splits")}:
        op.drop_index("ix_splits_account_id", table_name="splits")
    if _table_exists(bind, "splits"):
        op.drop_table("splits")
    if _table_exists(bind, "transactions"):
        op.drop_table("transactions")
