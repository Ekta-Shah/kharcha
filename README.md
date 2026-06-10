# Kharcha

Voice-first expense tracker with bank reconciliation. INR, IST, UPI-heavy.

## Quick start (dev)

```bash
cp .env.example .env          # fill ANTHROPIC_API_KEY
docker compose up -d          # start postgres

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.seed            # or: make seed
uvicorn app.main:app --reload  # http://localhost:8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

## Common tasks

```bash
make seed    # seed 3 months of demo data
make test    # pytest (29 tests)
make eval    # recon eval harness (precision/recall on fixture)
make lint    # ruff
```

## Auth

`AUTH_TOKEN` in `.env` enables single-user Bearer token auth on all `/api/*` routes.  
Leave it empty (default) to skip auth in dev.  
In prod, generate a random token: `openssl rand -hex 32`.

Frontend must send `Authorization: Bearer <token>` on every request when auth is enabled.

## Production deploy

```bash
# build and run the full stack (postgres + backend + frontend)
AUTH_TOKEN=<secret> ANTHROPIC_API_KEY=<key> docker compose -f docker-compose.prod.yml up -d
```

The frontend nginx proxies `/api/` to the backend container.  
App is served on port 80.

## Health check

```bash
curl http://localhost:8000/health   # {"status":"ok"}
```

## Run tests

```bash
cd backend && pytest
# or
make test
```

## Eval harness

Runs the reconciliation engine against a synthetic 10-expense / 12-txn fixture with known ground truth. No real API calls — LLM tier is mocked.

```bash
make eval
# exits 0 if precision ≥ 0.95 and recall ≥ 0.85
```

## CI

GitHub Actions runs lint → pytest → eval → frontend build on every push/PR to `main`.

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
