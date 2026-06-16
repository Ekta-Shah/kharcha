import asyncio
import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import InsightsCache

_INSIGHTS_PROMPT = (Path(__file__).parent.parent / "prompts" / "insights_system.txt").read_text()


# ── Gemini ────────────────────────────────────────────────────────────────────

def _get_gemini_client():
    from google import genai
    return genai.Client(api_key=settings.gemini_api_key)

_gemini_client = None

def get_gemini():
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = _get_gemini_client()
    return _gemini_client

# Keep this accessible for chat.py multi-turn
def _get_client():
    return get_gemini()


async def _chat_gemini(system: str, messages: list[dict], *, max_tokens: int) -> str:
    from fastapi import HTTPException
    from google.genai import types
    from google.genai.errors import ClientError, ServerError

    contents = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]

    for attempt in range(3):
        try:
            response = await get_gemini().aio.models.generate_content(
                model=settings.llm_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text
        except ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                raise HTTPException(
                    status_code=503,
                    detail="Gemini API quota exhausted for today (free tier: 20 req/day). Switch to Ollama or wait until tomorrow.",
                )
            raise
        except ServerError:
            if attempt == 2:
                raise
            await asyncio.sleep(3 * (attempt + 1))


# ── OpenAI-compatible (Groq, Ollama, etc.) ───────────────────────────────────

_oai_clients: dict = {}

def _get_oai_client(base_url: str, api_key: str):
    if base_url not in _oai_clients:
        from openai import AsyncOpenAI
        _oai_clients[base_url] = AsyncOpenAI(base_url=base_url, api_key=api_key)
    return _oai_clients[base_url]


async def _chat_oai_compat(base_url: str, api_key: str, model: str, system: str, messages: list[dict], *, max_tokens: int) -> str:
    oai_messages = [{"role": "system", "content": system}] + list(messages)
    client = _get_oai_client(base_url, api_key)
    response = await client.chat.completions.create(
        model=model,
        messages=oai_messages,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


# ── Unified interface ─────────────────────────────────────────────────────────

async def chat_with_history(system: str, messages: list[dict], *, max_tokens: int = 1024) -> str:
    """Multi-turn chat. messages = [{"role": "user"|"assistant", "content": str}, ...]"""
    if settings.llm_provider == "groq":
        return await _chat_oai_compat(
            "https://api.groq.com/openai/v1",
            settings.groq_api_key,
            settings.groq_model,
            system, messages, max_tokens=max_tokens,
        )
    if settings.llm_provider == "ollama":
        return await _chat_oai_compat(
            settings.ollama_base_url,
            "ollama",
            settings.ollama_model,
            system, messages, max_tokens=max_tokens,
        )
    return await _chat_gemini(system, messages, max_tokens=max_tokens)


async def chat(system: str, user: str, *, max_tokens: int = 1024) -> str:
    """Single-turn convenience wrapper."""
    return await chat_with_history(system, [{"role": "user", "content": user}], max_tokens=max_tokens)


# ── Insights (cached) ─────────────────────────────────────────────────────────

async def monthly_insights(month: str, db: AsyncSession) -> dict:
    from app.services.categorizer import monthly_summary, build_insights_context

    summary = await monthly_summary(db)
    context = build_insights_context(summary, month)
    data_hash = hashlib.sha256(context.encode()).hexdigest()

    cached = await db.execute(
        select(InsightsCache).where(InsightsCache.month == month)
    )
    row = cached.scalar_one_or_none()

    if row and row.data_hash == data_hash:
        return {"month": month, "insights": row.insights, "cached": True}

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
