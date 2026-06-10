import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app

MOCK_RESPONSE = json.dumps({
    "items": [
        {"date": "2026-06-10", "item": "Zomato Order", "category": "Food & Dining", "cost": 320},
        {"date": "2026-06-10", "item": "Auto Fare", "category": "Transport", "cost": 80},
    ],
    "warnings": [],
})


@pytest.mark.asyncio
async def test_parse_multi_item():
    with patch("app.services.llm.chat", new=AsyncMock(return_value=MOCK_RESPONSE)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/parse", json={"text": "zomato 320, auto 80"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 2
    assert data["items"][0]["item"] == "Zomato Order"
    assert data["items"][1]["cost"] == 80


@pytest.mark.asyncio
async def test_parse_large_amount_warning():
    mock = json.dumps({
        "items": [{"date": "2026-06-10", "item": "Car", "category": "Shopping", "cost": 1500000}],
        "warnings": [],
    })
    with patch("app.services.llm.chat", new=AsyncMock(return_value=mock)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/parse", json={"text": "car 15 lakh"})
    assert r.status_code == 200
    data = r.json()
    assert any("verify" in w for w in data["warnings"])
