from __future__ import annotations
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
"""
def _parse_ofx_date(raw: str) -> date:
    # '20250107120000[-5:EST]' -> 2025-01-07
    return datetime.strptime(raw.strip()[:8], "%Y%m%d").date()

# if your code refers to _parse_datetime, alias it:
_parse_datetime = _parse_ofx_date
"""
from pathlib import Path
from typing import Optional, Iterable, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session
from loguru import logger

from ..models import Statement, StatementLine


# --- Tolerant Decimal parser for TRNAMT ---
def _safe_decimal(raw: str) -> Optional[Decimal]:
    s = (raw or "").strip().replace(",", "")
    if s.endswith("-") and len(s) > 1:
        s = "-" + s[:-1]
    s = re.sub(r"[^0-9.\-+]", "", s)  # drop currency symbols/strays
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None

OFX_TXN_BLOCK_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.DOTALL | re.IGNORECASE)
# --- STMTTRN block iterator (works with and without explicit </STMTTRN>) ---
_STMTTRN_OPEN_RE = re.compile(r"<STMTTRN>", re.IGNORECASE)
_STMTTRN_CLOSE_RE = re.compile(r"</STMTTRN>", re.IGNORECASE)

def _parse_datetime(raw: str) -> date:
    ds = raw.strip()[:8]
    return datetime.strptime(ds, "%Y%m%d").date()

# --- OFX date helpers ---
def _parse_ofx_date(raw: str) -> date:
    # OFX dates always start with YYYYMMDD; ignore time/zone suffixes
    return datetime.strptime(raw.strip()[:8], "%Y%m%d").date()

def _closing_from_ofx(ofx_text: str) -> Optional[Decimal]:
    # Prefer value inside <LEDGERBAL>…</LEDGERBAL>
    m = re.search(r"<LEDGERBAL>(.*?)</LEDGERBAL>", ofx_text, re.IGNORECASE | re.DOTALL)
    if m:
        bal = _extract_tag(m.group(1), "BALAMT")
        if bal:
            v = _safe_decimal(bal)
            if v is not None:
                return v
    # Fallback to first <BALAMT> anywhere
    bal_any = _extract_tag(ofx_text, "BALAMT")
    if bal_any:
        v = _safe_decimal(bal_any)
        if v is not None:
            return v
    return None

def _period_from_ofx(ofx_text: str) -> Tuple[Optional[date], Optional[date]]:
    start = _extract_tag(ofx_text, "DTSTART")
    end = _extract_tag(ofx_text, "DTEND")
    ps = _parse_ofx_date(start) if start else None
    pe = _parse_ofx_date(end) if end else None
    return ps, pe

# --- Robust tag extractor (handles SGML-style tags without explicit closing) ---
def _extract_tag(text: str, tag: str) -> Optional[str]:
    """
    Return the text immediately following <TAG> up until the next '<'.
    Works for OFX SGML where tags may not be closed (e.g., <DTPOSTED>20250107).
    """
    m = re.search(rf"<{tag}>\s*([^<\r\n]+)", text, re.IGNORECASE)
    return m.group(1).strip() if m else None

def _iter_stmttrn(ofx_text: str):
    """
    Yield dicts: {posted_date: date, amount: Decimal, fitid: str|None, description: str}
    Skips rows with malformed DTPOSTED/TRNAMT.
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

        amount = _safe_decimal(amt)
        if amount is None:
            logger.warning(f"Skipping malformed TRNAMT: {amt!r}")
            continue

        try:
            posted = _parse_ofx_date(dt)
        except Exception:
            logger.warning(f"Skipping malformed DTPOSTED: {dt!r}")
            continue

        yield {
            "posted_date": posted,
            "amount": amount,
            "fitid": (fitid or "").strip() or None,
            "description": desc[:255],
        }

def _iter_stmttrn_blocks(text: str) -> Iterable[str]:
    pos = 0
    while True:
        m_open = _STMTTRN_OPEN_RE.search(text, pos)
        if not m_open:
            break
        start = m_open.end()
        m_close = _STMTTRN_CLOSE_RE.search(text, start)
        m_next_open = _STMTTRN_OPEN_RE.search(text, start)
        if m_close and (not m_next_open or m_close.start() <= m_next_open.start()):
            end = m_close.start()
            pos = m_close.end()
        else:
            end = m_next_open.start() if m_next_open else len(text)
            pos = end
        yield text[start:end]

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

