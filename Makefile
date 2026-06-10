PYTHON := backend/.venv/bin/python

.PHONY: seed test eval lint dev-up dev-down

seed:
	cd backend && $(CURDIR)/backend/.venv/bin/python -m app.seed

test:
	cd backend && $(CURDIR)/backend/.venv/bin/python -m pytest

eval:
	cd backend && $(CURDIR)/backend/.venv/bin/python -m app.evals.run_recon_eval

lint:
	cd backend && .venv/bin/ruff check app tests

dev-up:
	docker compose up -d

dev-down:
	docker compose down
