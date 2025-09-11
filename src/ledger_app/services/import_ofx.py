from sqlalchemy.orm import Session
from decimal import Decimal, InvalidOperation
from pathlib import Path
from datetime import date, datetime
from typing import Optional, Tuple
from sqlalchemy import select
from loguru import logger


def import_ofx(
    db: Session,
    *,
    account_id: int,
    ofx_path: str,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    opening_bal: Optional[Decimal] = None,
    closing_bal: Optional[Decimal] = None,
    infer_opening: bool = False,
) -> Tuple[int, int]:
    """Import OFX/QFX and return (statement_id, inserted_count)."""
    path = Path(ofx_path)
    if not path.exists():
        raise FileNotFoundError(ofx_path)

    text = path.read_text(encoding="utf-8", errors="ignore")
    txns = list(_iter_stmttrn(text))

    # Determine period
    if not (period_start and period_end):
        ps, pe = _period_from_ofx(text)
        period_start = period_start or ps
        period_end = period_end or pe
    if not (period_start and period_end):
        # as a fallback (no DTSTART/DTEND), derive from txn dates if any
        if txns:
            dates = [t["posted_date"] for t in txns]
            period_start = min(dates)
            period_end = max(dates)
        else:
            raise ValueError("Statement period is required (DTSTART/DTEND or explicit arguments).")

    # Determine balances
    if closing_bal is None:
        closing_bal = _closing_from_ofx(text)

    if opening_bal is None and infer_opening:
        if closing_bal is None:
            raise ValueError(
                "Cannot infer opening balance without a closing balance (provide closing_bal or include <LEDGERBAL><BALAMT>)."
            )
        period_sum = sum(
            (t["amount"] for t in txns if period_start <= t["posted_date"] <= period_end),
            Decimal("0"),
        )
        opening_bal = closing_bal - period_sum

    if opening_bal is None or closing_bal is None:
        raise ValueError(
            "opening_bal and closing_bal are required (or set infer_opening=True with a closing balance present)."
        )

    # Get or create the Statement (idempotent across imports)
    stmt = _get_or_create_statement(
        db=db,
        account_id=account_id,
        period_start=period_start,
        period_end=period_end,
        opening_bal=opening_bal,
        closing_bal=closing_bal,
    )

    # Insert lines with dedupe:
    # - If FITID present → dedupe against DB by FITID
    # - If FITID missing → dedupe only within this batch (avoid blocking due to other importers)
    inserted = 0
    seen_no_fitid: set[tuple[date, Decimal, str]] = set()

    for trn in txns:
        if not (period_start <= trn["posted_date"] <= period_end):
            continue

        if trn["fitid"]:
            dup = db.execute(
                select(StatementLine).where(
                    StatementLine.statement_id == stmt.id,
                    StatementLine.fitid == trn["fitid"],
                )
            ).scalar_one_or_none()
            if dup:
                continue
        else:
            key = (trn["posted_date"], trn["amount"], trn["description"])
            if key in seen_no_fitid:
                continue
            seen_no_fitid.add(key)

        line = StatementLine(
            statement_id=stmt.id,
            posted_date=trn["posted_date"],
            amount=trn["amount"],
            description=trn["description"],
            fitid=trn["fitid"],
        )
        db.add(line)
        inserted += 1

    db.commit()
    return stmt.id, inserted
