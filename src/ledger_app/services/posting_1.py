from decimal import Decimal
from sqlalchemy.orm import Session
from loguru import logger
from ..models import Transaction, Split

def post_transaction(db: Session, tx: Transaction, splits: list[Split]) -> Transaction:
    """
    Create a transaction with splits, enforcing double-entry.
    Amount convention: positive = credit, negative = debit (or the reverse, as long as consistent system-wide).
    """
    total = sum(Decimal(s.amount) for s in splits)
    if total != Decimal("0"):
        logger.error(f"Unbalanced transaction attempt: total={total} desc={tx.description}")
        raise ValueError(f"Unbalanced transaction: total={total}")
    db.add(tx)
    for s in splits:
        s.transaction_id = tx.id
        db.add(s)
    db.flush()
    logger.info(f"Posted transaction id={tx.id} with {len(splits)} splits.")
    return tx
