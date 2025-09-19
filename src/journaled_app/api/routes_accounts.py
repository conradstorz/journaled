
from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from journaled_app.models import Account, AccountType, Split
from journaled_app.api.deps import get_db, get_current_active_user
from journaled_app.models import User
from journaled_app.schemas import AccountCreate, AccountRead

router = APIRouter(prefix="/accounts", tags=["accounts"])

@router.get("/", response_model=List[AccountRead])
def list_accounts(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[Account]:
    from sqlalchemy import func
    stmt = select(Account).order_by(Account.type, Account.name)
    accounts = db.execute(stmt).scalars().all()
    # Get balances for each account
    balances = dict(
        db.query(Split.account_id, func.coalesce(func.sum(Split.amount), 0))
        .group_by(Split.account_id)
        .all()
    )
    result = []
    for acct in accounts:
        balance = float(balances.get(acct.id, 0))
        acct_dict = acct.__dict__.copy()
        acct_dict['balance'] = balance
        result.append(AccountRead(**acct_dict))
    return result

@router.post("/", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Account:
    # Ensure name unique
    exists = db.execute(select(Account).where(Account.name == payload.name)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Account name already exists")

    # Validate parent if provided
    parent_id = None
    if payload.parent_id:
        parent = db.execute(select(Account).where(Account.id == payload.parent_id)).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent account not found")
        parent_id = parent.id

    acct = Account(
        name=payload.name,
        code=payload.code,
        type=AccountType(payload.type),
        parent_id=parent_id,
        currency=payload.currency,
        is_active=payload.is_active,
    )
    db.add(acct)
    db.flush()  # assign id
    db.refresh(acct)
    db.commit()
    return acct

@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    from sqlalchemy import func
    acct = db.get(Account, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    # Check for attached splits/transactions
    splits_count = db.query(func.count()).select_from(Split).filter_by(account_id=account_id).scalar()
    if splits_count > 0:
        raise HTTPException(status_code=409, detail="Account has attached transactions and cannot be deleted")
    # Check balance (sum of splits)
    balance = db.query(func.coalesce(func.sum(Split.amount), 0)).filter_by(account_id=account_id).scalar()
    if balance != 0:
        raise HTTPException(status_code=409, detail="Account balance is not zero and cannot be deleted")
    db.delete(acct)
    db.commit()
    return