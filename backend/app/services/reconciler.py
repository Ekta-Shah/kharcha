import json
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BankTransaction, Expense, Match, Statement
from app.services import llm as llm_service

_RECON_PROMPT = (Path(__file__).parent.parent / "prompts" / "recon_llm.txt").read_text()
_CONFIDENCE_THRESHOLD = Decimal("0.70")
_BATCH_SIZE = 40


# ── candidate dataclass ───────────────────────────────────────────────────────

@dataclass
class _Candidate:
    expense: Expense
    bank_txn: BankTransaction
    status: str          # "exact" | "fuzzy" | "llm"
    confidence: Decimal
    rationale: str


# ── tier helpers ──────────────────────────────────────────────────────────────

def _amount_close(a: Decimal, b: Decimal) -> bool:
    diff = abs(a - b)
    return diff <= Decimal("2") or diff / max(a, b) <= Decimal("0.01")


def _date_within(d1, d2, days: int) -> bool:
    return abs((d1 - d2).days) <= days


def _tier1(expenses: list[Expense], txns: list[BankTransaction]) -> list[_Candidate]:
    """Exact: same amount, date within ±1 day."""
    candidates: list[_Candidate] = []
    for exp in expenses:
        for txn in txns:
            if exp.cost == txn.amount and _date_within(exp.date, txn.txn_date, 1):
                candidates.append(_Candidate(
                    exp, txn, "exact", Decimal("1.00"),
                    f"Exact amount ₹{exp.cost}, date within 1 day",
                ))
    return candidates


def _tier2(expenses: list[Expense], txns: list[BankTransaction]) -> list[_Candidate]:
    """Fuzzy: amount within ₹2/1%, date within ±3 days; not already exact."""
    candidates: list[_Candidate] = []
    for exp in expenses:
        for txn in txns:
            if _amount_close(exp.cost, txn.amount) and _date_within(exp.date, txn.txn_date, 3):
                day_diff = abs((exp.date - txn.txn_date).days)
                rationale = (
                    f"Amount ₹{exp.cost} ≈ ₹{txn.amount} "
                    f"({day_diff}d apart)"
                )
                candidates.append(_Candidate(exp, txn, "fuzzy", Decimal("0.85"), rationale))
    return candidates


async def _tier3(
    expenses: list[Expense],
    txns: list[BankTransaction],
) -> list[_Candidate]:
    """LLM: batch up to _BATCH_SIZE pairs, accept confidence ≥ 0.70."""
    if not expenses or not txns:
        return []

    exp_lines = "\n".join(
        f"{i}. [{exp.id}] {exp.date} \"{exp.item}\" ₹{exp.cost} ({exp.category})"
        for i, exp in enumerate(expenses[:_BATCH_SIZE])
    )
    txn_lines = "\n".join(
        f"{j}. [{txn.id}] {txn.txn_date} \"{txn.description}\" ₹{txn.amount}"
        for j, txn in enumerate(txns[:_BATCH_SIZE])
    )
    user_msg = f"Ledger expenses:\n{exp_lines}\n\nBank transactions:\n{txn_lines}"

    raw = await llm_service.chat(_RECON_PROMPT, user_msg, max_tokens=2048)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    candidates: list[_Candidate] = []
    for pair in data.get("pairs", []):
        ei = pair.get("expense_idx")
        ti = pair.get("bank_txn_idx")
        conf = Decimal(str(pair.get("confidence", 0)))
        if (
            ei is None or ti is None
            or ei >= len(expenses) or ti >= len(txns)
            or conf < _CONFIDENCE_THRESHOLD
        ):
            continue
        candidates.append(_Candidate(
            expenses[ei], txns[ti], "llm", conf,
            str(pair.get("rationale", "LLM match")),
        ))
    return candidates


def _greedy_assign(candidates: list[_Candidate]) -> list[_Candidate]:
    """Sort by confidence desc; assign each expense/txn to at most one match."""
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    used_exp: set[uuid.UUID] = set()
    used_txn: set[uuid.UUID] = set()
    result: list[_Candidate] = []
    for c in candidates:
        if c.expense.id in used_exp or c.bank_txn.id in used_txn:
            continue
        used_exp.add(c.expense.id)
        used_txn.add(c.bank_txn.id)
        result.append(c)
    return result


