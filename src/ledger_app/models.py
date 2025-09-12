# src/ledger_app/models.py
from __future__ import annotations
from datetime import date, datetime  # Add datetime here
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Date,
    DateTime,  # Add DateTime here
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Boolean,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass



# --- NEW: Party model ---
class Party(Base):
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # optional: address fields later


class AccountType(str, Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class Account(Base):
    """Chart-of-accounts entry (supports parent/child hierarchy)."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(30))
    type: Mapped[AccountType] = mapped_column(SAEnum(AccountType), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Hierarchical COA
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent: Mapped[Optional["Account"]] = relationship(
        "Account", remote_side="Account.id", back_populates="children"
    )
    children: Mapped[List["Account"]] = relationship(
        "Account", back_populates="parent", cascade="all"
    )

    splits: Mapped[List["Split"]] = relationship(back_populates="account")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    party_id: Mapped[int | None] = mapped_column(
        ForeignKey("parties.id", ondelete="SET NULL"), nullable=True, index=True
    )
    party: Mapped["Party"] = relationship("Party")
    # reference field for external references or reversal tracking
    reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    # Relationship with cascade; adding to txn.splits sets transaction_id automatically
    splits: Mapped[List["Split"]] = relationship(
        "Split",
        back_populates="transaction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Split(Base):
    __tablename__ = "splits"

    id: Mapped[int] = mapped_column(primary_key=True)

    # ✅ Non-nullable FK; will be filled by relationship when you append to txn.splits
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    memo: Mapped[Optional[str]] = mapped_column(String(255))

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="splits")
    account = relationship("Account")


class Statement(Base):
    __tablename__ = "statements"
    __table_args__ = (
        UniqueConstraint("account_id", "period_start", "period_end", name="uq_statement_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    opening_bal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    closing_bal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    lines: Mapped[List["StatementLine"]] = relationship(
        back_populates="statement", cascade="all, delete-orphan"
    )


class StatementLine(Base):
    __tablename__ = "statement_lines"
    __table_args__ = (UniqueConstraint("statement_id", "fitid", name="uq_stmtline_fitid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(
        ForeignKey("statements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    posted_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    fitid: Mapped[Optional[str]] = mapped_column(String(64))
    matched_split_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("splits.id", ondelete="SET NULL"), index=True
    )

    statement: Mapped["Statement"] = relationship(back_populates="lines")
    matched_split: Mapped[Optional["Split"]] = relationship(foreign_keys=[matched_split_id])


class TransactionReversal(Base):
    __tablename__ = "transaction_reversals"
    __table_args__ = (
        UniqueConstraint("original_tx_id", name="uq_reversal_original"),
        UniqueConstraint("reversing_tx_id", name="uq_reversal_reversing"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_tx_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    reversing_tx_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )


class CheckStatus(str, Enum):
    ISSUED = "issued"
    VOID = "void"
    CLEARED = "cleared"


class Check(Base):
    __tablename__ = "checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    check_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    payee: Mapped[Optional[str]] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    memo_line: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[CheckStatus] = mapped_column(
        SAEnum(CheckStatus), default=CheckStatus.ISSUED, nullable=False
    )
