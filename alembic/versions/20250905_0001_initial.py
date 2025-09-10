"""initial schema

Revision ID: 20250905_0001
Revises: 
Create Date: 2025-09-05 15:21:58

"""

from alembic import op
import sqlalchemy as sa
import enum

# revision identifiers, used by Alembic.
revision = "20250905_0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    account_type = sa.Enum("ASSET","LIABILITY","EQUITY","INCOME","EXPENSE", name="accounttype")
    party_kind = sa.Enum("PAYEE","VENDOR","CUSTOMER","MIXED", name="partykind")

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("type", account_type, nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="USD"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1"))
    )

    op.create_table(
        "parties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("kind", party_kind, nullable=False, server_default="MIXED"),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
    )

    op.create_table(
        "addresses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("line1", sa.String(), nullable=False),
        sa.Column("line2", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("postal", sa.String(), nullable=False),
        sa.Column("country", sa.String(), nullable=False, server_default="US"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("parties.id"), nullable=True),
    )

    op.create_table(
        "splits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18,2), nullable=False),
        sa.Column("memo", sa.String(), nullable=True),
        sa.UniqueConstraint("transaction_id","account_id","amount","memo", name="uq_split_dedupe"),
    )

    op.create_table(
        "statements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("opening_bal", sa.Numeric(18,2), nullable=False),
        sa.Column("closing_bal", sa.Numeric(18,2), nullable=False),
    )

    op.create_table(
        "statement_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("statement_id", sa.Integer(), sa.ForeignKey("statements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("posted_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18,2), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("fitid", sa.String(), nullable=True),
        sa.Column("matched_split_id", sa.Integer(), sa.ForeignKey("splits.id"), nullable=True),
    )

def downgrade() -> None:
    op.drop_table("statement_lines")
    op.drop_table("statements")
    op.drop_table("splits")
    op.drop_table("transactions")
    op.drop_table("addresses")
    op.drop_table("parties")
    op.drop_table("accounts")
    op.execute("DROP TYPE IF EXISTS accounttype")
    op.execute("DROP TYPE IF EXISTS partykind")

