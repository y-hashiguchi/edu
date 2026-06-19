# ECS/Fargate Deployment Runbook

**最終更新:** 2026-06-18

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

Terraform 参考実装: [`../../infra/terraform/ecs/`](../../infra/terraform/ecs/)
ALB module は `target_type = "ip"` で適用し、出力された target group ARN と
ALB security group ID を ECS module に渡す。

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
Repository Terraform: [`../../infra/terraform/ecr/`](../../infra/terraform/ecr/)

```bash
terraform -chdir=infra/terraform/ecr apply
VITE_API_BASE_URL=https://api.example.com \
  ./infra/scripts/push_ecr_images.sh
```

helperはbackend/frontend build contextの未コミット変更を拒否し、ECR login、
production build、`sha-<commit>` immutable tag pushを実行して、ECS Terraformへ
設定する2つのimage URIを出力する。docsのみの差分はbuildを妨げない。

## Task Definitions

`infra/terraform/ecs/` は既存 VPC / private subnets / ALB target groups /
RDS / ElastiCache / S3 / ECR を入力として、以下を作成する。

- ECS cluster + Container Insights
- backend / grading-worker / frontend services
- Alembic one-off migration task definition
- CloudWatch logs
- task/execution IAM roles
- ALB からのみ 8000/80 を許可する task security group
- Secrets Manager / SSM からの secret injection
- backend / frontend CPU target tracking auto scaling
- CloudWatch high-CPU / running-task-count alarms for all services
- DynamoDB deployment lock

```bash
cd infra/terraform/ecs
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

既定の scaling range:

| Service | Min | Desired | Max | Metric |
|---|---:|---:|---:|---|
| backend | 2 | 2 | 6 | average CPU 60% |
| frontend | 2 | 2 | 4 | average CPU 60% |
| grading-worker | - | 1 | - | fixed count |

worker は CPU 使用率と Redis queue depth が一致しないため、自動 scaling は
custom CloudWatch metric を導入してから設定する。

`alarm_action_arns` にSNS topic ARNを設定すると、high CPUとrunning task不足の
alarm/復旧通知が送信される。

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

Do not run Alembic in every backend task startup. Terraform registers new task
definition revisions but ignores ECS service `task_definition` drift. Deploy
through the helper so migration completes before any service update:

```bash
terraform -chdir=infra/terraform/ecs apply
ECS_API_HEALTH_URL=https://api.example.com/healthz \
ECS_FRONTEND_HEALTH_URL=https://learn.example.com/login \
  ./infra/scripts/deploy_ecs.sh
```

The helper requires `aws`, `terraform`, and `jq`. The executing AWS principal
also needs `dynamodb:PutItem` / `dynamodb:DeleteItem` for the lock table. It:

1. acquires the DynamoDB deployment lock
2. rejects the deploy if any service is under capacity or already deploying
3. runs the migration task and waits for it to stop
4. aborts without updating services when exit code is non-zero
5. updates backend, worker, and frontend sequentially
6. waits for each ECS service to become stable
7. checks the optional API/frontend URLs through the ALB
8. restores already-updated services to their previous task definitions when a service update fails

The backend image includes `alembic.ini`, `alembic/`, and `scripts/` so migration and operational scripts can run inside the same artifact.

## local uploads から S3 へ移行

既存環境が local upload volume を使っていた場合は、ECS 移行前に [production-deploy.md](./production-deploy.md) の `migrate_uploads_to_s3` 手順を完了する。Fargate 本番では local volume を共有しない。

## Deployment Order

1. Apply ECR then ALB infrastructure when creating the environment.
2. Run `push_ecr_images.sh` and copy its output image URIs into ECS variables.
3. Run ECS `terraform apply`.
4. Run `deploy_ecs.sh`.
5. Confirm migration exit code and all three service stabilization waits succeed.
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
