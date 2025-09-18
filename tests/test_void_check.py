from datetime import date
from decimal import Decimal
from journaled_app.models import Transaction, Split, Check, CheckStatus, Account
from journaled_app.services.posting import post_transaction
from journaled_app.services.checks import void_check

def test_void_check_creates_reversal(cloned_test_db):
    import uuid
    db = cloned_test_db
    # Generate unique account names
    unique_name1 = f"Cash_{uuid.uuid4().hex[:8]}"
    unique_name2 = f"Expenses_{uuid.uuid4().hex[:8]}"

    # Verify accounts do not exist
    assert db.query(Account).filter_by(name=unique_name1).count() == 0
    assert db.query(Account).filter_by(name=unique_name2).count() == 0

    # Create accounts
    account1 = Account(name=unique_name1, type="ASSET", is_active=True)
    account2 = Account(name=unique_name2, type="EXPENSE", is_active=True)
    db.add_all([account1, account2])
    db.flush()  # assign IDs

    # Verify creation
    assert db.query(Account).filter_by(name=unique_name1).count() == 1
    assert db.query(Account).filter_by(name=unique_name2).count() == 1

    tx = Transaction(date=date.today(), description="Check payment")
    s1 = Split(account_id=account1.id, amount=Decimal("-250.00"), memo="Cash out")
    s2 = Split(account_id=account2.id, amount=Decimal("250.00"), memo="Expense")
    post_transaction(db, tx, [s1, s2])
    db.commit()

    chk = Check(account_id=account1.id, check_number="1001", issue_date=date.today(), payee=None, amount=Decimal("250.00"), memo_line="X")
    db.add(chk)
    db.commit()

    void_check(db, chk.id, date.today(), "Voiding test", create_reversal=True)
    refreshed = db.get(Check, chk.id)
    assert refreshed.status == CheckStatus.VOID

    # Delete related splits before deleting accounts
    db.query(Split).filter(Split.account_id.in_([account1.id, account2.id])).delete(synchronize_session=False)
    db.commit()

    db.delete(account1)
    db.delete(account2)
    db.commit()

    # Verify deletion
    assert db.query(Account).filter_by(name=unique_name1).count() == 0
    assert db.query(Account).filter_by(name=unique_name2).count() == 0
