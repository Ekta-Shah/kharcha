import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import reconciler

router = APIRouter()


@router.post("/recon/run")
async def run_recon(payload: dict, db: AsyncSession = Depends(get_db)):
    return await reconciler.run(uuid.UUID(payload["statement_id"]), db)


@router.get("/recon/{statement_id}")
async def get_recon(statement_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await reconciler.get_buckets(statement_id, db)


@router.post("/recon/match")
async def manual_match(payload: dict, db: AsyncSession = Depends(get_db)):
    return await reconciler.manual_match(
        uuid.UUID(payload["expense_id"]), uuid.UUID(payload["bank_txn_id"]), db
    )


@router.post("/recon/confirm")
async def confirm_match(payload: dict, db: AsyncSession = Depends(get_db)):
    return await reconciler.confirm(uuid.UUID(payload["match_id"]), payload["accepted"], db)
