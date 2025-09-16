
# This test module verifies constraints and business rules for Split and Transaction models.
# It ensures that transactions are balanced and that unique constraints on splits are enforced.

from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError
from journaled_app.models import Transaction, Split
from journaled_app.services.posting import post_transaction
from datetime import date


def test_unbalanced_raises_in_service(cloned_test_db):
    """
    Test that posting an unbalanced transaction (sum of splits != 0)
    raises a ValueError in the service layer.
    """
    db = cloned_test_db
    # Create a transaction with two splits that do not balance
    tx = Transaction(date=date.today(), description="Oops")
    s1 = Split(account_id=1, amount=Decimal("100.00"))  # Credit
    s2 = Split(account_id=2, amount=Decimal("-90.00"))  # Debit (should be -100.00 to balance)
    # The post_transaction service should raise ValueError for unbalanced splits
    with pytest.raises(ValueError):
        post_transaction(db, tx, [s1, s2])


def test_duplicate_split_unique_constraint(cloned_test_db):
    """
    Test that adding a duplicate Split (same transaction_id and account_id)
    violates the unique constraint and raises an IntegrityError.
    """
    db = cloned_test_db
    # Create a balanced transaction with two splits
    tx = Transaction(date=date.today(), description="Dup test")
    s1 = Split(account_id=1, amount=Decimal("100.00"), memo="A")
    s2 = Split(account_id=2, amount=Decimal("-100.00"), memo="B")
    post_transaction(db, tx, [s1, s2])
    db.commit()
    # Attempt to add a duplicate split for the same transaction and account
    dup = Split(transaction_id=tx.id, account_id=s1.account_id, amount=s1.amount, memo=s1.memo)
    db.add(dup)
    # Committing should raise an IntegrityError due to unique constraint violation
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
