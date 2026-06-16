from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense
from app.services import llm as llm_service
from app.services.categorizer import monthly_summary

_SYSTEM_TEMPLATE = (Path(__file__).parent.parent / "prompts" / "chat_system.txt").read_text()


async def _build_context(db: AsyncSession) -> str:
    summary = await monthly_summary(db)
    lines: list[str] = []

    # Monthly aggregates
    for m in summary["months"]:
        lines.append(f"\nMonth: {m['month']}  |  Total: ₹{m['total']:,.0f}")
        if m["mom_delta_pct"] is not None:
            direction = "up" if m["mom_delta_pct"] > 0 else "down"
            lines.append(f"  MoM: {direction} {abs(m['mom_delta_pct']):.1f}%")
        for cat, amt in m["by_category"].items():
            lines.append(f"  {cat}: ₹{amt:,.0f}")

    # Recurring
    if summary["recurring"]:
        lines.append("\nRecurring payments:")
        for r in summary["recurring"]:
            lines.append(f"  {r['item'].title()}: ₹{r['avg_amount']:,.0f}/month ({', '.join(r['months'])})")

    # Recent individual expenses (last 90 days) for item-level queries
    cutoff = date.today() - timedelta(days=90)
    result = await db.execute(
        select(Expense)
        .where(Expense.date >= cutoff)
        .order_by(Expense.date.desc())
    )
    recent = result.scalars().all()
    if recent:
        lines.append("\nRecent expenses (last 90 days):")
        for exp in recent:
            lines.append(f"  {exp.date}  {exp.item}  [{exp.category}]  ₹{float(exp.cost):,.0f}")

    return "\n".join(lines)


async def answer(question: str, history: list[dict], db: AsyncSession) -> dict:
    context = await _build_context(db)
    system = _SYSTEM_TEMPLATE.replace("{{EXPENSE_CONTEXT}}", context)

    messages = [*history, {"role": "user", "content": question}]
    answer_text = await llm_service.chat_with_history(system, messages, max_tokens=512)
    return {"question": question, "answer": answer_text}
