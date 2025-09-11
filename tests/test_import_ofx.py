# tests/test_import_ofx.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from ledger_app.models import Account, AccountType, Statement, StatementLine
from ledger_app.services.import_ofx import import_ofx

SIMPLE_OFX = """
OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <BANKTRANLIST>
          <DTSTART>20250101<DTEND>20250131
          <STMTTRN>
            <TRNTYPE>DEBIT
            <DTPOSTED>20250106
            <TRNAMT>-50.00
            <FITID>fit-001
            <NAME>MERCHANT A
            <MEMO>SUPPLIES
          </STMTTRN>
          <STMTTRN>
            <TRNTYPE>CREDIT
            <DTPOSTED>20250107
            <TRNAMT>100.00
            <FITID>fit-002
            <NAME>REFUND
          </STMTTRN>
        </BANKTRANLIST>
        <LEDGERBAL><BALAMT>1050.00<DTASOF>20250131</LEDGERBAL>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
""".strip()


def test_import_ofx(tmp_path: Path, session_from_url):
    db = session_from_url

    # Ensure an account exists
    acct = Account(name="Checking", type=AccountType.ASSET)
    db.add(acct)
    db.commit()
    db.refresh(acct)

    # Write OFX to a temp file
    ofx_file = tmp_path / "sample.ofx"
    ofx_file.write_text(SIMPLE_OFX, encoding="utf-8")

    # First import
    stmt_id, count = import_ofx(
        db=db,
        account_id=acct.id,
        ofx_path=str(ofx_file),
        infer_opening=True,  # derive opening = closing - sum(period txns)
    )
    assert count == 2

    # Validate statement properties
    stmt = db.get(Statement, stmt_id)
    assert stmt is not None
    assert stmt.account_id == acct.id
    assert stmt.period_start == date(2025, 1, 1)
    assert stmt.period_end == date(2025, 1, 31)
    # closing from <LEDGERBAL>, opening inferred: 1050 - (-50 + 100) = 1000
    assert stmt.closing_bal == Decimal("1050.00")
    assert stmt.opening_bal == Decimal("1000.00")

    # Validate lines
    lines = db.execute(
        select(StatementLine).where(StatementLine.statement_id == stmt.id)
    ).scalars().all()
    assert len(lines) == 2
    amounts = sorted(l.amount for l in lines)
    assert amounts == [Decimal("-50.00"), Decimal("100.00")]

    # Second import of the same file should be idempotent:
    # - FITID-based dedupe prevents duplicates
    stmt_id_2, count_2 = import_ofx(
        db=db,
        account_id=acct.id,
        ofx_path=str(ofx_file),
        infer_opening=True,
    )
    assert stmt_id_2 == stmt_id
    assert count_2 == 0
