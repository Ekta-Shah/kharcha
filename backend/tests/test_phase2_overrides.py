"""
Phase 2 acceptance test: recategorize 'Zomato' twice → third parse uses corrected category.
"""
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.models import CategoryOverride
from app.services.parser import _few_shot_block

CLIENT = {"transport": ASGITransport(app=app), "base_url": "http://test"}

_ZOMATO_PARSE = json.dumps({
    "items": [{"date": "2026-06-10", "item": "Zomato Order", "category": "Food & Dining", "cost": 320}],
    "warnings": [],
})


@pytest.mark.asyncio
async def test_override_deduplication_in_few_shot(db_session):
    """Most recent category per item wins; older entries for same item are suppressed."""
    now = datetime.now(timezone.utc)
    db_session.add_all([
        CategoryOverride(item_text="Zomato Order", category="Entertainment",
                         created_at=now - timedelta(seconds=10)),
        CategoryOverride(item_text="Zomato Order", category="Subscriptions",
                         created_at=now),
        CategoryOverride(item_text="Auto Fare", category="Transport",
                         created_at=now),
    ])
    await db_session.commit()

    block = await _few_shot_block(db_session)

    assert '"Subscriptions"' in block
    assert '"Entertainment"' not in block   # older, suppressed by dedup
    assert '"Auto Fare"' in block


@pytest.mark.asyncio
async def test_feedback_loop_end_to_end(db_session):
    """
    1. Log a Zomato expense.
    2. Recategorize it twice (Food → Entertainment → Subscriptions).
    3. Parse a new Zomato note → system prompt must reference 'Subscriptions'.
    """
    async with AsyncClient(**CLIENT) as client:
        # Step 1: create expense
        r = await client.post("/api/expenses", json=[{
            "date": "2026-06-10", "item": "Zomato Order",
            "category": "Food & Dining", "cost": 320, "source": "manual",
        }])
        exp_id = r.json()[0]["id"]

        # Step 2a: recategorize → Entertainment
        await client.patch(f"/api/expenses/{exp_id}", json={"category": "Entertainment"})
        # Step 2b: recategorize → Subscriptions
        await client.patch(f"/api/expenses/{exp_id}", json={"category": "Subscriptions"})

    # Step 3: parse a new Zomato note — capture the system prompt sent to LLM
    captured_system: list[str] = []

    async def mock_chat(system: str, user: str, **kwargs) -> str:
        captured_system.append(system)
        return _ZOMATO_PARSE

    with patch("app.services.llm.chat", new=mock_chat):
        async with AsyncClient(**CLIENT) as client:
            r = await client.post("/api/parse", json={"text": "zomato order 350"})

    assert r.status_code == 200
    assert len(captured_system) == 1
    prompt = captured_system[0]
    # Most recent override (Subscriptions) must appear in the prompt.
    assert "Subscriptions" in prompt


@pytest.mark.asyncio
async def test_overrides_table_written_on_category_patch(db_session):
    """Each PATCH to category writes a row to category_overrides."""
    async with AsyncClient(**CLIENT) as client:
        r = await client.post("/api/expenses", json=[{
            "date": "2026-06-10", "item": "Chai", "category": "Food & Dining",
            "cost": 30, "source": "manual",
        }])
        exp_id = r.json()[0]["id"]
        await client.patch(f"/api/expenses/{exp_id}", json={"category": "Groceries"})

    result = await db_session.execute(
        select(CategoryOverride).where(CategoryOverride.item_text == "Chai")
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].category == "Groceries"
