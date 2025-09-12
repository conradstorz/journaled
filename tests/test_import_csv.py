from datetime import date
from decimal import Decimal
from pathlib import Path
from sqlalchemy import select
from ledger_app.models import Base, Statement, StatementLine
from ledger_app.services.import_csv import import_statement_csv

CSV_CONTENT = "date,amount,description,fitid\n2025-01-06,-50.00,OFFICE SUPPLIES,abc123\n2025-01-07,100.00,REFUND,def456\n"

def test_import_csv_creates_statement_and_lines(tmp_path, session_from_url):
    db = session_from_url
    csv_file = tmp_path / "bank.csv"
    csv_file.write_text(CSV_CONTENT, encoding="utf-8")

    stmt_id, count = import_statement_csv(
        db=db,
        account_id=1,
        period_start=date(2025,1,1),
        period_end=date(2025,1,31),
        opening_bal=Decimal("1000.00"),
        closing_bal=Decimal("1050.00"),
        csv_path=str(csv_file),
    )
    assert count == 2

    stmt = db.get(Statement, stmt_id)
    assert stmt is not None
    lines = db.execute(select(StatementLine).where(StatementLine.statement_id == stmt.id)).scalars().all()
    assert len(lines) == 2
    stmt_id2, count2 = import_statement_csv(
        db=db,
        account_id=1,
        period_start=date(2025,1,1),
        period_end=date(2025,1,31),
        opening_bal=Decimal("1000.00"),
        closing_bal=Decimal("1050.00"),
        csv_path=str(csv_file),
    )
    assert stmt_id2 == stmt_id
    assert count2 == 0
