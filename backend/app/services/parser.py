import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CategoryOverride
from app.schemas import CATEGORIES, ParseResponse, ParsedItem
from app.services import llm as llm_service

IST = ZoneInfo("Asia/Kolkata")
PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "parse_system.txt"
_PROMPT_TEMPLATE = PROMPT_FILE.read_text()


def _today_ist() -> str:
    return datetime.now(IST).date().isoformat()


async def _few_shot_block(db: AsyncSession) -> str:
    # Fetch more than needed so dedup by item_text still yields up to 10 unique items.
    result = await db.execute(
        select(CategoryOverride).order_by(CategoryOverride.created_at.desc()).limit(50)
    )
    overrides = result.scalars().all()
    if not overrides:
        return ""

    seen: set[str] = set()
    lines: list[str] = []
    for o in overrides:
        key = o.item_text.lower()
        if key not in seen:
            seen.add(key)
            lines.append(f'  "{o.item_text}" → "{o.category}"')
        if len(lines) >= 10:
            break

    return (
        "User category corrections (MUST apply these when the item is similar):\n"
        + "\n".join(lines)
    )


async def parse(text: str, db: AsyncSession) -> ParseResponse:
    few_shot = await _few_shot_block(db)
    system = (
        _PROMPT_TEMPLATE
        .replace("{{TODAY}}", _today_ist())
        .replace("{{CATEGORIES}}", ", ".join(CATEGORIES))
        .replace("{{FEW_SHOT}}", few_shot)
    )

    raw = await llm_service.chat(system, text, max_tokens=1024)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raw2 = await llm_service.chat(
            system,
            f"{text}\n\n[Previous response was invalid JSON. Return ONLY the JSON object.]\n{raw}",
            max_tokens=1024,
        )
        data = json.loads(raw2)

    items: list[ParsedItem] = []
    warnings: list[str] = list(data.get("warnings", []))

    for obj in data.get("items", []):
        cost = Decimal(str(obj["cost"]))
        if cost > Decimal("1000000"):
            warnings.append(f"Unusually large amount ₹{cost} for '{obj['item']}' — please verify.")
        items.append(ParsedItem(
            date=date.fromisoformat(obj["date"]),
            item=obj["item"],
            category=obj.get("category", "Other"),
            cost=cost,
        ))

    return ParseResponse(items=items, warnings=warnings)
