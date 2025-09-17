# src/journaled_app/services/reversal.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select
from loguru import logger
from ..models import Transaction, Split, TransactionReversal
from .posting import post_transaction

def create_reversing_entry(db: Session, original_tx_id: int, reversal_date: date, memo: str | None = None) -> int:
    """Create a reversing transaction that negates all splits on the original transaction.
    Returns the new reversing transaction id.
    """
    existing = db.execute(
        select(TransactionReversal).where(TransactionReversal.original_tx_id == original_tx_id)
    ).scalar_one_or_none()
    if existing:
        logger.info(f"Transaction {original_tx_id} already reversed by {existing.reversing_tx_id}")
        return existing.reversing_tx_id

    orig_tx = db.get(Transaction, original_tx_id)
    if not orig_tx:
        raise ValueError(f"Original transaction {original_tx_id} not found")

    orig_splits = db.execute(select(Split).where(Split.transaction_id == original_tx_id)).scalars().all()
    if not orig_splits:
        raise ValueError("Original transaction has no splits to reverse")

    rev_tx = Transaction(
        date=reversal_date,
        description=(memo or f"Reversal of tx {original_tx_id}: {orig_tx.description}"),
        reference=f"REV-{original_tx_id}",
        party_id=orig_tx.party_id,
    )
    rev_splits = []
    for s in orig_splits:
        assert s.account_id is not None, f"Original split {s.id} has no account_id!"
        rev_split = Split(account_id=s.account_id, amount=Decimal(-s.amount), memo=f"Reversal of split {s.id}")
        assert rev_split.account_id is not None, f"Reversal split for original {s.id} has no account_id!"
        rev_splits.append(rev_split)

    post_transaction(db, rev_tx, rev_splits)
    db.flush()
    link = TransactionReversal(original_tx_id=original_tx_id, reversing_tx_id=rev_tx.id)
    db.add(link)
    db.commit()
    logger.success(f"Created reversing transaction {rev_tx.id} for original {original_tx_id}")
    return rev_tx.id
