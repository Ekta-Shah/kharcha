#!/usr/bin/env python3
"""Synthetic Hinglish expense dataset generator (Groq, resumable).

  python generate_data.py generate --per-category 300   # resumable, re-run after 429s
  python generate_data.py split                         # raw/ -> train/val/test JSONL
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

CATEGORIES = [
    "Food & Dining", "Groceries", "Transport", "Shopping",
    "Utilities & Bills", "Subscriptions", "Health", "Entertainment",
    "Rent & Home", "Education", "Travel", "Personal Care",
    "Gifts & Family", "Cash Withdrawal", "Other",
]

MODEL = os.environ.get("GEN_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
DATA_DIR = Path(__file__).parent / "data"
RAW_DIR = DATA_DIR / "raw"
BATCH = 25
SEED = 13

STYLES = [
    "UPI/GPay note style: lowercase, terse, often just merchant + amount",
    "spoken Hinglish sentence, Hindi words in Latin script",
    "bank SMS fragment style with amount",
    "quick app entry with typos and abbreviations",
    "mention popular Indian merchants, apps or places",
    "family/household context, amounts in rupees",
]

PROMPT = """Generate {n} short, realistic expense entries that an Indian user might type into an expense tracker app. Every entry must clearly belong to the category "{category}".

Style for this batch: {style}.

Rules:
- Mix Hinglish (Hindi in Latin script) and English across entries
- 2 to 10 words each; include a rupee amount in roughly half
- No numbering, no category names inside the text, no duplicates
- Keep them distinguishable from other categories (this is classification data)

Respond with ONLY a JSON array of strings."""


def call_groq(prompt: str, max_retries: int = 8) -> str:
    key = os.environ["GROQ_API_KEY"]
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 1200,
        "temperature": 0.9,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "kharcha-finetune/0.1",  # urllib's default UA gets 403'd
        },
    )
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req) as resp:
                return json.load(resp)["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                delay = float(e.headers.get("retry-after", 2 ** attempt))
                time.sleep(min(delay + random.random(), 120))
                continue
            raise
    raise RuntimeError("unreachable")


def parse_array(raw: str) -> list[str]:
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    try:
        return [str(x).strip() for x in json.loads(m.group(0)) if str(x).strip()]
    except json.JSONDecodeError:
        return []


def slug(cat: str) -> str:
    return re.sub(r"[^a-z]+", "_", cat.lower()).strip("_")


def generate(per_category: int) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    for cat in CATEGORIES:
        path = RAW_DIR / f"{slug(cat)}.jsonl"
        seen = set()
        if path.exists():
            for line in path.read_text().splitlines():
                seen.add(json.loads(line)["text"].lower())
        stalls = 0
        while len(seen) < per_category and stalls < 8:
            style = rng.choice(STYLES)
            entries = parse_array(call_groq(PROMPT.format(n=BATCH, category=cat, style=style)))
            new = [e for e in entries if e.lower() not in seen and 2 <= len(e.split()) <= 14]
            stalls = stalls + 1 if not new else 0
            with path.open("a") as f:
                for text in new[: per_category - len(seen)]:
                    seen.add(text.lower())
                    f.write(json.dumps({"text": text, "label": cat}, ensure_ascii=False) + "\n")
            print(f"{cat}: {len(seen)}/{per_category}")
    print("generation complete")


def split(test_per_cat: int = 13, val_per_cat: int = 27) -> None:
    by_cat: dict[str, list[str]] = defaultdict(list)
    seen = set()
    for path in sorted(RAW_DIR.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row["text"].lower() not in seen:
                seen.add(row["text"].lower())
                by_cat[row["label"]].append(row["text"])
    rng = random.Random(SEED)
    splits: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    for cat, texts in sorted(by_cat.items()):
        rng.shuffle(texts)
        for i, text in enumerate(texts):
            name = "test" if i < test_per_cat else "val" if i < test_per_cat + val_per_cat else "train"
            splits[name].append({"text": text, "label": cat})
    for name, rows in splits.items():
        rng.shuffle(rows)
        out = DATA_DIR / f"{name}.jsonl"
        out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
        print(f"{name}: {len(rows)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["generate", "split"])
    ap.add_argument("--per-category", type=int, default=300)
    args = ap.parse_args()
    if args.command == "generate":
        generate(args.per_category)
    else:
        split()
