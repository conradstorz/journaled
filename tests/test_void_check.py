from datetime import date
from decimal import Decimal
from ledger_app.models import Transaction, Split, Check, CheckStatus, Account
from ledger_app.services.posting import post_transaction
from ledger_app.services.checks import void_check

def test_void_check_creates_reversal(session_from_url):
    db = session_from_url
    # Create two accounts for the splits and check
    account1 = Account(name="Cash", type="ASSET", is_active=True)
    account2 = Account(name="Expenses", type="EXPENSE", is_active=True)
    db.add_all([account1, account2])
    db.flush()  # assign IDs

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
