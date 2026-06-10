"""
Phase 3 acceptance tests:
- All 5 sample statements parse to normalized txns.
- Re-upload adds 0 rows (dedupe).
- pytest green.
"""
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.models import BankTransaction

FIXTURES = Path(__file__).parent / "fixtures" / "statements"
CLIENT = {"transport": ASGITransport(app=app), "base_url": "http://test"}

BANKS = ["hdfc", "icici", "sbi", "kotak", "axis"]


async def _upload(client: AsyncClient, name: str) -> dict:
    path = FIXTURES / f"{name}_statement.csv"
    content = path.read_bytes()
    r = await client.post(
        "/api/statements/upload",
        files={"file": (f"{name}_statement.csv", content, "text/csv")},
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_all_banks_parse(db_session):
    async with AsyncClient(**CLIENT) as client:
        for bank in BANKS:
            data = await _upload(client, bank)
            assert data["bank"] == bank, f"{bank}: wrong detection, got {data['bank']}"
            assert data["new"] > 0, f"{bank}: parsed 0 new transactions"
            assert data["total"] > 0


@pytest.mark.asyncio
async def test_hdfc_debit_rows_stored(db_session):
    async with AsyncClient(**CLIENT) as client:
        data = await _upload(client, "hdfc")

    result = await db_session.execute(
        select(BankTransaction).where(BankTransaction.statement_id == data["statement_id"])
    )
    txns = result.scalars().all()
    assert len(txns) == data["new"]
    debits = [t for t in txns if t.is_debit]
    credits = [t for t in txns if not t.is_debit]
    assert len(debits) > 0
    assert len(credits) > 0  # salary credit


@pytest.mark.asyncio
async def test_reupload_adds_zero_rows(db_session):
    async with AsyncClient(**CLIENT) as client:
        first = await _upload(client, "hdfc")
        second = await _upload(client, "hdfc")

    assert second["duplicates"] == first["new"]
    assert second["new"] == 0


@pytest.mark.asyncio
async def test_period_dates_detected(db_session):
    async with AsyncClient(**CLIENT) as client:
        data = await _upload(client, "axis")

    assert data["period_start"] == "2026-06-04"
    assert data["period_end"] == "2026-06-10"


@pytest.mark.asyncio
async def test_hash_uniqueness(db_session):
    """No two stored transactions have the same hash."""
    async with AsyncClient(**CLIENT) as client:
        for bank in BANKS:
            await _upload(client, bank)

    result = await db_session.execute(select(BankTransaction.hash))
    hashes = [r[0] for r in result.all()]
    assert len(hashes) == len(set(hashes))
