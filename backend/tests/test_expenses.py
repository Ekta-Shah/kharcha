import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app

CLIENT_KWARGS = {"transport": ASGITransport(app=app), "base_url": "http://test"}

SAMPLE = [
    {"date": "2026-06-10", "item": "Coffee", "category": "Food & Dining", "cost": 120, "source": "manual"},
    {"date": "2026-06-10", "item": "Auto Fare", "category": "Transport", "cost": 60, "source": "manual"},
]


@pytest.mark.asyncio
async def test_create_and_list():
    async with AsyncClient(**CLIENT_KWARGS) as client:
        r = await client.post("/api/expenses", json=SAMPLE)
        assert r.status_code == 200
        ids = [e["id"] for e in r.json()]
        assert len(ids) == 2

        r2 = await client.get("/api/expenses", params={"from_date": "2026-06-10", "to_date": "2026-06-10"})
        assert r2.status_code == 200
        items = r2.json()
        assert any(e["item"] == "Coffee" for e in items)


@pytest.mark.asyncio
async def test_patch_expense():
    async with AsyncClient(**CLIENT_KWARGS) as client:
        r = await client.post("/api/expenses", json=[SAMPLE[0]])
        exp_id = r.json()[0]["id"]

        r2 = await client.patch(f"/api/expenses/{exp_id}", json={"category": "Groceries", "cost": 130})
        assert r2.status_code == 200
        assert r2.json()["category"] == "Groceries"
        assert r2.json()["cost"] == 130.0


@pytest.mark.asyncio
async def test_delete_expense():
    async with AsyncClient(**CLIENT_KWARGS) as client:
        r = await client.post("/api/expenses", json=[SAMPLE[0]])
        exp_id = r.json()[0]["id"]

        r2 = await client.delete(f"/api/expenses/{exp_id}")
        assert r2.status_code == 204

        r3 = await client.get("/api/expenses")
        assert all(e["id"] != exp_id for e in r3.json())
