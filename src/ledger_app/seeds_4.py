from loguru import logger
from sqlalchemy.orm import Session
from .models import Account, AccountType

def seed_chart_of_accounts(db: Session) -> None:
    defaults = [
        ("Cash", AccountType.ASSET, None),
        ("Checking Account", AccountType.ASSET, "Cash"),
        ("Accounts Receivable", AccountType.ASSET, None),
        ("Accounts Payable", AccountType.LIABILITY, None),
        ("Owner's Equity", AccountType.EQUITY, None),
        ("Sales", AccountType.INCOME, None),
        ("Expenses", AccountType.EXPENSE, None),
    ]

    existing = {a.name: a for a in db.query(Account).all()}
    name_to_obj = existing.copy()

    for name, acct_type, parent_name in defaults:
        if name in name_to_obj:
            logger.info(f"Account '{name}' already exists, skipping.")
            continue
        parent_id = None
        if parent_name:
            parent = name_to_obj.get(parent_name)
            if not parent:
                logger.error(f"Parent account '{parent_name}' not found for '{name}'.")
                continue
            parent_id = parent.id
        acct = Account(name=name, type=acct_type, parent_id=parent_id)
        db.add(acct)
        db.flush()
        name_to_obj[name] = acct
        logger.success(f"Created account: {name} ({acct_type})")

    db.commit()
    logger.info("Chart of accounts seeding complete.")
