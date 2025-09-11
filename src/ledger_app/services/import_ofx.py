from __future__ import annotations
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, Iterable, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session
from loguru import logger

from ..models import Statement, StatementLine

OFX_TXN_BLOCK_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.DOTALL | re.IGNORECASE)

def _parse_datetime(raw: str) -> date:
    ds = raw.strip()[:8]
    return datetime.strptime(ds, "%Y%m%d").date()

def _extract_tag(block: str, tag: str) -> str | None:
    pattern = re.compile(rf"<{tag}>([\s\S]*?)(?=\r?\n<|$)", re.IGNORECASE)
    m = pattern.search(block)
    return m.group(1).strip() if m else None

def _iter_stmttrn(ofx_text: str):
    for m in OFX_TXN_BLOCK_RE.finditer(ofx_text):
        block = m.group(1)
        dt = _extract_tag(block, "DTPOSTED")
        amt = _extract_tag(block, "TRNAMT")
        fitid = _extract_tag(block, "FITID")
        name = _extract_tag(block, "NAME") or ""
        memo = _extract_tag(block, "MEMO") or ""
        desc = (name + " " + memo).strip() or name or memo
        if not dt or not amt:
            continue
        yield {
            "posted_date": _parse_datetime(dt),
            "amount": Decimal(amt.replace(",", "")),
            "fitid": (fitid or "").strip() or None,
            "description": desc[:255],
        }

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

