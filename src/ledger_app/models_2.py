from sqlalchemy import String, Integer, ForeignKey, Date, Numeric, Enum, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base
import enum

class AccountType(str, enum.Enum):
    ASSET="ASSET"; LIABILITY="LIABILITY"; EQUITY="EQUITY"; INCOME="INCOME"; EXPENSE="EXPENSE"

class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    code: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[AccountType] = mapped_column(Enum(AccountType))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    currency: Mapped[str] = mapped_column(String, default="USD")
    active: Mapped[bool] = mapped_column(default=True)
    parent = relationship("Account", remote_side=[id])

class PartyKind(str, enum.Enum):
    PAYEE="PAYEE"; VENDOR="VENDOR"; CUSTOMER="CUSTOMER"; MIXED="MIXED"

class Party(Base):
    __tablename__ = "parties"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    kind: Mapped[PartyKind] = mapped_column(Enum(PartyKind), default=PartyKind.MIXED)
    email: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)

class Address(Base):
    __tablename__ = "addresses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"))
    line1: Mapped[str] = mapped_column(String)
    line2: Mapped[str | None] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    postal: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String, default="US")
    is_default: Mapped[bool] = mapped_column(default=True)

class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[Date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String)
    reference: Mapped[str | None] = mapped_column(String)
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))

class Split(Base):
    __tablename__ = "splits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[Numeric] = mapped_column(Numeric(18, 2))
    memo: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        UniqueConstraint("transaction_id", "account_id", "amount", "memo", name="uq_split_dedupe"),
    )

class Statement(Base):
    __tablename__ = "statements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    period_start: Mapped[Date]
    period_end: Mapped[Date]
    opening_bal: Mapped[Numeric] = mapped_column(Numeric(18,2))
    closing_bal: Mapped[Numeric] = mapped_column(Numeric(18,2))

class StatementLine(Base):
    __tablename__ = "statement_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id", ondelete="CASCADE"))
    posted_date: Mapped[Date]
    amount: Mapped[Numeric] = mapped_column(Numeric(18,2))
    description: Mapped[str] = mapped_column(String)
    fitid: Mapped[str | None] = mapped_column(String)
    matched_split_id: Mapped[int | None] = mapped_column(ForeignKey("splits.id"))
