from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from journaled_app.db import Base
from journaled_app.models import Transaction, Split
from journaled_app.services.posting import post_transaction
from datetime import date

def make_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()

def test_must_balance():
    db = make_db()
    tx = Transaction(date=date.today(), description="Test")
    s1 = Split(account_id=1, amount=Decimal("100.00"))
    s2 = Split(account_id=2, amount=Decimal("-100.00"))
    post_transaction(db, tx, [s1, s2])
    db.commit()

def test_unbalanced_raises():
    db = make_db()
    tx = Transaction(date=date.today(), description="Oops")
    s1 = Split(account_id=1, amount=Decimal("100.00"))
    s2 = Split(account_id=2, amount=Decimal("-90.00"))
    try:
        post_transaction(db, tx, [s1, s2])
        assert False, "Should have raised"
    except ValueError:
        pass
