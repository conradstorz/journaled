"""add checks and transaction reversal link

Revision ID: 20250908_0002
Revises: 20250905_0001
Create Date: 2025-09-08 15:36:41
"""
from alembic import op
import sqlalchemy as sa

revision = "20250908_0002"
down_revision = "20250905_0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    check_status = sa.Enum("ISSUED","VOID","CLEARED", name="checkstatus")

    op.create_table(
        "checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("check_no", sa.String(), nullable=False, unique=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("payee_id", sa.Integer(), sa.ForeignKey("parties.id"), nullable=True),
        sa.Column("amount", sa.Numeric(18,2), nullable=False),
        sa.Column("memo", sa.String(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("status", check_status, nullable=False, server_default="ISSUED"),
    )

    op.create_table(
        "transaction_reversals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("original_tx_id", sa.Integer(), sa.ForeignKey("transactions.id"), unique=True, nullable=False),
        sa.Column("reversing_tx_id", sa.Integer(), sa.ForeignKey("transactions.id"), unique=True, nullable=False),
    )

def downgrade() -> None:
    op.drop_table("transaction_reversals")
    op.drop_table("checks")
    op.execute("DROP TYPE IF EXISTS checkstatus")
