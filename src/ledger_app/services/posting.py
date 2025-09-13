# src/ledger_app/services/posting.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping, Sequence

from sqlalchemy.orm import Session

from ..models import Transaction, Split


class UnbalancedTransactionError(ValueError):
    """Raised when splits do not sum to zero."""


def post_transaction(
    db: Session,
    *,
    txn_date: date,
    description: str,
    entries: Sequence[Mapping],
) -> int:
    """
    Create a transaction with splits and enforce double-entry balance.

    entries: a list of dicts like:
      {"account_id": 1, "amount": Decimal("100.00"), "memo": "optional"}
      amounts can be positive or negative; sum must be zero.

    Returns the transaction id.
    """
    # Validate balanced
    total = sum((e["amount"] for e in entries), Decimal("0"))
    if total != Decimal("0"):
        raise UnbalancedTransactionError(f"Splits must sum to zero, got {total}")

    txn = Transaction(date=txn_date, description=description or "")
    # Attach splits via relationship so transaction_id is set automatically
    for e in entries:
        txn.splits.append(
            Split(
                account_id=e["account_id"],
                amount=e["amount"],
                memo=e.get("memo"),
            )
        )

    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn.id



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
