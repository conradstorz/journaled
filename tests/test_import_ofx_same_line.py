# tests/test_import_ofx_same_line.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from journaled_app.models import Account, AccountType, Statement, StatementLine
from journaled_app.services.import_ofx import import_ofx

# OFX where both <STMTTRN> are on one line / tightly packed tags
SAME_LINE_OFX = """
OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>
<BANKTRANLIST><DTSTART>20250101<DTEND>20250131
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20250106<TRNAMT>-50.00<FITID>sl-1<NAME>MERCHANT<MEMO>SUPPLIES</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20250107<TRNAMT>100.00<FITID>sl-2<NAME>REFUND</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>1050.00<DTASOF>20250131</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
""".strip()


def test_import_ofx_same_line_tags(tmp_path: Path, session_from_url):
    db = session_from_url

    # account
    acct = Account(name="Checking (same-line)", type=AccountType.ASSET)
    db.add(acct)
    db.commit()
    db.refresh(acct)

    # write file
    p = tmp_path / "same_line.ofx"
    p.write_text(SAME_LINE_OFX, encoding="utf-8")

    # first import (infer opening from closing - sum(period))
    stmt_id, count = import_ofx(
        db=db,
        account_id=acct.id,
        ofx_path=str(p),
        infer_opening=True,
    )
    assert count == 2

    # verify statement
    stmt = db.get(Statement, stmt_id)
    assert stmt is not None
    assert stmt.period_start == date(2025, 1, 1)
    assert stmt.period_end == date(2025, 1, 31)
    assert stmt.closing_bal == Decimal("1050.00")
    # opening = 1050 - (-50 + 100) = 1000
    assert stmt.opening_bal == Decimal("1000.00")

    # lines after first import
    lines1 = db.execute(
        select(StatementLine).where(StatementLine.statement_id == stmt_id)
    ).scalars().all()
    assert len(lines1) == 2
    amounts = sorted(l.amount for l in lines1)
    assert amounts == [Decimal("-50.00"), Decimal("100.00")]

    # second import of SAME file should be idempotent
    stmt_id2, count2 = import_ofx(
        db=db,
        account_id=acct.id,
        ofx_path=str(p),
        infer_opening=True,
    )
    assert stmt_id2 == stmt_id
    assert count2 == 0

    # still only two lines
    lines2 = db.execute(
        select(StatementLine).where(StatementLine.statement_id == stmt_id)
    ).scalars().all()
    assert len(lines2) == 2
    amounts2 = sorted(l.amount for l in lines2)
    assert amounts2 == [Decimal("-50.00"), Decimal("100.00")]
