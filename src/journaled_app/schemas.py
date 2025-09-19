from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal, List
from datetime import date, datetime

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
    balance: float = 0.0
    model_config = ConfigDict(from_attributes=True)

class SplitCreate(BaseModel):
    account_id: int
    amount: float

class TransactionCreate(BaseModel):
    date: date
    description: str
    splits: List[SplitCreate]

# User schemas
class UserBase(BaseModel):
    username: str
    email: str
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserRead(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
