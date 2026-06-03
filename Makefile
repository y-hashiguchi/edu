.PHONY: dev test test-backend test-frontend lint clean migrate revision db-shell seed-embeddings

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

lint:
	cd backend && uv run ruff check app tests
	cd frontend && npm run lint

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
