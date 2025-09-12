"""create transactions and splits (idempotent)"""

from alembic import op
import sqlalchemy as sa

# adjust these to match your chain
revision = "20250910_0006"
down_revision = "20250910_0005"  # or your current head before this file
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- transactions ---
    if not _table_exists("transactions"):
        op.create_table(
            "transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("date", sa.Date(), nullable=False, index=True),
            sa.Column("description", sa.String(255), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    # --- splits ---
    if not _table_exists("splits"):
        op.create_table(
            "splits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("transaction_id", sa.Integer(), nullable=False, index=True),
            sa.Column("account_id", sa.Integer(), nullable=False, index=True),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("memo", sa.String(255), nullable=True),
            sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], name="fk_splits_txn", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_splits_acct", ondelete="RESTRICT"),
        )

    # helpful indexes (SQLite-safe idempotence)
    _create_index_if_not_exists("ix_transactions_date", "transactions", ["date"])
    _create_index_if_not_exists("ix_splits_txn_acct", "splits", ["transaction_id", "account_id"])
    _create_index_if_not_exists("ix_splits_acct", "splits", ["account_id"])


def downgrade() -> None:
    if _table_exists("splits"):
        op.drop_table("splits")
    if _table_exists("transactions"):
        op.drop_table("transactions")


# ---- helpers (SQLite-safe) ----
def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def _create_index_if_not_exists(ix_name: str, table: str, cols: list[str]) -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return
    existing = {ix["name"] for ix in insp.get_indexes(table)}
    if ix_name not in existing:
        op.create_index(ix_name, table, cols)
