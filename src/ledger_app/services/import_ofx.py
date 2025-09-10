from __future__ import annotations
import re
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Tuple

from decimal import Decimal, InvalidOperation
from sqlalchemy import select
from sqlalchemy.orm import Session
from loguru import logger

from ..models import Statement, StatementLine

def _parse_ofx_date(raw: str) -> date:
    # OFX dates are like 20250107120000[-5:EST]; we only need YYYYMMDD
    return datetime.strptime(raw.strip()[:8], "%Y%m%d").date()

OFX_TXN_BLOCK_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.DOTALL | re.IGNORECASE)
LEDGERBAL_BLOCK_RE = re.compile(r"<LEDGERBAL>(.*?)</LEDGERBAL>", re.DOTALL | re.IGNORECASE)

def _extract_tag(text: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}>\s*([^<]+)", text, re.IGNORECASE)
    return m.group(1).strip() if m else None

def _closing_from_ofx(text: str) -> Decimal | None:
    m = LEDGERBAL_BLOCK_RE.search(text)
    if m:
        balamt = _extract_tag(m.group(1), "BALAMT")
        if balamt:
            try:
                return Decimal(balamt.replace(",", ""))
            except Exception:
                pass
    bal_fallback = _extract_tag(text, "BALAMT")
    if bal_fallback:
        try:
            return Decimal(bal_fallback.replace(",", ""))
        except Exception:
            return None
    return None

def _parse_datetime(raw: str) -> date:
    ds = raw.strip()[:8]
    return datetime.strptime(ds, "%Y%m%d").date()

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

        # NEW: safer Decimal parsing
        raw_amt = amt.replace(",", "").strip()
        try:
            amount = Decimal(raw_amt)
        except InvalidOperation:
            # Skip malformed amounts rather than crashing
            logger.warning(f"Skip malformed TRNAMT: {raw_amt!r}")
            continue

        yield {
            "posted_date": _parse_ofx_date(dt),
            "amount": amount,
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
    account_id: int,
    period_start: date,
    period_end: date,
    opening_bal: Decimal,
    closing_bal: Decimal,
    ofx_path: str,
) -> Tuple[int, int]:
    path = Path(ofx_path)
    if not path.exists():
        raise FileNotFoundError(ofx_path)

    text = path.read_text(encoding="utf-8", errors="ignore")
    stmt = _get_or_create_statement(db, account_id, period_start, period_end, opening_bal, closing_bal)

    inserted = 0
    for trn in _iter_stmttrn(text):
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
            dup = db.execute(
                select(StatementLine).where(
                    StatementLine.statement_id == stmt.id,
                    StatementLine.posted_date == trn["posted_date"],
                    StatementLine.amount == trn["amount"],
                    StatementLine.description == trn["description"],
                )
            ).scalar_one_or_none()
            if dup:
                continue

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
