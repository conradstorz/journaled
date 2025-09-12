"""add checks.memo_line"""

from alembic import op
import sqlalchemy as sa

revision = "20250912_0011"   # or whatever Alembic assigned
down_revision = "20250912_0010"  # set to your current head
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "checks" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("checks")}
        if "memo_line" not in cols:
            op.add_column("checks", sa.Column("memo_line", sa.String(length=255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "checks" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("checks")}
        if "memo_line" in cols:
            op.drop_column("checks", "memo_line")
