"""add timestamps to transactions and unique idx on splits"""

from alembic import op
import sqlalchemy as sa

# Adjust these to match your chain:
revision = "20250912_0007"
down_revision = "20250910_0006"  # <-- set to your current head
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # --- Ensure transactions.created_at / updated_at exist ---
    if "transactions" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("transactions")}

        if "created_at" not in cols:
            op.add_column(
                "transactions",
                sa.Column(
                    "created_at",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                ),
            )

        if "updated_at" not in cols:
            op.add_column(
                "transactions",
                sa.Column(
                    "updated_at",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                ),
            )

    # --- Create a uniqueness guard for duplicate splits within a transaction ---
    # This prevents exact-duplicate rows (same txn, account, amount, memo).
    # SQLite treats NULLs as distinct; if your tests rely on that, this is OK.
    if "splits" in insp.get_table_names():
        existing = {ix["name"] for ix in insp.get_indexes("splits")}
        if "uq_splits_txn_acct_amt_memo" not in existing:
            op.create_index(
                "uq_splits_txn_acct_amt_memo",
                "splits",
                ["transaction_id", "account_id", "amount", "memo"],
                unique=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "splits" in insp.get_table_names():
        existing = {ix["name"] for ix in insp.get_indexes("splits")}
        if "uq_splits_txn_acct_amt_memo" in existing:
            op.drop_index("uq_splits_txn_acct_amt_memo", table_name="splits")

    # (Leave timestamps in place on downgrade to avoid data loss; or drop them if you prefer:)
    if "transactions" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("transactions")}
        if "updated_at" in cols:
            op.drop_column("transactions", "updated_at")
        if "created_at" in cols:
            op.drop_column("transactions", "created_at")
