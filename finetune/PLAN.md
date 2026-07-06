# Hinglish Expense Classifier - LoRA Fine-tune Plan

Fine-tune a small open model to classify Hinglish expense entries into kharcha's
15 categories, and prove it beats API-model prompting on accuracy, latency, and
cost. Everything runs on free tiers (Groq for data, Colab T4 for training,
local Mac for inference).

Labels = kharcha's exact categories (backend/app/schemas.py), so the model
plugs into the app unchanged.

## Phase 1 - Synthetic dataset
- `generate_data.py generate`: Hinglish/code-mixed expense strings per category
  via Groq, batched, seeded, resumable (appends to raw/ files, skips done work).
- `generate_data.py split`: dedupe, stratified split -> train/val/test JSONL.
- Target: ~4200 train / ~400 val / ~200 test.
- Human step: review data/test.jsonl and fix any wrong labels (~30 min).
  The test set being human-verified is what makes the comparison defensible.
- Accept: balanced splits, no cross-split duplicates, test set reviewed.

## Phase 2 - API baselines (the "before")
- `evaluate.py --backend groq --mode zero` and `--mode few` on test.jsonl:
  accuracy, p50 latency, tokens/request -> results/*.json.
- Accept: baseline table committed.

## Phase 3 - LoRA fine-tune (manual, Colab free T4, ~30 min)
- `train_lora.ipynb`: Qwen2.5-1.5B-Instruct, LoRA r=16, 2 epochs on train.jsonl,
  early sanity on val.jsonl, push merged model + GGUF to Hugging Face Hub.
- Accept: val accuracy >= best API baseline; model public on HF.

## Phase 4 - Head-to-head
- `evaluate.py --backend hf --model <hf-repo>` locally (MPS): same test set,
  same metrics. Comparison table: fine-tune vs zero-shot vs few-shot API,
  with cost per 1k requests (local = 0) and per-category error analysis.
- Accept: single reproducible results table in README.

## Phase 5 - Release
- README results, HF model card, optional kharcha integration (replace the
  API categorizer in backend/app/services/parser.py behind a flag),
  LinkedIn post: "when I stopped prompting and fine-tuned".

## Non-goals
- No multi-label, no amount extraction (kharcha's parser handles that), no
  full-precision training, no serving infra.