# ── merchant name extraction for bank-only rows ───────────────────────────────

_UPI_PATTERNS = [
    re.compile(r"UPI[-/](?:DR[-/]\d+[-/])?([A-Z][A-Z0-9 ]+?)(?:[-/]|@)", re.I),
    re.compile(r"POS\s+\w+\s+(.+)", re.I),
    re.compile(r"ATM\b", re.I),
    re.compile(r"NACH\b|ECS\b|SI\b|EMI\b", re.I),
    re.compile(r"NEFT|IMPS|RTGS", re.I),
]


def _suggest_item(desc: str) -> str:
    for pat in _UPI_PATTERNS[:2]:
        m = pat.search(desc)
        if m:
            return m.group(1).strip().title()
    if re.search(r"ATM", desc, re.I):
        return "Cash Withdrawal"
    if re.search(r"NACH|ECS|EMI", desc, re.I):
        return "EMI / Auto-debit"
    if re.search(r"NEFT|IMPS|RTGS", desc, re.I):
        return "Transfer"
    return desc[:40].strip().title()


# ── public API ────────────────────────────────────────────────────────────────

async def run(statement_id: uuid.UUID, db: AsyncSession) -> dict:
    stmt = await db.get(Statement, statement_id)
    if not stmt:
        return {"error": "Statement not found"}

    # Load bank debits for this statement
    txns_res = await db.execute(
        select(BankTransaction).where(
            BankTransaction.statement_id == statement_id,
            BankTransaction.is_debit.is_(True),
        )
    )
    all_txns = list(txns_res.scalars().all())

    # Load ledger expenses in statement date range ± 3 days
    exp_res = await db.execute(
        select(Expense).where(
            Expense.date >= stmt.period_start - timedelta(days=3),
            Expense.date <= stmt.period_end + timedelta(days=3),
        )
    )
    all_expenses = list(exp_res.scalars().all())

    # Clear prior unconfirmed matches for this statement's transactions
    txn_ids = [t.id for t in all_txns]
    if txn_ids:
        await db.execute(
            delete(Match).where(
                Match.bank_txn_id.in_(txn_ids),
                Match.confirmed.is_(False),
            )
        )

    # Get IDs already in confirmed matches (skip them)
    confirmed_res = await db.execute(
        select(Match).where(Match.confirmed.is_(True), Match.bank_txn_id.in_(txn_ids))
    )
    confirmed = confirmed_res.scalars().all()
    confirmed_exp_ids = {m.expense_id for m in confirmed if m.expense_id}
    confirmed_txn_ids = {m.bank_txn_id for m in confirmed if m.bank_txn_id}

    expenses = [e for e in all_expenses if e.id not in confirmed_exp_ids]
    txns = [t for t in all_txns if t.id not in confirmed_txn_ids]

    # Tier 1 — exact
    t1 = _tier1(expenses, txns)
    assigned = _greedy_assign(t1)
    matched_exp = {c.expense.id for c in assigned}
    matched_txn = {c.bank_txn.id for c in assigned}

    rem_exp = [e for e in expenses if e.id not in matched_exp]
    rem_txn = [t for t in txns if t.id not in matched_txn]

    # Tier 2 — fuzzy (on unmatched only)
    t2 = _tier2(rem_exp, rem_txn)
    t2_assigned = _greedy_assign(t2)
    for c in t2_assigned:
        matched_exp.add(c.expense.id)
        matched_txn.add(c.bank_txn.id)
    assigned.extend(t2_assigned)

    rem_exp = [e for e in expenses if e.id not in matched_exp]
    rem_txn = [t for t in txns if t.id not in matched_txn]

    # Tier 3 — LLM
    t3 = await _tier3(rem_exp, rem_txn)
    t3_assigned = _greedy_assign(t3)
    assigned.extend(t3_assigned)

    # Persist all matches
    new_matches = [
        Match(
            id=uuid.uuid4(),
            expense_id=c.expense.id,
            bank_txn_id=c.bank_txn.id,
            status=c.status,
            confidence=c.confidence,
            rationale=c.rationale,
            confirmed=False,
        )
        for c in assigned
    ]
    db.add_all(new_matches)
    await db.commit()

    return {
        "statement_id": str(statement_id),
        "matched": len(assigned),
        "ledger_only": len(all_expenses) - len(assigned) - len(confirmed_exp_ids),
        "bank_only": len(all_txns) - len(assigned) - len(confirmed_txn_ids),
    }


