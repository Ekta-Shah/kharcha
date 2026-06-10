import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Expense, CategoryOverride
from app.schemas import ExpenseCreate, ExpenseOut, ExpensePatch

router = APIRouter()


@router.post("/expenses", response_model=list[ExpenseOut])
async def create_expenses(items: list[ExpenseCreate], db: AsyncSession = Depends(get_db)):
    rows = [Expense(**item.model_dump()) for item in items]
    db.add_all(rows)
    await db.commit()
    for r in rows:
        await db.refresh(r)
    return rows


@router.get("/expenses", response_model=list[ExpenseOut])
async def list_expenses(
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Expense).order_by(Expense.date.desc(), Expense.created_at.desc())
    if from_date:
        q = q.where(Expense.date >= from_date)
    if to_date:
        q = q.where(Expense.date <= to_date)
    result = await db.execute(q)
    return result.scalars().all()


@router.patch("/expenses/{expense_id}", response_model=ExpenseOut)
async def patch_expense(expense_id: uuid.UUID, patch: ExpensePatch, db: AsyncSession = Depends(get_db)):
    row = await db.get(Expense, expense_id)
    if not row:
        raise HTTPException(404)
    data = patch.model_dump(exclude_none=True)
    for k, v in data.items():
        setattr(row, k, v)
    if "category" in data:
        db.add(CategoryOverride(item_text=row.item, category=data["category"]))
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/expenses/{expense_id}", status_code=204)
async def delete_expense(expense_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    row = await db.get(Expense, expense_id)
    if not row:
        raise HTTPException(404)
    await db.delete(row)
    await db.commit()
