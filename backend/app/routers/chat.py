from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ChatRequest, ChatResponse
from app.services import chat as chat_service

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def ask(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    return await chat_service.answer(
        req.question,
        [{"role": m.role, "content": m.content} for m in req.history],
        db,
    )
