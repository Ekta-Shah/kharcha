from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Statement
from app.schemas import StatementOut
from app.services import statement_ingest

router = APIRouter()


@router.post("/statements/upload")
async def upload_statement(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    content = await file.read()
    return await statement_ingest.ingest(content, file.filename or "", db)


@router.get("/statements", response_model=list[StatementOut])
async def list_statements(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Statement).order_by(Statement.uploaded_at.desc()))
    return result.scalars().all()