async def get_buckets(statement_id: uuid.UUID, db: AsyncSession) -> dict:
    txns_res = await db.execute(
        select(BankTransaction).where(BankTransaction.statement_id == statement_id)
    )
    all_txns = {t.id: t for t in txns_res.scalars().all()}

    matches_res = await db.execute(
        select(Match).where(Match.bank_txn_id.in_(list(all_txns.keys())))
    )
    all_matches = list(matches_res.scalars().all())

    matched_exp_ids = {m.expense_id for m in all_matches if m.expense_id}
    matched_txn_ids = {m.bank_txn_id for m in all_matches if m.bank_txn_id}

    exp_ids_needed = matched_exp_ids
    expenses_res = await db.execute(
        select(Expense).where(Expense.id.in_(list(exp_ids_needed)))
    ) if exp_ids_needed else None
    exp_map = {e.id: e for e in (expenses_res.scalars().all() if expenses_res else [])}

    # All ledger expenses in statement date range
    stmt = await db.get(Statement, statement_id)
    all_exp_res = await db.execute(
        select(Expense).where(
            Expense.date >= stmt.period_start - timedelta(days=3),
            Expense.date <= stmt.period_end + timedelta(days=3),
        )
    ) if stmt else None
    all_expenses = list(all_exp_res.scalars().all() if all_exp_res else [])

    def _txn_dict(t: BankTransaction) -> dict:
        return {
            "id": str(t.id), "txn_date": t.txn_date.isoformat(),
            "description": t.description, "amount": float(t.amount),
            "is_debit": t.is_debit,
        }

    def _exp_dict(e: Expense) -> dict:
        return {
            "id": str(e.id), "date": e.date.isoformat(),
            "item": e.item, "category": e.category, "cost": float(e.cost),
        }

    matched_out = []
    for m in all_matches:
        exp = exp_map.get(m.expense_id) if m.expense_id else None
        txn = all_txns.get(m.bank_txn_id) if m.bank_txn_id else None
        matched_out.append({
            "match_id": str(m.id),
            "status": m.status,
            "confidence": float(m.confidence) if m.confidence else None,
            "rationale": m.rationale,
            "confirmed": m.confirmed,
            "expense": _exp_dict(exp) if exp else None,
            "bank_txn": _txn_dict(txn) if txn else None,
        })

    ledger_only = [_exp_dict(e) for e in all_expenses if e.id not in matched_exp_ids]

    bank_only = []
    for txn in all_txns.values():
        if txn.id not in matched_txn_ids and txn.is_debit:
            bank_only.append({
                **_txn_dict(txn),
                "suggested_item": _suggest_item(txn.description),
            })

    unaccounted = sum(t["amount"] for t in bank_only)

    return {
        "matched": matched_out,
        "ledger_only": ledger_only,
        "bank_only": bank_only,
        "summary": {
            "total_matched": len(matched_out),
            "total_ledger_only": len(ledger_only),
            "total_bank_only": len(bank_only),
            "unaccounted_amount": round(unaccounted, 2),
        },
    }


async def manual_match(
    expense_id: uuid.UUID, bank_txn_id: uuid.UUID, db: AsyncSession
) -> dict:
    match = Match(
        id=uuid.uuid4(),
        expense_id=expense_id,
        bank_txn_id=bank_txn_id,
        status="manual",
        confidence=Decimal("1.00"),
        rationale="Manually linked by user",
        confirmed=True,
    )
    db.add(match)
    await db.commit()
    return {"match_id": str(match.id), "status": "manual", "confirmed": True}


async def confirm(match_id: uuid.UUID, accepted: bool, db: AsyncSession) -> dict:
    match = await db.get(Match, match_id)
    if not match:
        return {"error": "Match not found"}
    if accepted:
        match.confirmed = True
    else:
        await db.delete(match)
    await db.commit()
    return {"match_id": str(match_id), "accepted": accepted}
