from datetime import date
from decimal import Decimal
from pathlib import Path
from sqlalchemy import select
from ledger_app.models import Statement, StatementLine
from ledger_app.services.import_ofx import import_ofx

OFX = """
OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <BANKTRANLIST>
          <STMTTRN>
            <TRNTYPE>DEBIT
            <DTPOSTED>20250106120000[-5:EST]
            <TRNAMT>-50.00
            <FITID>abc123
            <NAME>OFFICE SUPPLIES
          </STMTTRN>
          <STMTTRN>
            <TRNTYPE>CREDIT
            <DTPOSTED>20250107120000[-5:EST]
            <TRNAMT>100.00
            <FITID>def456
            <NAME>REFUND
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
"""

def test_import_ofx(tmp_path, session_from_url):
    db = session_from_url
    f = tmp_path / "sample.ofx"
    f.write_text(OFX, encoding="utf-8")

    stmt_id, count = import_ofx(
        db=db,
        account_id=1,
        period_start=date(2025,1,1),
        period_end=date(2025,1,31),
        opening_bal=Decimal("1000.00"),
        closing_bal=Decimal("1050.00"),
        ofx_path=str(f),
    )
    assert count == 2
    stmt = db.get(Statement, stmt_id)
    lines = db.execute(select(StatementLine).where(StatementLine.statement_id == stmt.id)).scalars().all()
    assert len(lines) == 2

    stmt_id2, count2 = import_ofx(
        db=db,
        account_id=1,
        period_start=date(2025,1,1),
        period_end=date(2025,1,31),
        opening_bal=Decimal("1000.00"),
        closing_bal=Decimal("1050.00"),
        ofx_path=str(f),
    )
    assert stmt_id2 == stmt_id
    assert count2 == 0
