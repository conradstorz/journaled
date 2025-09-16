from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from journaled_app.models import Transaction, Split
from journaled_app.api.deps import get_db
from journaled_app.services.posting import post_transaction
from journaled_app.schemas import TransactionCreate
from decimal import Decimal

router = APIRouter(prefix="/transactions", tags=["transactions"])

@router.post("/", response_model=None, status_code=status.HTTP_201_CREATED)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    # Create Transaction object
    tx = Transaction(date=payload.date, description=payload.description)

    splits = [Split(account_id=s.account_id, amount=Decimal(str(s.amount))) for s in payload.splits]
    # Use service to post transaction (handles balancing, etc.)
    post_transaction(db, tx, splits)
    db.commit()
    return {"id": tx.id}
