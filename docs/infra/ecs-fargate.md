# ECS/Fargate Deployment Runbook

**最終更新:** 2026-06-17

EC2 + Docker Compose 構成を、AWS ECS/Fargate に移すための設計メモと実行手順。ALB / RDS / ElastiCache / S3 は [alb-deploy.md](./alb-deploy.md) と同じ前提を使う。

## アーキテクチャ

```
Internet
   |
   v
ALB (443/80, ACM)
   |-- Host: learn.example.com -> ECS service: frontend:80
   `-- Host: api.example.com   -> ECS service: backend:8000 (/healthz)

ECS/Fargate private subnets
   |-- backend service        FastAPI
   |-- grading-worker service arq worker
   `-- frontend service       nginx static frontend

Shared managed services
   |-- RDS PostgreSQL + pgvector
   |-- ElastiCache Redis
   `-- S3 submission uploads
```

Fargate では shared local volume を前提にしない。提出ファイルは `UPLOAD_STORAGE_BACKEND=s3` を必須にする。

## Compose から ECS への対応

| Compose service | ECS/Fargate | Notes |
|---|---|---|
| `backend` | ECS service | public API。ALB target group は port `8000`, health check `/healthz` |
| `grading-worker` | ECS service | ALB なし。desired count は `1+`、Redis queue を処理 |
| `frontend` | ECS service | nginx static。ALB target group は port `80`, health check `/login` |
| `postgres` | RDS | Fargate では同居しない |
| `redis` | ElastiCache | Fargate では同居しない |
| `submission_uploads` | S3 | local volume は使わない |

## Image

ECR に backend / frontend の 2 image を push する。`grading-worker` は backend image を再利用し、command だけ変える。

```bash
AWS_ACCOUNT_ID=123456789012
AWS_REGION=ap-northeast-1
ECR_BASE="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/edu"
IMAGE_TAG="$(git rev-parse --short HEAD)"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker build -t "$ECR_BASE-backend:$IMAGE_TAG" ./backend
docker build -f frontend/Dockerfile.prod \
  --build-arg VITE_API_BASE_URL=https://api.example.com \
  -t "$ECR_BASE-frontend:$IMAGE_TAG" ./frontend

docker push "$ECR_BASE-backend:$IMAGE_TAG"
docker push "$ECR_BASE-frontend:$IMAGE_TAG"
```

## Task Definitions

### backend

- Image: `edu-backend:{sha}`
- Port mapping: `8000/tcp`
- CPU/memory baseline: `512 CPU / 1024 MiB`
- Command: default Dockerfile command
- Health check: ALB `/healthz`

Required environment:

```bash
DATABASE_URL=postgresql+asyncpg://app:SECRET@rds.example:5432/ai_tutor?ssl=require
REDIS_URL=rediss://elasticache.example:6379/0
CORS_ALLOW_ORIGINS=https://learn.example.com
UPLOAD_STORAGE_BACKEND=s3
S3_UPLOAD_BUCKET=your-uploads-bucket
S3_UPLOAD_PREFIX=uploads
S3_UPLOAD_REGION=ap-northeast-1
GRADING_ASYNC_ENABLED=true
CURRICULUM_CACHE_PUBSUB_ENABLED=true
CLAUDE_STUB_MODE=false
EMBEDDING_STUB_MODE=false
```

Secrets Manager / SSM Parameter Store:

- `ANTHROPIC_API_KEY`
- `JWT_SECRET_KEY`
- DB password if `DATABASE_URL` is assembled outside the task definition

### grading-worker

- Image: same as backend
- Port mapping: none
- CPU/memory baseline: `512 CPU / 1024 MiB`
- Command:

```bash
uv run arq app.worker.settings.WorkerSettings
```

Use the same env/secrets as backend. The worker must reach RDS, ElastiCache, and S3.

### frontend

- Image: `edu-frontend:{sha}`
- Port mapping: `80/tcp`
- CPU/memory baseline: `256 CPU / 512 MiB`
- Health check: ALB `/login`

`VITE_API_BASE_URL` is baked at image build time, so rebuild frontend when API hostname changes.

## Migration

Do not run Alembic in every backend task startup. In ECS, run migration once as a one-off task before updating services:

```bash
aws ecs run-task \
  --cluster edu-prod \
  --launch-type FARGATE \
  --task-definition edu-backend-migrate:{revision} \
  --network-configuration file://ecs-network.json \
  --overrides '{
    "containerOverrides": [
      {
        "name": "backend",
        "command": ["uv", "run", "alembic", "upgrade", "head"]
      }
    ]
  }'
```

The backend image includes `alembic.ini`, `alembic/`, and `scripts/` so migration and operational scripts can run inside the same artifact.

## local uploads から S3 へ移行

既存環境が local upload volume を使っていた場合は、ECS 移行前に [production-deploy.md](./production-deploy.md) の `migrate_uploads_to_s3` 手順を完了する。Fargate 本番では local volume を共有しない。

## Deployment Order

1. Build and push backend/frontend images with the same git SHA tag.
2. Run Alembic one-off task and confirm success.
3. Update `backend` ECS service to the new backend task definition.
4. Update `grading-worker` ECS service to the same backend image revision.
5. Update `frontend` ECS service.
6. Confirm ALB target groups are healthy.
7. Smoke test:

```bash
curl -sf https://api.example.com/healthz
curl -sf -o /dev/null -w '%{http_code}\n' https://learn.example.com/login
```

## Rollback

- App rollback: update ECS services to the previous task definition revision.
- DB rollback: only use backward-compatible migrations for normal releases. If a migration is destructive, prepare an explicit restore plan before deploy.
- Frontend rollback: switch frontend service to previous task definition; no DB dependency.
- Worker rollback: keep worker image compatible with backend API/data model during rolling deploys.

## Readiness Checklist

- [ ] `UPLOAD_STORAGE_BACKEND=s3` enabled
- [ ] RDS has `vector` extension
- [ ] ElastiCache TLS setting matches `REDIS_URL` scheme
- [ ] Backend task role can read/write S3 upload bucket
- [ ] Task execution role can read Secrets Manager / SSM values
- [ ] ALB SG can reach backend/frontend service SGs
- [ ] ECS tasks run in private subnets with NAT or VPC endpoints for ECR/CloudWatch/S3
- [ ] CloudWatch logs configured for all three services
- [ ] `make lint`, backend pytest, frontend tests/build, and E2E are green before image push
