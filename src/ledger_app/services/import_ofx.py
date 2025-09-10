from __future__ import annotations

import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Tuple, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from loguru import logger

from ..models import Statement, StatementLine


# ---- helpers -----------------------------------------------------------------

def _parse_ofx_date(raw: str) -> date:
    """OFX dates like 20250107120000[-5:EST] -> date(2025, 1, 7)."""
    return datetime.strptime(raw.strip()[:8], "%Y%m%d").date()


# Match transaction blocks anywhere (BANK or CREDIT CARD statements)
OFX_TXN_BLOCK_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.DOTALL | re.IGNORECASE)
# For closing balance extraction
LEDGERBAL_BLOCK_RE = re.compile(r"<LEDGERBAL>(.*?)</LEDGERBAL>", re.DOTALL | re.IGNORECASE)


def _extract_tag(text: str, tag: str) -> Optional[str]:
    """
    Tolerant SGML-ish tag extractor.
    Stops at the next '<' regardless of line breaks so it works when tags share a line.
    """
    m = re.search(rf"<{tag}>\s*([^<]+)", text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _period_from_ofx(text: str) -> tuple[Optional[date], Optional[date]]:
    dt_start = _extract_tag(text, "DTSTART")
    dt_end = _extract_tag(text, "DTEND")
    return (_parse_ofx_date(dt_start) if dt_start else None,
            _parse_ofx_date(dt_end) if dt_end else None)


def _closing_from_ofx(text: str) -> Optional[Decimal]:
    """
    Try <LEDGERBAL><BALAMT> first, then fall back to the first <BALAMT> seen.
    """
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


def _iter_stmttrn(ofx_text: str) -> Iterable[dict]:
    """
    Yield normalized transactions from <STMTTRN> blocks with:
      posted_date (date), amount (Decimal), fitid (str|None), description (str)
    """
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

        raw_amt = amt.replace(",", "").strip()
        try:
            amount = Decimal(raw_amt)
        except InvalidOperation:
            logger.warning(f"Skip malformed TRNAMT: {raw_amt!r}")
            continue

        yield {
            "posted_date": _parse_ofx_date(dt),
            "amount": amount,
            "fitid": (fitid or "").strip() or None,
            "description": desc[:255],
        }


# ---- persistence --------------------------------------------------------------

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
        # Set balances if missing (avoid accidental overwrite)
        if stmt.opening_bal is None:
            stmt.opening_bal = opening_bal
        if stmt.closing_bal is None:
            stmt.closing_bal = closing_bal
        db.add(stmt)
        db.flush()
        return stmt

    stmt = Statement(
        account_id=account_id,
        period_start=period_start,
        period_end=period_end,
        opening_bal=opening_bal,
        closing_bal=closing_bal,
    )
    db.add(stmt)
    db.flush()
    return stmt


# ---- main importer ------------------------------------------------------------

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
    """
    Import OFX/QFX (BANK or CREDIT CARD) into statement_lines.

    - If period_start/period_end not provided, tries to read from <DTSTART>/<DTEND>.
    - If closing_bal not provided, tries to read from <LEDGERBAL><BALAMT>.
    - If opening_bal not provided and infer_opening=True and closing known, computes:
          opening = closing - sum(all transaction amounts in period)

    Returns (statement_id, lines_inserted).
    """
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
        raise ValueError(
            "Statement period is required (provide period_start/period_end or include DTSTART/DTEND in OFX)."
        )

    # Determine closing
    if closing_bal is None:
        closing_bal = _closing_from_ofx(text)

    # Determine opening
    if opening_bal is None and infer_opening:
        if closing_bal is None:
            raise ValueError(
                "Cannot infer opening balance: closing balance not available "
                "(supply closing or ensure <LEDGERBAL><BALAMT> exists)."
            )
        period_sum = sum(
            (t["amount"] for t in txns if period_start <= t["posted_date"] <= period_end),
            Decimal("0"),
        )
        opening_bal = closing_bal - period_sum

    if opening_bal is None or closing_bal is None:
        raise ValueError(
            "Opening and closing balances are required "
            "(or set infer_opening=True with LEDGERBAL in the file)."
        )

    # Create or get the Statement
    stmt = _get_or_create_statement(db, account_id, period_start, period_end, opening_bal, closing_bal)

    # Insert lines with de-duplication and period filter
    inserted = 0
    for trn in txns:
        if trn["posted_date"] < period_start or trn["posted_date"] > period_end:
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
