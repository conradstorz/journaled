from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal

# Pydantic v2 models
class AccountBase(BaseModel):
    name: str
    code: Optional[str] = None
    type: Literal["ASSET","LIABILITY","EQUITY","INCOME","EXPENSE"]
    parent_id: Optional[int] = None
    currency: str = "USD"
    active: bool = True

class AccountCreate(AccountBase):
    pass

class AccountRead(AccountBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
