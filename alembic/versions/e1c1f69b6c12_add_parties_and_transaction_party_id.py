"""add parties and transaction.party_id"""

from alembic import op
import sqlalchemy as sa

revision = "20250912_0008"
down_revision = "20250912_0007"  # set to your current head
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1) Create parties table if missing
    if "parties" not in insp.get_table_names():
        op.create_table(
            "parties",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False, index=True),
        )

    # 2) Add party_id to transactions if missing
    if "transactions" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("transactions")}
        if "party_id" not in cols:
            op.add_column(
                "transactions",
                sa.Column("party_id", sa.Integer(), nullable=True),
            )
            # SQLite won’t enforce FK without table rebuild; that’s fine for tests.
            # Still create the index and (best-effort) FK for non-SQLite engines.
            # Index:
            existing = {ix["name"] for ix in insp.get_indexes("transactions")}
            if "ix_transactions_party_id" not in existing:
                op.create_index("ix_transactions_party_id", "transactions", ["party_id"])
            # FK (will be a no-op on SQLite runtime; okay for dev):
            try:
                op.create_foreign_key(
                    "fk_transactions_party",
                    source_table="transactions",
                    referent_table="parties",
                    local_cols=["party_id"],
                    remote_cols=["id"],
                    ondelete="SET NULL",
                )
            except Exception:
                # SQLite path: ignore if not supported
                pass

def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # drop FK/index/column (best-effort, SQLite-safe)
    if "transactions" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("transactions")}
        existing = {ix["name"] for ix in insp.get_indexes("transactions")}
        if "fk_transactions_party" in getattr(insp, "get_foreign_keys", lambda *_: [])("transactions"):
            try:
                op.drop_constraint("fk_transactions_party", "transactions", type_="foreignkey")
            except Exception:
                pass
        if "ix_transactions_party_id" in existing:
            op.drop_index("ix_transactions_party_id", table_name="transactions")
        if "party_id" in cols:
            op.drop_column("transactions", "party_id")

    if "parties" in insp.get_table_names():
        op.drop_table("parties")

