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

_STMTTRN_OPEN_RE = re.compile(r"<STMTTRN>", re.IGNORECASE)
_STMTTRN_CLOSE_RE = re.compile(r"</STMTTRN>", re.IGNORECASE)

def _iter_stmttrn_blocks(text: str):
    """
    Yield the inner text of each STMTTRN block.
    Works for both:
      - <STMTTRN> ... </STMTTRN>
      - <STMTTRN> ... <STMTTRN> (implicit close at the next open)
    """
    pos = 0
    while True:
        m_open = _STMTTRN_OPEN_RE.search(text, pos)
        if not m_open:
            break
        start = m_open.end()

        # Prefer a proper closing tag if present
        m_close = _STMTTRN_CLOSE_RE.search(text, start)
        m_next_open = _STMTTRN_OPEN_RE.search(text, start)

        if m_close and (not m_next_open or m_close.start() <= m_next_open.start()):
            end = m_close.start()
            pos = m_close.end()
        else:
            # No close tag before the next open; treat the next open as the boundary
            end = m_next_open.start() if m_next_open else len(text)
            pos = end

        yield text[start:end]



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


def _iter_stmttrn(ofx_text: str):
    """
    Yield normalized transactions from STMTTRN blocks with:
      posted_date (date), amount (Decimal), fitid (str|None), description (str)
    """
    for block in _iter_stmttrn_blocks(ofx_text):
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
    """Import an OFX/QFX file into statements and statement lines.

    Returns (statement_id, inserted_count).
    """
    with open(ofx_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    txns = list(_iter_stmttrn(text))
    if not txns:
        logger.warning("No transactions found in OFX file %s", ofx_path)
        # still create a statement if period_start/end provided
        if not (period_start and period_end):
            return -1, 0

    if not period_start or not period_end:
        dates = [t["posted_date"] for t in txns]
        if dates:
            period_start = min(dates)
            period_end = max(dates)
        else:
            raise ValueError("No transactions and no explicit period provided")

    stmt = Statement(
        account_id=account_id,
        period_start=period_start,
        period_end=period_end,
        opening_balance=opening_bal,
        closing_balance=closing_bal,
    )
    db.add(stmt)
    db.flush()  # get stmt.id

    # Insert lines with de-duplication and period filter
    inserted = 0
    seen_no_fitid: set[tuple[date, Decimal, str]] = set()

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
