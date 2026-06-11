.PHONY: dev test test-backend test-frontend test-e2e lint clean migrate revision db-shell seed-embeddings worker

worker:
	docker compose up -d redis postgres
	cd backend && set -a && . ../.env && set +a && \
		DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
		REDIS_URL=redis://localhost:6379/0 \
		uv run arq app.worker.settings.WorkerSettings

dev:
	docker compose up --build

migrate:
	cd backend && uv run alembic upgrade head

revision:
	@if [ -z "$(M)" ]; then echo "Usage: make revision M='message'"; exit 1; fi
	cd backend && uv run alembic revision --autogenerate -m "$(M)"

db-shell:
	docker compose exec postgres psql -U postgres -d ai_tutor

seed-embeddings:
	docker compose up -d postgres
	cd backend && set -a && . ../.env && set +a && \
		DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
		uv run python scripts/seed_embeddings.py

test: test-backend test-frontend

test-backend:
	docker compose up -d postgres
	cd backend && uv run pytest -v

test-frontend:
	cd frontend && npm run test

test-e2e:
	docker compose up -d postgres backend
	cd frontend && npm run test:e2e

lint:
	cd backend && uv run ruff check app tests
	cd frontend && npm run lint

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
