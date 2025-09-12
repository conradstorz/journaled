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
    text = Path(ofx_path).read_text(encoding="utf-8", errors="ignore")
    txns = list(_iter_stmttrn(text))

    # Determine statement period
    if not (period_start and period_end):
        ps, pe = _period_from_ofx(text)
        period_start = period_start or ps
        period_end = period_end or pe
    if not (period_start and period_end):
        if txns:
            dates = [t["posted_date"] for t in txns]
            period_start, period_end = min(dates), max(dates)
        else:
            raise ValueError("Statement period is required (DTSTART/DTEND or explicit args).")

    # Balances
    if closing_bal is None:
        closing_bal = _closing_from_ofx(text)

    if opening_bal is None and infer_opening:
        if closing_bal is None:
            raise ValueError("Cannot infer opening balance without a closing balance.")
        period_sum = sum(
            (t["amount"] for t in txns if period_start <= t["posted_date"] <= period_end),
            Decimal("0"),
        )
        opening_bal = closing_bal - period_sum

    if opening_bal is None or closing_bal is None:
        raise ValueError(
            "opening_bal and closing_bal are required (or set infer_opening=True with a closing balance)."
        )

    # Get/create statement (idempotent)
    stmt = _get_or_create_statement(
        db=db,
        account_id=account_id,
        period_start=period_start,
        period_end=period_end,
        opening_bal=opening_bal,
        closing_bal=closing_bal,
    )

    # Snapshot what's already present for this statement (fast dedupe)
    existing_fitids: Set[str] = {
        fid for (fid,) in db.execute(
            select(StatementLine.fitid).where(
                StatementLine.statement_id == stmt.id,
                StatementLine.fitid.is_not(None),
            )
        )
        if fid is not None
    }
    existing_triples: Set[tuple[date, Decimal, str]] = {
        (pd, amt, desc) for (pd, amt, desc) in db.execute(
            select(
                StatementLine.posted_date,
                StatementLine.amount,
                StatementLine.description,
            ).where(StatementLine.statement_id == stmt.id)
        )
    }

    inserted = 0
    seen_fitids: Set[str] = set()
    seen_no_fitid: Set[tuple[date, Decimal, str]] = set()

    logger.debug(
        "txns parsed: {}",
        [(t["fitid"], t["posted_date"], t["amount"], t["description"]) for t in txns],
    )

    for trn in txns:
        # Period guard
        if not (period_start <= trn["posted_date"] <= period_end):
            continue

        fitid = trn["fitid"]
        triple = (trn["posted_date"], trn["amount"], trn["description"])

        # In-batch dedupe
        if fitid:
            if fitid in seen_fitids:
                continue
            seen_fitids.add(fitid)
        else:
            if triple in seen_no_fitid:
                continue
            seen_no_fitid.add(triple)

        # DB snapshot dedupe (same statement)
        if fitid:
            # primary: FITID
            if fitid in existing_fitids:
                continue
            # fallback: triple (guards against FITID variance across downloads)
            if triple in existing_triples:
                continue
        else:
            if triple in existing_triples:
                continue

        # Insert
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

        # update snapshots
        if fitid:
            existing_fitids.add(fitid)
        existing_triples.add(triple)

    db.commit()
    return stmt.id, inserted
