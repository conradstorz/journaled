from datetime import date
from decimal import Decimal
from sqlalchemy import select
from ledger_app.models import Transaction, Split, Check, CheckStatus
from ledger_app.services.posting import post_transaction
from ledger_app.services.checks import void_check

def test_void_check_creates_reversal(session_from_url):
    db = session_from_url
    tx = Transaction(date=date.today(), description="Check payment")
    s1 = Split(account_id=1, amount=Decimal("-250.00"), memo="Cash out")
    s2 = Split(account_id=2, amount=Decimal("250.00"), memo="Expense")
    post_transaction(db, tx, [s1, s2])
    db.commit()

    chk = Check(check_no="1001", date=date.today(), payee_id=None, amount=Decimal("250.00"), memo="X", transaction_id=tx.id)
    db.add(chk); db.commit()

    void_check(db, chk.id, date.today(), "Voiding test", create_reversal=True)
    refreshed = db.get(Check, chk.id)
    assert refreshed.status == CheckStatus.VOID
