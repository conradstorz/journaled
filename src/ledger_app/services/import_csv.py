from __future__ import annotations
import csv
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session
from loguru import logger

from ..models import Statement, StatementLine

def _get_or_create_statement(
    db: Session,
    account_id: int,
    period_start: date,
    period_end: date,
    opening_bal: Decimal,
    closing_bal: Decimal,
) -> Statement:
    stmt = db.execute(
        select(Statement).where(
            Statement.account_id == account_id,
            Statement.period_start == period_start,
            Statement.period_end == period_end,
        )
    ).scalar_one_or_none()
    if stmt:
        if stmt.opening_bal is None:
            stmt.opening_bal = opening_bal
        if stmt.closing_bal is None:
            stmt.closing_bal = closing_bal
        db.add(stmt); db.flush()
        return stmt
    stmt = Statement(
        account_id=account_id,
        period_start=period_start,
        period_end=period_end,
        opening_bal=opening_bal,
        closing_bal=closing_bal,
    )
    db.add(stmt); db.flush()
    return stmt

def import_statement_csv(
    db: Session,
    account_id: int,
    period_start: date,
    period_end: date,
    opening_bal: Decimal,
    closing_bal: Decimal,
    csv_path: str,
    date_format: str = "%Y-%m-%d",
    has_header: bool = True,
    date_col: str = "date",
    amount_col: str = "amount",
    desc_col: str = "description",
    fitid_col: str = "fitid",
) -> Tuple[int, int]:
    stmt = _get_or_create_statement(db, account_id, period_start, period_end, opening_bal, closing_bal)

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(csv_path)

    inserted = 0
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh) if has_header else csv.reader(fh)
        for row in reader:
            if has_header:
                raw_date = row.get(date_col, "").strip()
                raw_amount = row.get(amount_col, "").replace(",", "").strip()
                raw_desc = row.get(desc_col, "").strip()
                raw_fitid = (row.get(fitid_col) or "").strip() or None
            else:
                raw_date = row[0].strip()
                raw_amount = row[1].replace(",", "").strip()
                raw_desc = row[2].strip() if len(row) > 2 else ""
                raw_fitid = row[3].strip() if len(row) > 3 else None

            posted_date = datetime.strptime(raw_date, date_format).date()
            amount = Decimal(raw_amount)

            if raw_fitid:
                dup = db.execute(
                    select(StatementLine).where(
                        StatementLine.statement_id == stmt.id,
                        StatementLine.fitid == raw_fitid,
                    )
                ).scalar_one_or_none()
                if dup:
                    logger.info(f"Skip duplicate by FITID: {raw_fitid}")
                    continue
            else:
                dup = db.execute(
                    select(StatementLine).where(
                        StatementLine.statement_id == stmt.id,
                        StatementLine.posted_date == posted_date,
                        StatementLine.amount == amount,
                        StatementLine.description == raw_desc,
                    )
                ).scalar_one_or_none()
                if dup:
                    logger.info("Skip duplicate by (date,amount,description)")
                    continue

            line = StatementLine(
                statement_id=stmt.id,
                posted_date=posted_date,
                amount=amount,
                description=raw_desc,
                fitid=raw_fitid,
            )
            db.add(line)
            inserted += 1

    db.commit()
    return stmt.id, inserted
