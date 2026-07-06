# Hinglish Expense Classifier (LoRA fine-tune)

Can a fine-tuned 1.5B open model beat API-model prompting at classifying
Hinglish expense entries ("swiggy se dinner 450", "rickshaw andheri 60",
"mummy ko gpay") into kharcha's 15 categories? This folder is the experiment.

## Pipeline

```bash
export GROQ_API_KEY=...

# 1. Generate synthetic training data (resumable; re-run after rate limits)
python generate_data.py generate --per-category 300
python generate_data.py split

# 2. Review data/test.jsonl by hand (fix wrong labels) - this makes the eval real

# 3. API baselines
python evaluate.py --backend groq --mode zero
python evaluate.py --backend groq --mode few

# 4. Train on Colab (free T4, ~30 min): open train_lora.ipynb, upload
#    data/train.jsonl + data/val.jsonl, run all, push to HF Hub

# 5. Head-to-head on your machine
pip install torch transformers
python evaluate.py --backend hf --model <your-hf-repo>
```

## Results

| Model | Accuracy | p50 latency | Cost / 1k requests |
|---|---:|---:|---:|
| API zero-shot (scout 17B) | 0.718 | 3144 ms | ~Rs. 4 (free tier: rate-limited) |
| API few-shot (scout 17B) | 0.733 | 3117 ms | ~Rs. 15 (free tier: rate-limited) |
| Qwen2.5-1.5B + LoRA (local) | pending | pending | Rs. 0 |

Full plan and acceptance criteria: [PLAN.md](PLAN.md).
