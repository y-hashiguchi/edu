.PHONY: dev prod prod-tls prod-managed prod-tls-managed test test-backend test-frontend test-e2e verify lint docker-build docker-smoke compose-config render-validate terraform-validate clean migrate revision db-shell seed-embeddings worker

COMPOSE_PROD = docker compose -f docker-compose.prod.yml
COMPOSE_PROD_BUNDLED = $(COMPOSE_PROD) --profile bundled-db
COMPOSE_PROD_TLS = $(COMPOSE_PROD) -f docker-compose.prod.tls.yml --profile bundled-db
E2E_DB ?= ai_tutor_e2e
E2E_API_PORT ?= 8001
E2E_DATABASE_URL = postgresql+asyncpg://postgres:postgres@localhost:5432/$(E2E_DB)
E2E_BACKEND_ENV = DATABASE_URL=$(E2E_DATABASE_URL) JWT_SECRET_KEY=test-secret ANTHROPIC_API_KEY=test-key CLAUDE_STUB_MODE=true EMBEDDING_STUB_MODE=true GRADING_ASYNC_ENABLED=false CURRICULUM_CACHE_PUBSUB_ENABLED=false RATE_LIMIT_ENABLED=false

prod:
	$(COMPOSE_PROD_BUNDLED) up -d --build

prod-tls:
	$(COMPOSE_PROD_TLS) up -d --build

prod-managed:
	$(COMPOSE_PROD) up -d --build

prod-tls-managed:
	$(COMPOSE_PROD) -f docker-compose.prod.tls.yml up -d --build

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

# Local CI gate for private repos (E2E requires backend on :8000 with CLAUDE_STUB_MODE).
verify: test-backend test-frontend
	@echo "Backend + frontend tests passed. Run 'make test-e2e' when backend is up."

test-backend:
	docker compose up -d postgres
	cd backend && uv run pytest -v

test-frontend:
	cd frontend && npm run test

test-e2e:
	docker compose up -d postgres
	docker compose exec -T postgres dropdb -U postgres --if-exists $(E2E_DB)
	docker compose exec -T postgres createdb -U postgres $(E2E_DB)
	cd backend && $(E2E_BACKEND_ENV) uv run alembic upgrade head
	@set -e; \
	cd backend; \
	$(E2E_BACKEND_ENV) uv run uvicorn app.main:app --host 127.0.0.1 --port $(E2E_API_PORT) > ../.e2e-backend.log 2>&1 & \
	backend_pid=$$!; \
	trap 'kill $$backend_pid 2>/dev/null || true; wait $$backend_pid 2>/dev/null || true; docker compose exec -T postgres dropdb -U postgres --if-exists $(E2E_DB) >/dev/null' EXIT INT TERM; \
	for _ in $$(seq 1 60); do \
		curl -sf http://127.0.0.1:$(E2E_API_PORT)/healthz >/dev/null && break; \
		sleep 1; \
	done; \
	curl -sf http://127.0.0.1:$(E2E_API_PORT)/api/courses/catalog >/dev/null; \
	cd ../frontend; \
	DATABASE_URL=$(E2E_DATABASE_URL) VITE_API_BASE_URL=http://127.0.0.1:$(E2E_API_PORT) npm run test:e2e

lint:
	cd backend && uv run ruff check app scripts tests
	cd frontend && npm run lint

docker-build:
	docker build -f backend/Dockerfile backend
	docker build -f frontend/Dockerfile.prod --build-arg VITE_API_BASE_URL=http://localhost:8000 frontend

docker-smoke:
	@set -e; \
	project="edu-smoke-$$(date +%s)-$$$$"; \
	cleanup() { \
		status=$$?; \
		if [ "$$status" -ne 0 ]; then \
			docker compose -p "$$project" -f docker-compose.smoke.yml ps || true; \
			docker compose -p "$$project" -f docker-compose.smoke.yml logs --no-color || true; \
		fi; \
		docker compose -p "$$project" -f docker-compose.smoke.yml down -v --remove-orphans --rmi local >/dev/null 2>&1 || true; \
		exit "$$status"; \
	}; \
	trap cleanup EXIT; \
	trap 'exit 130' INT; \
	trap 'exit 143' TERM; \
	SMOKE_BACKEND_PORT=$${SMOKE_BACKEND_PORT:-18000} \
	SMOKE_FRONTEND_PORT=$${SMOKE_FRONTEND_PORT:-18080} \
	docker compose -p "$$project" -f docker-compose.smoke.yml up -d --build --wait; \
	curl -sf "http://127.0.0.1:$${SMOKE_BACKEND_PORT:-18000}/healthz" >/dev/null; \
	curl -sf "http://127.0.0.1:$${SMOKE_BACKEND_PORT:-18000}/api/courses/catalog" >/dev/null; \
	curl -sf "http://127.0.0.1:$${SMOKE_FRONTEND_PORT:-18080}/login" >/dev/null

compose-config:
	@set -e; \
	created_env=0; \
	if [ ! -f .env ]; then cp .env.example .env; created_env=1; fi; \
	trap 'if [ "$$created_env" = "1" ]; then rm -f .env; fi' EXIT INT TERM; \
	docker compose --env-file .env.example -f docker-compose.prod.yml config --quiet; \
	APP_DOMAIN=learn.example.com API_DOMAIN=api.example.com ACME_EMAIL=ops@example.com docker compose --env-file .env.example -f docker-compose.prod.yml -f docker-compose.prod.tls.yml config --quiet

render-validate:
	bash infra/scripts/test_render_blueprint.sh

terraform-validate:
	docker run --rm -v $(CURDIR):/workspace:ro --entrypoint sh hashicorp/terraform:1.9.8 -c 'set -e; \
		mkdir -p /tmp/terraform-plugins; \
		export TF_PLUGIN_CACHE_DIR=/tmp/terraform-plugins; \
		for module in alb ecr ecs; do \
			terraform -chdir=/workspace/infra/terraform/$$module fmt -check; \
			cp -R /workspace/infra/terraform/$$module /tmp/$$module; \
			rm -rf /tmp/$$module/.terraform; \
			terraform -chdir=/tmp/$$module init -backend=false; \
			terraform -chdir=/tmp/$$module validate; \
			terraform -chdir=/tmp/$$module test; \
		done'
	bash -n infra/scripts/deploy_ecs.sh infra/scripts/push_ecr_images.sh infra/scripts/test_deploy_ecs.sh infra/scripts/test_push_ecr_images.sh
	docker run --rm -v $(CURDIR):/workspace:ro -w /workspace koalaman/shellcheck:v0.10.0 infra/scripts/deploy_ecs.sh infra/scripts/push_ecr_images.sh infra/scripts/test_deploy_ecs.sh infra/scripts/test_push_ecr_images.sh
	bash infra/scripts/test_deploy_ecs.sh
	bash infra/scripts/test_push_ecr_images.sh

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
