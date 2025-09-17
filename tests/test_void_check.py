from datetime import date
from decimal import Decimal
from journaled_app.models import Transaction, Split, Check, CheckStatus, Account
from journaled_app.services.posting import post_transaction
from journaled_app.services.checks import void_check

def test_void_check_creates_reversal(cloned_test_db):
    # Global event listener to catch any Split added with account_id=None
    from sqlalchemy.orm import Session
    from journaled_app.models import Split
    def after_attach(session, instance):
        if isinstance(instance, Split) and getattr(instance, 'account_id', None) is None:
            print(f"WARNING: Split with account_id=None attached to session! {instance}")
            print(f"All columns: {[ (col.name, getattr(instance, col.name, None)) for col in instance.__table__.columns ]}")
    from sqlalchemy import event
    event.listen(Session, 'after_attach', after_attach)
    # Add event listener to print all pending Split objects before flush
    from sqlalchemy import event
    import traceback
    def before_flush(session, flush_context, instances):
        print("DIAGNOSTIC: before_flush - printing ALL Split objects in session")
        for obj in session.identity_map.values():
            if isinstance(obj, Split):
                print(f"SESSION Split: id={obj.id}, account_id={obj.account_id}, transaction_id={obj.transaction_id}, amount={obj.amount}, memo={obj.memo}")
        for obj in session.new:
            if isinstance(obj, Split):
                print(f"NEW Split: id={obj.id}, account_id={obj.account_id}, transaction_id={obj.transaction_id}, amount={obj.amount}, memo={obj.memo}")
        for obj in session.dirty:
            if isinstance(obj, Split):
                print(f"DIRTY Split: id={obj.id}, account_id={obj.account_id}, transaction_id={obj.transaction_id}, amount={obj.amount}, memo={obj.memo}")
        # Print all splits in DB before flush
        print("DIAGNOSTIC: before_flush - printing ALL splits in DB before flush")
        all_splits = session.query(Split).all()
        for split in all_splits:
            print(f"DB Split: id={split.id}, account_id={split.account_id}, transaction_id={split.transaction_id}, amount={split.amount}, memo={split.memo}")
        bad_splits = session.query(Split).filter(Split.account_id == None).all()
        if bad_splits:
            print(f"DIAGNOSTIC: Splits with missing account_id before flush: {bad_splits}")
    event.listen(cloned_test_db, "before_flush", before_flush)
    from sqlalchemy.exc import IntegrityError
    try:
        db = cloned_test_db
        # Diagnostic: print any splits with missing account_id
        rogue_splits = db.query(Split).filter(Split.account_id == None).all()
        if rogue_splits:
            print(f"DIAGNOSTIC: Found {len(rogue_splits)} splits with account_id=None:")
            for split in rogue_splits:
                print(f"  Split id={split.id}, transaction_id={split.transaction_id}, amount={split.amount}, memo={split.memo}")
        # Create two accounts with unique names for the splits and check
        import uuid
        unique_suffix = uuid.uuid4().hex[:8]
        account1_name = f"Cash_{unique_suffix}"
        account2_name = f"Expenses_{unique_suffix}"
        # Ensure accounts do not exist before creation
        assert db.query(Account).filter_by(name=account1_name).first() is None, f"Account {account1_name} already exists!"
        # ...existing code...
        db.commit()
    except IntegrityError as e:
        print("DIAGNOSTIC: IntegrityError on commit or flush!")
        import traceback
        traceback.print_exc()
        print("DIAGNOSTIC: Exception args:", getattr(e, 'args', None))
        print("DIAGNOSTIC: Exception statement:", getattr(e, 'statement', None))
        print("DIAGNOSTIC: Exception params:", getattr(e, 'params', None))
        all_splits = cloned_test_db.query(Split).all()
        print("DIAGNOSTIC: All splits in DB after failure:")
        for split in all_splits:
            print(f"DB Split: id={split.id}, account_id={split.account_id}, transaction_id={split.transaction_id}, amount={split.amount}, memo={split.memo}")
        bad_splits = cloned_test_db.query(Split).filter(Split.account_id == None).all()
        print(f"DIAGNOSTIC: Splits with missing account_id: {bad_splits}")
        print("DIAGNOSTIC: session.new:")
        for obj in cloned_test_db.new:
            if hasattr(obj, '__table__'):
                print(f"NEW: {obj} columns: {[ (col.name, getattr(obj, col.name, None)) for col in obj.__table__.columns ]}")
        print("DIAGNOSTIC: session.dirty:")
        for obj in cloned_test_db.dirty:
            if hasattr(obj, '__table__'):
                print(f"DIRTY: {obj} columns: {[ (col.name, getattr(obj, col.name, None)) for col in obj.__table__.columns ]}")
        print("DIAGNOSTIC: session.deleted:")
        for obj in cloned_test_db.deleted:
            if hasattr(obj, '__table__'):
                print(f"DELETED: {obj} columns: {[ (col.name, getattr(obj, col.name, None)) for col in obj.__table__.columns ]}")
        print("DIAGNOSTIC: All Split objects in session.identity_map:")
        for obj in cloned_test_db.identity_map.values():
            if isinstance(obj, Split):
                print(f"SESSION Split: id={obj.id}, account_id={obj.account_id}, transaction_id={obj.transaction_id}, amount={obj.amount}, memo={obj.memo}")
        import sys
        print("DIAGNOSTIC: sys.exc_info:", sys.exc_info())
        raise
    assert db.query(Account).filter_by(name=account2_name).first() is None, f"Account {account2_name} already exists!"
    account1 = Account(name=account1_name, type="ASSET", is_active=True)
    account2 = Account(name=account2_name, type="EXPENSE", is_active=True)
    db.add_all([account1, account2])
    db.flush()  # assign IDs
    # Ensure account IDs are set
    assert account1.id is not None, "account1.id is None after flush!"
    assert account2.id is not None, "account2.id is None after flush!"


    tx = Transaction(date=date.today(), description="Check payment")
    s1 = Split(account_id=account1.id, amount=Decimal("-250.00"), memo="Cash out")
    s2 = Split(account_id=account2.id, amount=Decimal("250.00"), memo="Expense")
    assert s1.account_id is not None, "s1.account_id is None before post_transaction!"
    assert s2.account_id is not None, "s2.account_id is None before post_transaction!"
    post_transaction(db, tx, [s1, s2])
    assert s1.account_id is not None, "s1.account_id is None after post_transaction!"
    assert s2.account_id is not None, "s2.account_id is None after post_transaction!"
    db.commit()

    chk = Check(account_id=account1.id, check_number="1001", issue_date=date.today(), payee=None, amount=Decimal("250.00"), memo_line="X")
    db.add(chk)
    db.commit()

    void_check(db, chk.id, date.today(), "Voiding test", create_reversal=True)
    refreshed = db.get(Check, chk.id)
    assert refreshed.status == CheckStatus.VOID

    # Remove the accounts after test
    db.delete(account1)
    db.delete(account2)
    db.commit()
    # Ensure accounts are removed
    assert db.query(Account).filter_by(name=account1_name).first() is None, f"Account {account1_name} was not removed!"
    assert db.query(Account).filter_by(name=account2_name).first() is None, f"Account {account2_name} was not removed!"
