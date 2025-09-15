from datetime import date
from decimal import Decimal
from sqlalchemy import select
from journaled_app.models import Transaction, Split, TransactionReversal
from journaled_app.services.posting import post_transaction
from journaled_app.services.reversal import create_reversing_entry

def test_create_reversing_entry(session_from_url):
    db = session_from_url
    tx = Transaction(date=date.today(), description="Orig")
    s1 = Split(account_id=1, amount=Decimal("100.00"), memo="A")
    s2 = Split(account_id=2, amount=Decimal("-100.00"), memo="B")
    post_transaction(db, tx, [s1, s2])
    db.commit()

    rev_id = create_reversing_entry(db, tx.id, date.today(), "Reversal test")

    link = db.execute(select(TransactionReversal).where(TransactionReversal.original_tx_id == tx.id)).scalar_one()
    assert link.reversing_tx_id == rev_id

    orig = db.execute(select(Split).where(Split.transaction_id == tx.id)).scalars().all()
    rev = db.execute(select(Split).where(Split.transaction_id == rev_id)).scalars().all()
    assert len(orig) == len(rev) == 2
    assert sorted([o.amount for o in orig]) == sorted([-r.amount for r in rev])
