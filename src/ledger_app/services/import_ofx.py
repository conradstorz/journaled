# src/ledger_app/services/import_ofx.py
from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional, Tuple, Set

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Statement, StatementLine


# -------------------------
# Parsing utilities
# -------------------------

TAG_VALUE = re.compile(r"<(?P<tag>[A-Za-z0-9_]+)>\s*([^<\r\n]+)", re.IGNORECASE)

def _extract_tag(text: str, tag: str) -> Optional[str]:
    """
    Return the text immediately following <TAG> up until the next '<'.
    Works for OFX/QFX SGML where tags may not be explicitly closed.
    """
    m = re.search(rf"<{tag}>\s*([^<\r\n]+)", text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _normalize_description(s: str) -> str:
    """Normalize description to make dedupe stable."""
    return re.sub(r"\s+", " ", (s or "").strip())


def _safe_decimal(raw: str) -> Optional[Decimal]:
    """
    Parse TRNAMT robustly:
    - strip spaces
    - remove thousands separators
    - handle trailing minus (e.g., '50.00-')
    - allow leading +/-
    Returns Decimal or None if not parseable.
    """
    if not raw:
        return None
    s = raw.strip().replace(",", "")
    if s.endswith("-") and len(s) > 1:
        s = "-" + s[:-1]
    s = re.sub(r"[^0-9.\-+]", "", s)
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _parse_ofx_date(raw: str) -> date:
    """OFX dates start with YYYYMMDD; ignore time/zone suffixes."""
    return datetime.strptime(raw.strip()[:8], "%Y%m%d").date()


def _period_from_ofx(ofx_text: str) -> Tuple[Optional[date], Optional[date]]:
    start = _extract_tag(ofx_text, "DTSTART")
    end = _extract_tag(ofx_text, "DTEND")
    ps = _parse_ofx_date(start) if start else None
    pe = _parse_ofx_date(end) if end else None
    return ps, pe


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


# -------------------------
# STMTTRN iteration
# -------------------------

_STMTTRN_OPEN_RE = re.compile(r"<STMTTRN>", re.IGNORECASE)
_STMTTRN_CLOSE_RE = re.compile(r"</STMTTRN>", re.IGNORECASE)

def _iter_stmttrn_blocks(text: str) -> Iterable[str]:
    """
    Yield inner text for each STMTTRN block.
    Works with closed </STMTTRN> and SGML-style unclosed blocks.
    """
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
        desc = _normalize_description((name + " " + memo).strip() or name or memo)

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


# -------------------------
# Statement helper
# -------------------------

def _get_or_create_statement(
    db: Session,
    *,
    account_id: int,
    period_start: date,
    period_end: date,
    opening_bal: Decimal,
    closing_bal: Decimal,
) -> Statement:
    """
    Re-use existing statement by (account_id, period_start, period_end), or create one.
    """
    existing = db.execute(
        select(Statement).where(
            Statement.account_id == account_id,
            Statement.period_start == period_start,
            Statement.period_end == period_end,
        )
    ).scalar_one_or_none()

    if existing:
        updated = False
        if existing.opening_bal is None:
            existing.opening_bal = opening_bal
            updated = True
        if existing.closing_bal is None:
            existing.closing_bal = closing_bal
            updated = True
        if updated:
            db.add(existing)
            db.flush()
        return existing

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


# -------------------------
# Public entry point
# -------------------------


# -------------------------
# Helper functions for import_ofx
# -------------------------
def _determine_statement_period(txns, text, period_start, period_end):
    """
    Determine the statement period using provided arguments, OFX tags, or transaction dates.
    """
    # If period_start and period_end are not both provided, try to extract from OFX tags
    if not (period_start and period_end):
        ps, pe = _period_from_ofx(text)
        period_start = period_start or ps
        period_end = period_end or pe
    # If still missing, infer from transaction dates (fallback)
    if not (period_start and period_end):
        if txns:
            dates = [t["posted_date"] for t in txns]
            period_start, period_end = min(dates), max(dates)
        else:
            # No transactions and no period info: cannot proceed
            raise ValueError("Statement period is required (DTSTART/DTEND or explicit args).")
    return period_start, period_end

def _determine_balances(txns, text, period_start, period_end, opening_bal, closing_bal, infer_opening):
    """
    Determine opening and closing balances, inferring opening if requested.
    """
    # If closing balance not provided, try to extract from OFX
    if closing_bal is None:
        closing_bal = _closing_from_ofx(text)

    # If opening balance is not provided, but infer_opening is set, calculate it
    if opening_bal is None and infer_opening:
        if closing_bal is None:
            # Cannot infer opening without a closing balance
            raise ValueError("Cannot infer opening balance without a closing balance.")
        # Sum all transaction amounts within the statement period
        period_sum = sum(
            (t["amount"] for t in txns if period_start <= t["posted_date"] <= period_end),
            Decimal("0"),
        )
        # Opening = closing - sum(period txns)
        opening_bal = closing_bal - period_sum

    # Both balances must be present at this point
    if opening_bal is None or closing_bal is None:
        raise ValueError(
            "opening_bal and closing_bal are required (or set infer_opening=True with a closing balance)."
        )
    return opening_bal, closing_bal

def _prepare_deduplication_sets(db, stmt):
    """
    Prepare sets of FITIDs and (date, amount, description) triples already present for this statement.
    """
    # Set of FITIDs already present in DB for this statement (for fast dedupe)
    existing_fitids: Set[str] = {
        fid for (fid,) in db.execute(
            select(StatementLine.fitid).where(
                StatementLine.statement_id == stmt.id,
                StatementLine.fitid.is_not(None),
            )
        )
        if fid is not None
    }
    # Set of (date, amount, description) triples already present (for fallback dedupe)
    existing_triples: Set[tuple[date, Decimal, str]] = {
        (pd, amt, desc) for (pd, amt, desc) in db.execute(
            select(
                StatementLine.posted_date,
                StatementLine.amount,
                StatementLine.description,
            ).where(StatementLine.statement_id == stmt.id)
        )
    }
    return existing_fitids, existing_triples

def _import_statement_lines(db, stmt, txns, period_start, period_end, existing_fitids, existing_triples):
    """
    Insert new StatementLine records for transactions within the statement period, avoiding duplicates.
    Returns the number of inserted records.
    """
    inserted = 0
    # Track FITIDs and triples seen in this import batch (to avoid in-batch dupes)
    seen_fitids: Set[str] = set()
    seen_no_fitid: Set[tuple[date, Decimal, str]] = set()

    # Log all parsed transactions for debugging
    logger.debug(
        "txns parsed: {}",
        [(t["fitid"], t["posted_date"], t["amount"], t["description"]) for t in txns],
    )

    # Main import loop: insert new StatementLines
    for trn in txns:
        # Only import transactions within the statement period
        if not (period_start <= trn["posted_date"] <= period_end):
            continue

        fitid = trn["fitid"]
        triple = (trn["posted_date"], trn["amount"], trn["description"])

        # In-batch deduplication: skip if already seen in this batch
        if fitid:
            if fitid in seen_fitids:
                continue
            seen_fitids.add(fitid)
        else:
            if triple in seen_no_fitid:
                continue
            seen_no_fitid.add(triple)

        # DB snapshot deduplication (for this statement):
        if fitid:
            # Primary dedupe: skip if FITID already in DB
            if fitid in existing_fitids:
                continue
            # Fallback: skip if triple already in DB (handles FITID changes)
            if triple in existing_triples:
                continue
        else:
            # If no FITID, dedupe only by triple
            if triple in existing_triples:
                continue

        # Passed all dedupe checks: insert new StatementLine
        db.add(
            StatementLine(
                statement_id=stmt.id,
                posted_date=trn["posted_date"],
                amount=trn["amount"],
                description=trn["description"],
                fitid=fitid,
            )
        )
        inserted += 1

        # Update dedupe sets so subsequent txns in this batch see this one
        if fitid:
            existing_fitids.add(fitid)
        existing_triples.add(triple)

    return inserted

# -------------------------
# Public entry point
# -------------------------
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
    Import OFX/QFX into Statement + StatementLine.
    Returns (statement_id, inserted_count).
    """
    # Read the OFX/QFX file as text (ignore encoding errors)
    text = Path(ofx_path).read_text(encoding="utf-8", errors="ignore")
    # Parse all transaction blocks from the OFX text
    txns = list(_iter_stmttrn(text))

    # Determine the statement period
    period_start, period_end = _determine_statement_period(txns, text, period_start, period_end)

    # Determine opening and closing balances
    opening_bal, closing_bal = _determine_balances(txns, text, period_start, period_end, opening_bal, closing_bal, infer_opening)

    # Get or create the Statement record (idempotent)
    stmt = _get_or_create_statement(
        db=db,
        account_id=account_id,
        period_start=period_start,
        period_end=period_end,
        opening_bal=opening_bal,
        closing_bal=closing_bal,
        )

    # Prepare deduplication sets for this statement
    existing_fitids, existing_triples = _prepare_deduplication_sets(db, stmt)

    # Insert new StatementLines, avoiding duplicates
    inserted = _import_statement_lines(db, stmt, txns, period_start, period_end, existing_fitids, existing_triples)

    # Commit all new StatementLines to the database
    db.commit()
    # Return the statement ID and the number of new lines inserted
    return stmt.id, inserted
