from sqlalchemy import select, func
from journaled_app.models import Account, AccountType
from journaled_app.seeds import seed_chart_of_accounts

def test_migrations_apply_and_seed_idempotent(session_from_url):
    db = session_from_url
    seed_chart_of_accounts(db)
    count1 = db.scalar(select(func.count()).select_from(Account))
    assert count1 >= 7
    seed_chart_of_accounts(db)
    count2 = db.scalar(select(func.count()).select_from(Account))
    assert count2 == count1, "Seeding should be idempotent and not create duplicates"

def test_checking_parent_is_cash(session_from_url):
    db = session_from_url
    seed_chart_of_accounts(db)
    cash = db.execute(select(Account).where(Account.name == "Cash")).scalar_one()
    checking = db.execute(select(Account).where(Account.name == "Checking Account")).scalar_one()
    assert checking.parent_id == cash.id
    assert cash.type == AccountType.ASSET
