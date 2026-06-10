import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, ForeignKey, Numeric, String, Text,
    TIMESTAMP, func, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    item: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False, default="Uncategorized")
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="voice")
    raw_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    matches: Mapped[list["Match"]] = relationship(back_populates="expense")

    __table_args__ = (CheckConstraint("cost >= 0", name="ck_expenses_cost_nonneg"),)


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str | None] = mapped_column(Text)
    bank: Mapped[str | None] = mapped_column(Text)
    period_start: Mapped[Date | None] = mapped_column(Date)
    period_end: Mapped[Date | None] = mapped_column(Date)
    uploaded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    transactions: Mapped[list["BankTransaction"]] = relationship(back_populates="statement")


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("statements.id"))
    txn_date: Mapped[Date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_debit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hash: Mapped[str | None] = mapped_column(String(64), unique=True)

    statement: Mapped["Statement"] = relationship(back_populates="transactions")
    matches: Mapped[list["Match"]] = relationship(back_populates="bank_txn")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expense_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("expenses.id"), nullable=True)
    bank_txn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("bank_transactions.id"), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    rationale: Mapped[str | None] = mapped_column(Text)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    expense: Mapped["Expense | None"] = relationship(back_populates="matches")
    bank_txn: Mapped["BankTransaction | None"] = relationship(back_populates="matches")


class InsightsCache(Base):
    __tablename__ = "insights_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    month: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    data_hash: Mapped[str] = mapped_column(Text, nullable=False)
    insights: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class CategoryOverride(Base):
    __tablename__ = "category_overrides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    # clock_timestamp() gives wall-clock time per INSERT (not transaction start), so ordering is deterministic.
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("clock_timestamp()"))
