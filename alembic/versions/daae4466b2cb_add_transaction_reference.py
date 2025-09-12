"""add transaction.reference"""

from alembic import op
import sqlalchemy as sa

revision = "20250912_0009"
down_revision = "20250912_0008"  # set to your current head
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "transactions" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("transactions")}
        if "reference" not in cols:
            op.add_column(
                "transactions",
                sa.Column("reference", sa.String(length=64), nullable=True),
            )

            # add an index for faster lookups (idempotent)
            existing = {ix["name"] for ix in insp.get_indexes("transactions")}
            if "ix_transactions_reference" not in existing:
                op.create_index("ix_transactions_reference", "transactions", ["reference"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "transactions" in insp.get_table_names():
        existing = {ix["name"] for ix in insp.get_indexes("transactions")}
        if "ix_transactions_reference" in existing:
            op.drop_index("ix_transactions_reference", table_name="transactions")

        cols = {c["name"] for c in insp.get_columns("transactions")}
        if "reference" in cols:
            op.drop_column("transactions", "reference")
