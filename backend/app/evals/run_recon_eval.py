"""
Reconciliation eval harness.
Loads recon_cases.json, runs the reconciler with a mocked LLM tier,
reports precision/recall, exits non-zero if below thresholds.

Usage:
    python -m app.evals.run_recon_eval
    python -m app.evals.run_recon_eval --precision 0.95 --recall 0.85
"""
import argparse
import asyncio
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base
from app.models import BankTransaction, Expense, Statement
from app.services import reconciler

_FIXTURE = Path(__file__).parent / "fixtures" / "recon_cases.json"
_TEST_DB = "postgresql+asyncpg://kharcha:kharcha@localhost:5432/kharcha_eval"


async def _setup_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _load_fixture(db: AsyncSession, data: dict) -> tuple[list[str], list[str]]:
    """Insert fixture rows; return (expense_ids, txn_ids) in fixture order."""
    import uuid

    stmt_id = uuid.uuid4()
    db.add(Statement(
        id=stmt_id, filename="eval_fixture.csv", bank="generic",
        period_start=date(2026, 6, 1), period_end=date(2026, 6, 30),
    ))

    exp_id_map: dict[str, object] = {}
    for e in data["expenses"]:
        uid = uuid.uuid4()
        exp_id_map[e["id"]] = uid
        db.add(Expense(
            id=uid,
            date=date.fromisoformat(e["date"]),
            item=e["item"],
            category=e["category"],
            cost=Decimal(str(e["cost"])),
            source="manual",
        ))

    txn_id_map: dict[str, object] = {}
    for t in data["bank_transactions"]:
        uid = uuid.uuid4()
        txn_id_map[t["id"]] = uid
        db.add(BankTransaction(
            id=uid,
            statement_id=stmt_id,
            txn_date=date.fromisoformat(t["txn_date"]),
            description=t["description"],
            amount=Decimal(str(t["amount"])),
            is_debit=t["is_debit"],
            hash=f"eval-{t['id']}",
        ))

    await db.commit()
    return exp_id_map, txn_id_map


async def _run(precision_threshold: float, recall_threshold: float) -> bool:
    engine = create_async_engine(_TEST_DB, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    data = json.loads(_FIXTURE.read_text())
    gt_matches = {
        (m["expense_id"], m["bank_txn_id"])
        for m in data["ground_truth"]["matches"]
    }

    await _setup_db(engine)

    async with Session() as db:
        exp_id_map, txn_id_map = await _load_fixture(db, data)

        # Mock LLM tier so eval runs without API credits
        with patch("app.services.reconciler._tier3", new_callable=AsyncMock, return_value=[]):
            stmt_id_query = (await db.execute(
                __import__("sqlalchemy", fromlist=["select"]).select(Statement)
            )).scalars().first()
            await reconciler.run(stmt_id_query.id, db)

        buckets = await reconciler.get_buckets(stmt_id_query.id, db)

    await engine.dispose()

    # Build predicted pairs using fixture symbolic IDs
    # exp_id_map values are UUID objects; buckets returns str(uuid)
    rev_exp = {str(v): k for k, v in exp_id_map.items()}
    rev_txn = {str(v): k for k, v in txn_id_map.items()}

    predicted = set()
    for m in buckets["matched"]:
        e = m["expense"]
        t = m["bank_txn"]
        if e and t:
            sym_e = rev_exp.get(e["id"])
            sym_t = rev_txn.get(t["id"])
            if sym_e and sym_t:
                predicted.add((sym_e, sym_t))

    tp = len(predicted & gt_matches)
    fp = len(predicted - gt_matches)
    fn = len(gt_matches - predicted)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0

    print(f"GT matches:  {len(gt_matches)}")
    print(f"Predicted:   {len(predicted)}")
    print(f"TP={tp}  FP={fp}  FN={fn}")
    print(f"Precision:   {precision:.3f}  (threshold ≥ {precision_threshold})")
    print(f"Recall:      {recall:.3f}  (threshold ≥ {recall_threshold})")

    ok = precision >= precision_threshold and recall >= recall_threshold
    if ok:
        print("✓ PASS")
    else:
        print("✗ FAIL")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--precision", type=float, default=0.95)
    parser.add_argument("--recall", type=float, default=0.85)
    args = parser.parse_args()

    ok = asyncio.run(_run(args.precision, args.recall))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
