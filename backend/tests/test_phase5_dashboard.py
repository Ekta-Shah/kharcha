"""Phase 5 acceptance tests: Dashboard API and insights cache."""
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.main import app
from app.models import Expense
from app.services import categorizer


# ── Fixtures ─────────────────────────────────────────────────────────────────

async def _add_expenses(db, rows: list[dict]) -> None:
    for r in rows:
        db.add(Expense(id=uuid.uuid4(), **r))
    await db.commit()


_THREE_MONTHS = [
    # April
    {"date": date(2026, 4, 5), "item": "Rent", "category": "Rent & Home", "cost": Decimal("15000"), "source": "manual"},
    {"date": date(2026, 4, 10), "item": "Swiggy Order", "category": "Food & Dining", "cost": Decimal("350"), "source": "voice"},
    {"date": date(2026, 4, 15), "item": "Netflix", "category": "Subscriptions", "cost": Decimal("649"), "source": "manual"},
    # May
    {"date": date(2026, 5, 5), "item": "Rent", "category": "Rent & Home", "cost": Decimal("15000"), "source": "manual"},
    {"date": date(2026, 5, 12), "item": "Swiggy Order", "category": "Food & Dining", "cost": Decimal("420"), "source": "voice"},
    {"date": date(2026, 5, 15), "item": "Netflix", "category": "Subscriptions", "cost": Decimal("649"), "source": "manual"},
    {"date": date(2026, 5, 20), "item": "Amazon Purchase", "category": "Shopping", "cost": Decimal("2500"), "source": "manual"},
    # June
    {"date": date(2026, 6, 5), "item": "Rent", "category": "Rent & Home", "cost": Decimal("15000"), "source": "manual"},
    {"date": date(2026, 6, 10), "item": "Swiggy Order", "category": "Food & Dining", "cost": Decimal("300"), "source": "voice"},
    {"date": date(2026, 6, 15), "item": "Netflix", "category": "Subscriptions", "cost": Decimal("649"), "source": "manual"},
]


# ── monthly_summary ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_monthly_summary_structure(db_session):
    await _add_expenses(db_session, _THREE_MONTHS)
    result = await categorizer.monthly_summary(db_session)

    assert "months" in result and "recurring" in result
    months = result["months"]
    assert len(months) == 3
    assert months[0]["month"] == "2026-04"
    assert months[-1]["month"] == "2026-06"


@pytest.mark.asyncio
async def test_monthly_summary_totals(db_session):
    await _add_expenses(db_session, _THREE_MONTHS)
    result = await categorizer.monthly_summary(db_session)
    months = {m["month"]: m for m in result["months"]}

    assert months["2026-04"]["total"] == pytest.approx(15000 + 350 + 649)
    assert months["2026-05"]["total"] == pytest.approx(15000 + 420 + 649 + 2500)


@pytest.mark.asyncio
async def test_monthly_summary_mom_delta(db_session):
    await _add_expenses(db_session, _THREE_MONTHS)
    result = await categorizer.monthly_summary(db_session)
    months = {m["month"]: m for m in result["months"]}

    assert months["2026-04"]["mom_delta_pct"] is None
    assert months["2026-05"]["mom_delta_pct"] is not None
    # May is more expensive than April (added Amazon)
    assert months["2026-05"]["mom_delta_pct"] > 0


@pytest.mark.asyncio
async def test_recurring_detection(db_session):
    await _add_expenses(db_session, _THREE_MONTHS)
    result = await categorizer.monthly_summary(db_session)

    recurring_items = {r["item"].lower() for r in result["recurring"]}
    assert "rent" in recurring_items
    assert "netflix" in recurring_items


@pytest.mark.asyncio
async def test_non_recurring_excluded(db_session):
    await _add_expenses(db_session, _THREE_MONTHS)
    result = await categorizer.monthly_summary(db_session)

    recurring_items = {r["item"].lower() for r in result["recurring"]}
    # Amazon Purchase only appears in May
    assert "amazon purchase" not in recurring_items


# ── GET /dashboard/monthly ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_monthly_endpoint(db_session):
    await _add_expenses(db_session, _THREE_MONTHS)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/api/dashboard/monthly")
    assert r.status_code == 200
    data = r.json()
    assert len(data["months"]) == 3
    assert any(m["month"] == "2026-06" for m in data["months"])


@pytest.mark.asyncio
async def test_dashboard_monthly_empty(db_session):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/api/dashboard/monthly")
    assert r.status_code == 200
    data = r.json()
    assert data["months"] == []
    assert data["recurring"] == []


# ── Insights cache ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_insights_cached_on_second_call(db_session):
    await _add_expenses(db_session, _THREE_MONTHS)

    fake_text = "You spent a lot on food this month."

    with patch("app.services.llm.chat", new_callable=AsyncMock, return_value=fake_text) as mock_chat:
        from app.services.llm import monthly_insights

        r1 = await monthly_insights("2026-06", db_session)
        assert r1["cached"] is False
        assert mock_chat.call_count == 1

        r2 = await monthly_insights("2026-06", db_session)
        assert r2["cached"] is True
        # LLM not called again for same data
        assert mock_chat.call_count == 1


@pytest.mark.asyncio
async def test_insights_regenerates_when_data_changes(db_session):
    await _add_expenses(db_session, _THREE_MONTHS)

    call_count = 0

    async def _fake_chat(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return f"Insight #{call_count}"

    with patch("app.services.llm.chat", side_effect=_fake_chat):
        from app.services.llm import monthly_insights

        r1 = await monthly_insights("2026-06", db_session)
        assert r1["cached"] is False

        # Add a new expense for June
        db_session.add(Expense(
            id=uuid.uuid4(),
            date=date(2026, 6, 25),
            item="Extra Purchase",
            category="Shopping",
            cost=Decimal("5000"),
            source="manual",
        ))
        await db_session.commit()

        # Cache hash will differ — should regenerate
        r2 = await monthly_insights("2026-06", db_session)
        assert r2["cached"] is False
        assert call_count == 2


@pytest.mark.asyncio
async def test_insights_endpoint(db_session):
    await _add_expenses(db_session, _THREE_MONTHS)

    with patch("app.services.llm.chat", new_callable=AsyncMock, return_value="Great spending month!"):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            r = await ac.get("/api/dashboard/insights?month=2026-06")
        assert r.status_code == 200
        data = r.json()
        assert data["month"] == "2026-06"
        assert "insights" in data
        assert "cached" in data
