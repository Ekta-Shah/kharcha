import hashlib
import uuid
from pathlib import Path

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import InsightsCache

_INSIGHTS_PROMPT = (Path(__file__).parent.parent / "prompts" / "insights_system.txt").read_text()

_client: anthropic.AsyncAnthropic | None = None


def client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def chat(system: str, user: str, *, max_tokens: int = 1024) -> str:
    response = await client().messages.create(
        model=settings.llm_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text  # type: ignore[index]


async def monthly_insights(month: str, db: AsyncSession) -> dict:
    from app.services.categorizer import monthly_summary, build_insights_context

    summary = await monthly_summary(db)
    context = build_insights_context(summary, month)
    data_hash = hashlib.sha256(context.encode()).hexdigest()

    # Check cache
    cached = await db.execute(
        select(InsightsCache).where(InsightsCache.month == month)
    )
    row = cached.scalar_one_or_none()

    if row and row.data_hash == data_hash:
        return {"month": month, "insights": row.insights, "cached": True}

    # Generate
    insights_text = await chat(_INSIGHTS_PROMPT, context, max_tokens=512)

    if row:
        row.data_hash = data_hash
        row.insights = insights_text
    else:
        db.add(InsightsCache(
            id=uuid.uuid4(),
            month=month,
            data_hash=data_hash,
            insights=insights_text,
        ))
    await db.commit()

    return {"month": month, "insights": insights_text, "cached": False}
