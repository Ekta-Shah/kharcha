from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ParseRequest, ParseResponse
from app.services import parser

router = APIRouter()


@router.post("/parse", response_model=ParseResponse)
async def parse_text(req: ParseRequest, db: AsyncSession = Depends(get_db)):
    return await parser.parse(req.text, db)
