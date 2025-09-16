from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal, List
from datetime import date

# Pydantic v2 models
class AccountBase(BaseModel):
    name: str
    code: Optional[str] = None
    type: Literal["ASSET","LIABILITY","EQUITY","INCOME","EXPENSE"]
    parent_id: Optional[int] = None
    currency: str = "USD"
    is_active: bool = True

class AccountCreate(AccountBase):
    pass

class AccountRead(AccountBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class SplitCreate(BaseModel):
    account_id: int
    amount: float

class TransactionCreate(BaseModel):
    date: date
    description: str
    splits: List[SplitCreate]
