from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from ledger_app.models import Transaction, Split
from ledger_app.services.posting import post_transaction
from datetime import date

def test_unbalanced_raises_in_service(session_from_url):
    db = session_from_url
    tx = Transaction(date=date.today(), description="Oops")
    s1 = Split(account_id=1, amount=Decimal("100.00"))
    s2 = Split(account_id=2, amount=Decimal("-90.00"))
    with pytest.raises(ValueError):
        post_transaction(db, tx, [s1, s2])

def test_duplicate_split_unique_constraint(session_from_url):
    db = session_from_url
    tx = Transaction(date=date.today(), description="Dup test")
    s1 = Split(account_id=1, amount=Decimal("100.00"), memo="A")
    s2 = Split(account_id=2, amount=Decimal("-100.00"), memo="B")
    post_transaction(db, tx, [s1, s2])
    db.commit()
    dup = Split(transaction_id=tx.id, account_id=s1.account_id, amount=s1.amount, memo=s1.memo)
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
