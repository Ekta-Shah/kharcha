import uuid
from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, PlainSerializer, field_validator

# Decimal serializes as float in JSON responses
Amount = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]

CATEGORIES = [
    "Food & Dining", "Groceries", "Transport", "Shopping",
    "Utilities & Bills", "Subscriptions", "Health", "Entertainment",
    "Rent & Home", "Education", "Travel", "Personal Care",
    "Gifts & Family", "Cash Withdrawal", "Other",
]


class ParsedItem(BaseModel):
    date: Date
    item: str
    category: str
    cost: Amount

    @field_validator("cost", mode="before")
    @classmethod
    def cost_positive(cls, v: object) -> Decimal:
        v = Decimal(str(v))
        if v < 0:
            raise ValueError("cost must be non-negative")
        return v


class ParseRequest(BaseModel):
    text: str


class ParseResponse(BaseModel):
    items: list[ParsedItem]
    warnings: list[str] = []


class ExpenseCreate(BaseModel):
    date: Date
    item: str
    category: str = "Uncategorized"
    cost: Amount
    source: Literal["voice", "manual", "bank_import"] = "voice"
    raw_text: Optional[str] = None


class ExpenseOut(BaseModel):
    id: uuid.UUID
    date: Date
    item: str
    category: str
    cost: Amount
    source: str
    raw_text: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ExpensePatch(BaseModel):
    date: Optional[Date] = None
    item: Optional[str] = None
    category: Optional[str] = None
    cost: Optional[Amount] = None


class StatementOut(BaseModel):
    id: uuid.UUID
    filename: Optional[str]
    bank: Optional[str]
    period_start: Optional[Date]
    period_end: Optional[Date]
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class BankTxnOut(BaseModel):
    id: uuid.UUID
    txn_date: Date
    description: str
    amount: Amount
    is_debit: bool

    model_config = {"from_attributes": True}


class MatchOut(BaseModel):
    id: uuid.UUID
    expense_id: Optional[uuid.UUID]
    bank_txn_id: Optional[uuid.UUID]
    status: str
    confidence: Optional[Amount]
    rationale: Optional[str]
    confirmed: bool

    model_config = {"from_attributes": True}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    question: str
    answer: str
