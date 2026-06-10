import hashlib
import io
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BankTransaction, Statement


class _NormRow(NamedTuple):
    txn_date: date
    description: str
    amount: Decimal
    is_debit: bool
    hash: str


# ── bank detection ──────────────────────────────────────────────────────────

def _headers(df: pd.DataFrame) -> set[str]:
    return {str(c).strip().lower() for c in df.columns}


def _detect_bank(df: pd.DataFrame) -> str:
    h = _headers(df)
    if "narration" in h and "withdrawal amt." in h:
        return "hdfc"
    if "transaction remarks" in h and any("withdrawal amount" in x for x in h):
        return "icici"
    if "ref no./cheque no." in h and "txn date" in h:
        return "sbi"
    if "cheque no." in h and "transaction date" in h and "description" in h:
        return "kotak"
    if "particulars" in h and "chqno" in h:
        return "axis"
    return "generic"


# ── date parsing ─────────────────────────────────────────────────────────────

_DATE_FMTS = [
    "%d/%m/%y", "%d/%m/%Y",
    "%d-%m-%Y", "%d-%m-%y",
    "%d %b %Y", "%d %b %y",
    "%Y-%m-%d",
]


def _parse_date(val: object) -> date | None:
    s = str(val).strip()
    for fmt in _DATE_FMTS:
        try:
            return pd.to_datetime(s, format=fmt).date()
        except Exception:
            pass
    try:
        return pd.to_datetime(s, dayfirst=True).date()
    except Exception:
        return None


# ── amount parsing ────────────────────────────────────────────────────────────

def _parse_amount(val: object) -> Decimal | None:
    if pd.isna(val) or str(val).strip() in ("", "-"):
        return None
    try:
        cleaned = str(val).replace(",", "").replace(" ", "").strip()
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _make_hash(d: date, desc: str, amt: Decimal) -> str:
    raw = f"{d.isoformat()}|{desc.strip()}|{amt}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ── bank-specific parsers ─────────────────────────────────────────────────────

def _parse_hdfc(df: pd.DataFrame) -> list[_NormRow]:
    rows: list[_NormRow] = []
    for _, r in df.iterrows():
        d = _parse_date(r.get("Date"))
        if d is None:
            continue
        desc = str(r.get("Narration", "")).strip()
        debit = _parse_amount(r.get("Withdrawal Amt."))
        credit = _parse_amount(r.get("Deposit Amt."))
        if debit and debit > 0:
            rows.append(_NormRow(d, desc, debit, True, _make_hash(d, desc, debit)))
        if credit and credit > 0:
            rows.append(_NormRow(d, desc, credit, False, _make_hash(d, desc, credit)))
    return rows


def _parse_icici(df: pd.DataFrame) -> list[_NormRow]:
    rows: list[_NormRow] = []
    debit_col = next((c for c in df.columns if "withdrawal amount" in c.lower()), None)
    credit_col = next((c for c in df.columns if "deposit amount" in c.lower()), None)
    for _, r in df.iterrows():
        d = _parse_date(r.get("Transaction Date"))
        if d is None:
            continue
        desc = str(r.get("Transaction Remarks", "")).strip()
        debit = _parse_amount(r.get(debit_col)) if debit_col else None
        credit = _parse_amount(r.get(credit_col)) if credit_col else None
        if debit and debit > 0:
            rows.append(_NormRow(d, desc, debit, True, _make_hash(d, desc, debit)))
        if credit and credit > 0:
            rows.append(_NormRow(d, desc, credit, False, _make_hash(d, desc, credit)))
    return rows


def _parse_sbi(df: pd.DataFrame) -> list[_NormRow]:
    rows: list[_NormRow] = []
    for _, r in df.iterrows():
        d = _parse_date(r.get("Txn Date"))
        if d is None:
            continue
        desc = str(r.get("Description", "")).strip()
        debit = _parse_amount(r.get("Debit"))
        credit = _parse_amount(r.get("Credit"))
        if debit and debit > 0:
            rows.append(_NormRow(d, desc, debit, True, _make_hash(d, desc, debit)))
        if credit and credit > 0:
            rows.append(_NormRow(d, desc, credit, False, _make_hash(d, desc, credit)))
    return rows


def _parse_kotak(df: pd.DataFrame) -> list[_NormRow]:
    rows: list[_NormRow] = []
    for _, r in df.iterrows():
        d = _parse_date(r.get("Transaction Date"))
        if d is None:
            continue
        desc = str(r.get("Description", "")).strip()
        debit = _parse_amount(r.get("Debit"))
        credit = _parse_amount(r.get("Credit"))
        if debit and debit > 0:
            rows.append(_NormRow(d, desc, debit, True, _make_hash(d, desc, debit)))
        if credit and credit > 0:
            rows.append(_NormRow(d, desc, credit, False, _make_hash(d, desc, credit)))
    return rows


