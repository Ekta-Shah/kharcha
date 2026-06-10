from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import llm as llm_service
from app.services import categorizer

router = APIRouter()


@router.get("/dashboard/monthly")
async def monthly(db: AsyncSession = Depends(get_db)):
    return await categorizer.monthly_summary(db)


@router.get("/dashboard/insights")
async def insights(month: str, db: AsyncSession = Depends(get_db)):
    return await llm_service.monthly_insights(month, db)
