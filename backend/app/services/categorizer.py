from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense

_MONTH_FMT = "%Y-%m"


def _month_key(d) -> str:
    return d.strftime(_MONTH_FMT)


async def monthly_summary(db: AsyncSession) -> dict:
    result = await db.execute(select(Expense).order_by(Expense.date.asc()))
    expenses = result.scalars().all()

    # Group by month → category → total
    month_cat: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    month_total: dict[str, Decimal] = defaultdict(Decimal)
    # For recurring: item_key → list of (month, amount)
    item_months: dict[str, list[tuple[str, Decimal]]] = defaultdict(list)

    for exp in expenses:
        m = _month_key(exp.date)
        month_cat[m][exp.category] += exp.cost
        month_total[m] += exp.cost
        item_months[exp.item.lower().strip()].append((m, exp.cost))

    sorted_months = sorted(month_total.keys())

    months_out = []
    prev_total: Decimal | None = None
    for i, m in enumerate(sorted_months):
        total = month_total[m]
        mom_delta_pct: float | None = None
        if prev_total and prev_total > 0:
            mom_delta_pct = round(float((total - prev_total) / prev_total * 100), 1)
        months_out.append({
            "month": m,
            "total": float(total),
            "by_category": {k: float(v) for k, v in sorted(month_cat[m].items(), key=lambda x: -x[1])},
            "mom_delta_pct": mom_delta_pct,
        })
        prev_total = total

    # Recurring detection: same item in ≥ 2 distinct months, avg amount stable within ±5%
    recurring = []
    for item_key, occurrences in item_months.items():
        distinct_months = sorted({m for m, _ in occurrences})
        if len(distinct_months) < 2:
            continue
        amounts = [amt for _, amt in occurrences]
        avg = sum(amounts) / len(amounts)
        if avg == 0:
            continue
        # Check all amounts within ±5% of avg
        if all(abs(a - avg) / avg <= Decimal("0.05") for a in amounts):
            recurring.append({
                "item": occurrences[0][1] and item_key.title(),
                "avg_amount": float(avg),
                "months": distinct_months,
            })

    recurring.sort(key=lambda r: -r["avg_amount"])

    return {"months": months_out, "recurring": recurring}


def build_insights_context(summary: dict, month: str) -> str:
    """Serialize monthly summary into a compact string for the LLM prompt."""
    target = next((m for m in summary["months"] if m["month"] == month), None)
    if not target:
        return f"No data found for {month}."

    parts = [f"Month: {month}", f"Total spend: ₹{target['total']:,.0f}"]

    if target["mom_delta_pct"] is not None:
        direction = "up" if target["mom_delta_pct"] > 0 else "down"
        parts.append(f"Month-over-month: {direction} {abs(target['mom_delta_pct']):.1f}%")

    parts.append("Spend by category:")
    for cat, amt in list(target["by_category"].items())[:10]:
        parts.append(f"  {cat}: ₹{amt:,.0f}")

    recurring_this_month = [
        r for r in summary["recurring"]
        if month in r["months"] and len(r["months"]) >= 2
    ]
    if recurring_this_month:
        parts.append("Recurring payments this month:")
        for r in recurring_this_month[:5]:
            parts.append(f"  {r['item'].title()}: ₹{r['avg_amount']:,.0f}/month")

    return "\n".join(parts)
