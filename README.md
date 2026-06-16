# Kharcha

Voice-first Indian expense tracker with bank reconciliation, monthly insights, and a conversational AI assistant. INR, IST, UPI-heavy.

## Features

| Feature | Description |
|---------|-------------|
| Voice / text entry | Parse natural language like "spent 450 on Zomato yesterday" |
| Auto-categorization | LLM-powered with feedback loop (thumbs up/down corrections) |
| Bank reconciliation | 3-tier matching: exact → fuzzy → LLM. Eval harness P=1.0 / R=1.0 |
| Monthly insights | AI-generated spending summary, cached and invalidated on data change |
| Dashboard | Recharts bar/pie breakdown with MoM delta |
| Ask AI (chat) | Multi-turn conversational assistant grounded in your expense data |
| Multi-provider LLM | Switch between Gemini, Groq, or local Ollama via one env var |

## Quick start (dev)

```bash
cp .env.example .env          # fill in your LLM provider key (see below)
docker compose up -d          # start postgres

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.seed            # seed 3 months of demo data
uvicorn app.main:app --reload  # http://localhost:8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

## LLM providers

Set `LLM_PROVIDER` in `backend/.env` to one of:

| Provider | `LLM_PROVIDER` | Key env var | Default model | Notes |
|----------|---------------|-------------|---------------|-------|
| **Groq** (recommended) | `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` | 14,400 free req/day, fast |
| **Gemini** | `gemini` | `GEMINI_API_KEY` | `gemini-2.5-flash` | 20 free req/day (free tier) |
| **Ollama** (local) | `ollama` | — | `llama3.1:8b` | Unlimited, private, needs local GPU |

```bash
# Groq (get key at console.groq.com)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...

# Gemini (get key at aistudio.google.com)
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...

# Ollama
brew install ollama && ollama serve && ollama pull llama3.1:8b
LLM_PROVIDER=ollama
```

## Auth

`AUTH_TOKEN` in `.env` enables single-user Bearer token auth on all `/api/*` routes.
Leave it empty (default) to skip auth in dev.
In prod: `openssl rand -hex 32`.

## Common tasks

```bash
make seed    # seed 3 months of demo data
make test    # pytest
make eval    # recon eval harness (P/R check)
make lint    # ruff
```

## Production deploy

```bash
AUTH_TOKEN=<secret> GROQ_API_KEY=<key> docker compose -f docker-compose.prod.yml up -d
```

Frontend nginx proxies `/api/` to the backend container. App served on port 80.

## Health check

```bash
curl http://localhost:8000/health   # {"status":"ok"}
```

## Eval harness

Runs reconciliation against a synthetic 10-expense / 12-txn fixture with known ground truth. No real API calls — LLM tier is mocked.

```bash
make eval
# exits 0 if precision ≥ 0.95 and recall ≥ 0.85
```

## Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0 async, Alembic, asyncpg
- **Frontend**: Vite + React + TypeScript + Tailwind + Recharts
- **LLM**: Groq / Gemini / Ollama (pluggable via `LLM_PROVIDER`)
- **DB**: PostgreSQL

## Phases

| Phase | Status |
|-------|--------|
| 0 — Scaffold | ✅ |
| 1 — Ledger core | ✅ |
| 2 — Categorization + feedback loop | ✅ |
| 3 — Bank statement ingestion | ✅ |
| 4 — Reconciliation | ✅ |
| 5 — Dashboard + Insights | ✅ |
| 6 — Hardening & deploy | ✅ |
| 7 — Conversational AI chat | ✅ |
