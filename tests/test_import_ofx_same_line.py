# tests/test_import_ofx_same_line.py
from datetime import date
from decimal import Decimal
from pathlib import Path
from sqlalchemy import select
from ledger_app.models import Statement, StatementLine
from ledger_app.services.import_ofx import import_ofx

OFX_SAME_LINE = """
OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <BANKTRANLIST>
          <DTSTART>20250101<DTEND>20250131
          <STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20250106<TRNAMT>-50.00<FITID>sl-1<NAME>MERCHANT<MEMO>SUPPLIES</STMTTRN>
          <STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20250107<TRNAMT>  100.00  <FITID>sl-2<NAME>REFUND</STMTTRN>
        </BANKTRANLIST>
        <LEDGERBAL><BALAMT>1050.00<DTASOF>20250131</LEDGERBAL>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
"""

def test_import_ofx_same_line_tags(tmp_path, session_from_url):
    db = session_from_url
    f = tmp_path / "same_line.ofx"
    f.write_text(OFX_SAME_LINE, encoding="utf-8")

    stmt_id, count = import_ofx(
        db=db,
        account_id=1,
        ofx_path=str(f),
        infer_opening=True,
    )
    # ✅ Two lines should import successfully
    assert count == 2

    stmt = db.get(Statement, stmt_id)
    # ✅ Period auto-detected from <DTSTART>/<DTEND>
    assert stmt.period_start == date(2025, 1, 1)
    assert stmt.period_end == date(2025, 1, 31)
    # ✅ Closing balance read from <LEDGERBAL>
    assert stmt.closing_bal == Decimal("1050.00")
    # ✅ Opening inferred = 1050 - (-50 + 100) = 1000
    assert stmt.opening_bal == Decimal("1000.00")

    # ✅ Check imported amounts
    lines = db.execute(
        select(StatementLine).where(StatementLine.statement_id == stmt.id)
    ).scalars().all()
    amounts = sorted([l.amount for l in lines])
    assert amounts == [Decimal("-50.00"), Decimal("100.00")]
