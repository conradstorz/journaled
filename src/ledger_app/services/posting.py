# src/ledger_app/services/posting.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping, Sequence, List

from sqlalchemy.orm import Session

from ..models import Transaction, Split


class UnbalancedTransactionError(ValueError):
    """Raised when splits do not sum to zero."""


def post_transaction(db: Session, tx: Transaction, splits: Sequence[Split]) -> int:
    """
    Backward-compatible API expected by tests:

        post_transaction(db, tx, [Split(...), Split(...)])

    - Validates that the splits sum to zero.
    - Ensures the Transaction is persisted (id assigned).
    - Attaches splits to the transaction so transaction_id is NOT NULL.
    - Commits and returns the transaction id.
    """
    # --- validation ---
    total = sum((s.amount for s in splits), Decimal("0"))
    if total != Decimal("0"):
        raise UnbalancedTransactionError(f"Splits must sum to zero, got {total}")

    # --- ensure transaction has an id ---
    if getattr(tx, "id", None) is None:
        db.add(tx)
        db.flush()  # assign tx.id

    # --- attach and persist splits ---
    for s in splits:
        # If ORM relationship exists, prefer it:
        if hasattr(s, "transaction"):
            s.transaction = tx  # sets FK automatically when relationship is defined
        else:
            # Fallback in case relationship isn't mapped for some reason
            s.transaction_id = tx.id
        db.add(s)

    db.commit()
    return tx.id


# Optional: a convenience API that some code may prefer (kept here for future use).
def post_transaction_v2(
    db: Session,
    *,
    txn_date: date,
    description: str,
    entries: Sequence[Mapping],
) -> int:
    """
    Alternative API (NOT used by your current tests):

        post_transaction_v2(
            db,
            txn_date=today,
            description="Widget sale",
            entries=[
                {"account_id": 1, "amount": Decimal("100.00"), "memo": "..."},
                {"account_id": 2, "amount": Decimal("-100.00")},
            ],
        )

    Creates Transaction + Split rows and enforces balance.
    """
    total = sum((e["amount"] for e in entries), Decimal("0"))
    if total != Decimal("0"):
        raise UnbalancedTransactionError(f"Splits must sum to zero, got {total}")

    tx = Transaction(date=txn_date, description=description or "")
    db.add(tx)
    db.flush()  # assign tx.id

    for e in entries:
        db.add(
            Split(
                transaction_id=tx.id,  # works even if relationships weren’t declared
                account_id=e["account_id"],
                amount=e["amount"],
                memo=e.get("memo"),
            )
        )

    db.commit()
    return tx.id
