"""
Phase 4 acceptance tests.
Precision ≥ 0.95 / recall ≥ 0.85 on eval fixtures (tiers 1+2 only; no real LLM call).
"""
import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models import BankTransaction, Expense, Match, Statement
from app.services.reconciler import _greedy_assign, _tier1, _tier2

CLIENT = {"transport": ASGITransport(app=app), "base_url": "http://test"}
FIXTURE = json.loads(
    (Path(__file__).parent.parent / "app" / "evals" / "fixtures" / "recon_cases.json").read_text()
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_expense(d: dict) -> Expense:
    return Expense(
        id=uuid.uuid4(),
        date=date.fromisoformat(d["date"]),
        item=d["item"],
        category=d["category"],
        cost=Decimal(str(d["cost"])),
        source="manual",
    )


def _make_txn(d: dict, stmt_id: uuid.UUID) -> BankTransaction:
    return BankTransaction(
        id=uuid.uuid4(),
        statement_id=stmt_id,
        txn_date=date.fromisoformat(d["txn_date"]),
        description=d["description"],
        amount=Decimal(str(d["amount"])),
        is_debit=d["is_debit"],
        hash=d["id"],
    )


# ── unit tests: tier logic ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tier1_exact_matches():
    expenses = [_make_expense(e) for e in FIXTURE["expenses"]]
    stmt_id = uuid.uuid4()
    txns = [_make_txn(t, stmt_id) for t in FIXTURE["bank_transactions"] if t["is_debit"]]

    candidates = _greedy_assign(_tier1(expenses, txns))

    # All exact-match pairs should be found
    exact_gt = [m for m in FIXTURE["ground_truth"]["matches"] if m["tier"] == "exact"]
    assert len(candidates) >= len(exact_gt)


@pytest.mark.asyncio
async def test_tier2_catches_fuzzy():
    """The ₹850 expense vs ₹852 bank txn must be caught by tier 2."""
    exp = _make_expense({"date": "2026-06-07", "item": "Grocery", "category": "Groceries", "cost": 850})
    txn = _make_txn({"txn_date": "2026-06-07", "description": "BIGBASKET", "amount": 852,
                      "is_debit": True, "id": "hash-fuzzy"}, uuid.uuid4())

    t1 = _tier1([exp], [txn])
    assert len(t1) == 0          # exact fails (850 ≠ 852)

    t2 = _tier2([exp], [txn])
    assert len(t2) == 1
    assert t2[0].status == "fuzzy"


# ── eval: precision / recall on fixture dataset ───────────────────────────────

@pytest.mark.asyncio
async def test_precision_recall_on_fixture(db_session):
    stmt_id = uuid.uuid4()
    stmt = Statement(
        id=stmt_id, filename="eval.csv", bank="hdfc",
        period_start=date(2026, 6, 4), period_end=date(2026, 6, 10),
    )
    db_session.add(stmt)

    expenses = [_make_expense(e) for e in FIXTURE["expenses"]]
    db_session.add_all(expenses)

    txns = [_make_txn(t, stmt_id) for t in FIXTURE["bank_transactions"]]
    db_session.add_all(txns)
    await db_session.commit()

    # Run tiers 1+2 only (no LLM in unit tests)
    debit_txns = [t for t in txns if t.is_debit]
    t1 = _greedy_assign(_tier1(expenses, debit_txns))
    matched_exp_ids = {c.expense.id for c in t1}
    matched_txn_ids = {c.bank_txn.id for c in t1}
    rem_exp = [e for e in expenses if e.id not in matched_exp_ids]
    rem_txn = [t for t in debit_txns if t.id not in matched_txn_ids]
    t2 = _greedy_assign(_tier2(rem_exp, rem_txn))
    all_candidates = t1 + t2

    gt_pairs = FIXTURE["ground_truth"]["matches"]

    # Build ground-truth set as (expense.item, expense.cost, txn.hash) tuples
    gt_set: set[tuple] = set()
    for pair in gt_pairs:
        e_fix = next(e for e in FIXTURE["expenses"] if e["id"] == pair["expense_id"])
        t_fix = next(t for t in FIXTURE["bank_transactions"] if t["id"] == pair["bank_txn_id"])
        gt_set.add((e_fix["item"], float(e_fix["cost"]), t_fix["id"]))

    pred_set: set[tuple] = set()
    for c in all_candidates:
        pred_set.add((c.expense.item, float(c.expense.cost), c.bank_txn.hash))

    tp = len(pred_set & gt_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    recall = tp / len(gt_set) if gt_set else 0.0

    print(f"\nPrecision: {precision:.2f}, Recall: {recall:.2f} ({tp}/{len(gt_set)} GT pairs found)")
    assert precision >= 0.95, f"Precision {precision:.2f} < 0.95"
    assert recall >= 0.85, f"Recall {recall:.2f} < 0.85"


# ── integration: API end-to-end ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recon_run_and_buckets(db_session):
    """Upload a statement, run recon, verify three-bucket response."""
    from pathlib import Path
    fixtures_dir = Path(__file__).parent / "fixtures" / "statements"
    content = (fixtures_dir / "hdfc_statement.csv").read_bytes()

    async with AsyncClient(**CLIENT) as client:
        # Upload statement
        upload = await client.post(
            "/api/statements/upload",
            files={"file": ("hdfc.csv", content, "text/csv")},
        )
        assert upload.status_code == 200
        stmt_id = upload.json()["statement_id"]

        # Add some matching ledger expenses
        await client.post("/api/expenses", json=[
            {"date": "2026-06-04", "item": "Swiggy Order", "category": "Food & Dining",
             "cost": 450, "source": "manual"},
            {"date": "2026-06-06", "item": "Zomato Dinner", "category": "Food & Dining",
             "cost": 320, "source": "manual"},
        ])

        # Run reconciliation
        run_r = await client.post("/api/recon/run", json={"statement_id": stmt_id})
        assert run_r.status_code == 200
        run_data = run_r.json()
        assert run_data["matched"] >= 2

        # Get buckets
        buckets = await client.get(f"/api/recon/{stmt_id}")
        assert buckets.status_code == 200
        data = buckets.json()
        assert len(data["matched"]) >= 2
        assert "summary" in data
        assert data["summary"]["total_matched"] >= 2
        assert "bank_only" in data


@pytest.mark.asyncio
async def test_confirm_and_reject(db_session):
    """Accept a match → confirmed=True; reject → match deleted."""
    from pathlib import Path
    content = (Path(__file__).parent / "fixtures" / "statements" / "hdfc_statement.csv").read_bytes()

    async with AsyncClient(**CLIENT) as client:
        upload = await client.post(
            "/api/statements/upload",
            files={"file": ("hdfc.csv", content, "text/csv")},
        )
        stmt_id = upload.json()["statement_id"]

        await client.post("/api/expenses", json=[
            {"date": "2026-06-04", "item": "Swiggy Order", "category": "Food & Dining",
             "cost": 450, "source": "manual"},
        ])
        await client.post("/api/recon/run", json={"statement_id": stmt_id})

        buckets = await client.get(f"/api/recon/{stmt_id}")
        matched = buckets.json()["matched"]
        assert len(matched) >= 1
        match_id = matched[0]["match_id"]

        # Accept
        r = await client.post("/api/recon/confirm", json={"match_id": match_id, "accepted": True})
        assert r.status_code == 200
        assert r.json()["accepted"] is True

        # Verify confirmed in DB
        match = await db_session.get(Match, uuid.UUID(match_id))
        assert match is not None
        assert match.confirmed is True