def _parse_axis(df: pd.DataFrame) -> list[_NormRow]:
    rows: list[_NormRow] = []
    for _, r in df.iterrows():
        d = _parse_date(r.get("Tran Date"))
        if d is None:
            continue
        desc = str(r.get("PARTICULARS", "")).strip()
        debit = _parse_amount(r.get("DR"))
        credit = _parse_amount(r.get("CR"))
        if debit and debit > 0:
            rows.append(_NormRow(d, desc, debit, True, _make_hash(d, desc, debit)))
        if credit and credit > 0:
            rows.append(_NormRow(d, desc, credit, False, _make_hash(d, desc, credit)))
    return rows


# ── generic fallback ─────────────────────────────────────────────────────────

_DATE_ALIASES = {"date", "txn date", "tran date", "transaction date", "value date"}
_DESC_ALIASES = {"description", "narration", "particulars", "transaction remarks", "details"}
_DEBIT_ALIASES = {"debit", "withdrawal amt.", "withdrawal amount (inr )", "dr", "withdrawal"}
_CREDIT_ALIASES = {"credit", "deposit amt.", "deposit amount (inr )", "cr", "deposit"}


def _best_col(cols: list[str], aliases: set[str]) -> str | None:
    lower = {c.lower(): c for c in cols}
    for alias in aliases:
        if alias in lower:
            return lower[alias]
    for alias in aliases:
        for col_l, col in lower.items():
            if alias in col_l:
                return col
    return None


def _parse_generic(df: pd.DataFrame) -> list[_NormRow]:
    cols = list(df.columns)
    date_col = _best_col(cols, _DATE_ALIASES)
    desc_col = _best_col(cols, _DESC_ALIASES)
    debit_col = _best_col(cols, _DEBIT_ALIASES)
    credit_col = _best_col(cols, _CREDIT_ALIASES)

    if not date_col or not desc_col:
        return []

    rows: list[_NormRow] = []
    for _, r in df.iterrows():
        d = _parse_date(r.get(date_col))
        if d is None:
            continue
        desc = str(r.get(desc_col, "")).strip()
        debit = _parse_amount(r.get(debit_col)) if debit_col else None
        credit = _parse_amount(r.get(credit_col)) if credit_col else None
        if debit and debit > 0:
            rows.append(_NormRow(d, desc, debit, True, _make_hash(d, desc, debit)))
        if credit and credit > 0:
            rows.append(_NormRow(d, desc, credit, False, _make_hash(d, desc, credit)))
    return rows


# ── main entry point ─────────────────────────────────────────────────────────

_PARSERS = {
    "hdfc": _parse_hdfc,
    "icici": _parse_icici,
    "sbi": _parse_sbi,
    "kotak": _parse_kotak,
    "axis": _parse_axis,
    "generic": _parse_generic,
}


def _read_df(content: bytes, filename: str) -> pd.DataFrame:
    if filename.lower().endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(content), dtype=str)
    return pd.read_csv(
        io.StringIO(content.decode("utf-8", errors="replace")),
        dtype=str,
        on_bad_lines="skip",
    )


async def ingest(content: bytes, filename: str, db: AsyncSession) -> dict:
    df = _read_df(content, filename)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")

    bank = _detect_bank(df)
    norm_rows = _PARSERS[bank](df)

    if not norm_rows:
        return {"bank": bank, "filename": filename, "total": 0, "new": 0, "duplicates": 0}

    # Dedupe against existing hashes
    all_hashes = [r.hash for r in norm_rows]
    existing = set(
        row[0]
        for row in (
            await db.execute(
                select(BankTransaction.hash).where(BankTransaction.hash.in_(all_hashes))
            )
        ).all()
    )

    dates = [r.txn_date for r in norm_rows]
    period_start = min(dates)
    period_end = max(dates)

    stmt = Statement(
        id=uuid.uuid4(),
        filename=filename,
        bank=bank,
        period_start=period_start,
        period_end=period_end,
    )
    db.add(stmt)
    await db.flush()  # get stmt.id

    new_txns = [
        BankTransaction(
            id=uuid.uuid4(),
            statement_id=stmt.id,
            txn_date=r.txn_date,
            description=r.description,
            amount=r.amount,
            is_debit=r.is_debit,
            hash=r.hash,
        )
        for r in norm_rows
        if r.hash not in existing
    ]
    db.add_all(new_txns)
    await db.commit()

    return {
        "statement_id": str(stmt.id),
        "bank": bank,
        "filename": filename,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total": len(norm_rows),
        "new": len(new_txns),
        "duplicates": len(norm_rows) - len(new_txns),
    }
