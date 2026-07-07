#!/usr/bin/env python3
"""Evaluate expense classification on data/test.jsonl.

  python evaluate.py --backend groq --mode zero            # API baseline
  python evaluate.py --backend groq --mode few             # few-shot baseline
  python evaluate.py --backend hf --model <hf-repo-or-dir> # fine-tuned model, local

Writes results/<name>.json with accuracy, latency, tokens, and per-category errors.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path

from generate_data import CATEGORIES, call_groq

DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = Path(__file__).parent / "results"

INSTRUCTION = (
    "Classify this expense entry into exactly one category from this list: "
    + "; ".join(CATEGORIES)
    + ". Respond with only the category name, nothing else."
)


def normalize(raw: str) -> str:
    raw = raw.strip().splitlines()[0].strip().strip('"').rstrip(".")
    for cat in CATEGORIES:
        if raw.lower() == cat.lower():
            return cat
    for cat in CATEGORIES:  # fuzzy: model echoed extra words
        if cat.lower() in raw.lower():
            return cat
    return "Other"


def few_shot_block() -> str:
    rows = [json.loads(x) for x in (DATA_DIR / "train.jsonl").read_text().splitlines()]
    picked: dict[str, str] = {}
    for row in rows:
        picked.setdefault(row["label"], row["text"])
    return "\n".join(f'"{t}" -> {c}' for c, t in sorted(picked.items()))


def predict_groq(text: str, mode: str) -> str:
    prompt = INSTRUCTION
    if mode == "few":
        prompt += "\n\nExamples:\n" + few_shot_block()
    prompt += f'\n\nEntry: "{text}"\nCategory:'
    return call_groq(prompt)


class HFModel:
    def __init__(self, model_id: str):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.tok = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=torch.float16
        ).to(device)
        self.device = device

    def predict(self, text: str) -> str:
        messages = [{"role": "user", "content": f'{INSTRUCTION}\n\nEntry: "{text}"'}]
        encoded = self.tok.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt", return_dict=True
        ).to(self.device)
        out = self.model.generate(
            **encoded, max_new_tokens=12, do_sample=False,
            pad_token_id=self.tok.eos_token_id,
        )
        prompt_len = encoded["input_ids"].shape[1]
        return self.tok.decode(out[0][prompt_len:], skip_special_tokens=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["groq", "hf"], required=True)
    ap.add_argument("--mode", choices=["zero", "few"], default="zero")
    ap.add_argument("--model", default=None, help="HF repo/dir (hf) or overrides GEN_MODEL (groq)")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if args.backend == "groq" and args.model:
        os.environ["GEN_MODEL"] = args.model
        import generate_data
        generate_data.MODEL = args.model

    rows = [json.loads(x) for x in (DATA_DIR / "test.jsonl").read_text().splitlines()]
    if args.limit:
        rows = rows[: args.limit]

    hf = HFModel(args.model) if args.backend == "hf" else None
    correct = 0
    latencies: list[float] = []
    errors: dict[str, list[dict]] = defaultdict(list)
    for i, row in enumerate(rows, 1):
        t0 = time.perf_counter()
        raw = hf.predict(row["text"]) if hf else predict_groq(row["text"], args.mode)
        latencies.append((time.perf_counter() - t0) * 1000)
        pred = normalize(raw)
        if pred == row["label"]:
            correct += 1
        else:
            errors[row["label"]].append({"text": row["text"], "predicted": pred})
        if i % 25 == 0:
            print(f"{i}/{len(rows)}  acc so far: {correct / i:.3f}")

    name = f"{args.backend}_{args.mode}" if args.backend == "groq" else "hf_finetune"
    model_name = args.model or os.environ.get("GEN_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    result = {
        "name": name,
        "model": model_name,
        "n": len(rows),
        "accuracy": correct / len(rows),
        "p50_latency_ms": statistics.median(latencies),
        "errors_by_category": {k: v for k, v in sorted(errors.items())},
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{name}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n{name}: accuracy={result['accuracy']:.3f}  p50={result['p50_latency_ms']:.0f}ms  -> {out}")


if __name__ == "__main__":
    main()
