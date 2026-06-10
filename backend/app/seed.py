"""
Seed 3 months of realistic demo data.
Run: python -m app.seed
"""
import asyncio
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Expense

_RECURRING = [
    ("Netflix", "Subscriptions", Decimal("649")),
    ("Spotify", "Subscriptions", Decimal("119")),
    ("Hotstar", "Subscriptions", Decimal("299")),
    ("Rent", "Rent & Home", Decimal("15000")),
    ("Term Insurance EMI", "Health", Decimal("3500")),
    ("Internet Bill", "Utilities & Bills", Decimal("999")),
]

_VARIABLE: list[tuple[str, str, Decimal, Decimal]] = [
    # item, category, min, max
    ("Swiggy Order",      "Food & Dining",   Decimal("150"), Decimal("600")),
    ("Zomato Order",      "Food & Dining",   Decimal("200"), Decimal("550")),
    ("Auto Fare",         "Transport",       Decimal("40"),  Decimal("150")),
    ("Rapido Ride",       "Transport",       Decimal("50"),  Decimal("200")),
    ("Grocery Run",       "Groceries",       Decimal("500"), Decimal("2500")),
    ("Blinkit Order",     "Groceries",       Decimal("200"), Decimal("800")),
    ("Amazon Purchase",   "Shopping",        Decimal("300"), Decimal("3000")),
    ("Meesho Order",      "Shopping",        Decimal("200"), Decimal("1200")),
    ("Pharmacy",          "Health",          Decimal("100"), Decimal("600")),
    ("Coffee",            "Food & Dining",   Decimal("80"),  Decimal("200")),
    ("Movie Tickets",     "Entertainment",   Decimal("400"), Decimal("900")),
    ("Electricity Bill",  "Utilities & Bills", Decimal("800"), Decimal("1800")),
    ("Restaurant Dinner", "Food & Dining",   Decimal("600"), Decimal("2000")),
    ("Petrol",            "Transport",       Decimal("500"), Decimal("2000")),
    ("Clothing",          "Shopping",        Decimal("500"), Decimal("3000")),
]

_MONTHS = [
    date(2026, 4, 1),
    date(2026, 5, 1),
    date(2026, 6, 1),
]


def _pseudo_random(seed: int, lo: Decimal, hi: Decimal) -> Decimal:
    """Deterministic fake random to keep seed reproducible."""
    frac = Decimal((seed * 2654435761) % 10000) / Decimal(10000)
    val = lo + (hi - lo) * frac
    return val.quantize(Decimal("1"))


def _day(month_start: date, day_offset: int) -> date:
    import calendar
    max_day = calendar.monthrange(month_start.year, month_start.month)[1]
    return month_start.replace(day=min(day_offset, max_day))


def _build_expenses() -> list[Expense]:
    rows: list[Expense] = []
    seed = 1

    for m_idx, month in enumerate(_MONTHS):
        # Recurring on fixed days
        for r_idx, (item, cat, amt) in enumerate(_RECURRING):
            rows.append(Expense(
                id=uuid.uuid4(),
                date=_day(month, r_idx + 1),
                item=item,
                category=cat,
                cost=amt,
                source="manual",
            ))

        # Variable expenses: ~18 per month spread across the month
        v_count = 18
        for i in range(v_count):
            item, cat, lo, hi = _VARIABLE[i % len(_VARIABLE)]
            cost = _pseudo_random(seed, lo, hi)
            seed += 1
            day_n = (i * 29 % 27) + 1
            rows.append(Expense(
                id=uuid.uuid4(),
                date=_day(month, day_n),
                item=item,
                category=cat,
                cost=cost,
                source="manual",
            ))

        # 2 cash-only expenses per month (no bank match possible)
        rows.append(Expense(
            id=uuid.uuid4(),
            date=_day(month, 15),
            item="Tea & Snacks",
            category="Food & Dining",
            cost=Decimal("80"),
            source="voice",
        ))
        rows.append(Expense(
            id=uuid.uuid4(),
            date=_day(month, 20),
            item="Auto Fare",
            category="Transport",
            cost=Decimal("60"),
            source="voice",
        ))

    return rows


async def seed() -> None:
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        existing = await db.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(Expense).limit(1)
        )
        if existing.scalar_one_or_none():
            print("Data already exists — skipping seed. Drop tables first to re-seed.")
            return

        expenses = _build_expenses()
        db.add_all(expenses)
        await db.commit()
        print(f"Seeded {len(expenses)} expenses across {len(_MONTHS)} months.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
