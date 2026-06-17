# AWS ALB 本番デプロイ Runbook

**最終更新:** 2026-06-17（Sprint 28）

Compose 単体ホスト（[production-deploy.md](./production-deploy.md)）の外側に **Application Load Balancer (ALB)** を置き、TLS 終端・マネージド DB/Redis/S3 と組み合わせる手順。

---

## アーキテクチャ

```
Internet
   │
   ▼
 ALB (443/80, ACM 証明書)
   ├── Host: learn.example.com  → TG:frontend:80
   └── Host: api.example.com    → TG:backend:8000  (/healthz)
          │
          ▼
   EC2 (Docker Compose)
   ├── frontend (nginx)
   ├── backend × N
   ├── grading-worker
   └── (postgres/redis は Compose 外 — RDS / ElastiCache)

共有: RDS (pgvector), ElastiCache (Redis), S3 (uploads)
```

Caddy overlay（Sprint 26）の代わりに **ALB で TLS 終端** する。EC2 上の Compose は HTTP のまま公開し、セキュリティグループで ALB からのみ 8000/80 を許可する。

---

## 前提チェックリスト

| 項目 | 要件 |
|------|------|
| VPC | パブリックサブネット 2+ AZ（ALB）、プライベートサブネット（EC2/RDS 推奨） |
| ACM | `learn.example.com` + `api.example.com`（またはワイルドカード `*.example.com`） |
| RDS | Postgres 16 + `CREATE EXTENSION vector` |
| ElastiCache | Redis 7 |
| S3 | Sprint 27 `UPLOAD_STORAGE_BACKEND=s3` |
| EC2 | Docker + Compose v2、IAM role（S3 / Secrets 読取） |

---

## 1. EC2 上の Compose 設定

`.env`（マネージド DB + S3 例）:

```bash
DATABASE_URL=postgresql+asyncpg://app:SECRET@your-rds.xxxx.ap-northeast-1.rds.amazonaws.com:5432/ai_tutor?ssl=require
REDIS_URL=rediss://your-elasticache.xxxx.cache.amazonaws.com:6379/0
UPLOAD_STORAGE_BACKEND=s3
S3_UPLOAD_BUCKET=your-uploads-bucket
S3_UPLOAD_REGION=ap-northeast-1

VITE_API_BASE_URL=https://api.example.com
CORS_ALLOW_ORIGINS=https://learn.example.com

GRADING_ASYNC_ENABLED=true
CURRICULUM_CACHE_PUBSUB_ENABLED=true
CLAUDE_STUB_MODE=false
EMBEDDING_STUB_MODE=false
```

起動（**Caddy overlay なし** — ALB が TLS を担当）:

```bash
make prod-managed
# または backend をスケール:
docker compose -f docker-compose.prod.yml up -d --build --scale backend=2
```

ホストにバインドするポート:

| サービス | ポート | 用途 |
|----------|--------|------|
| backend | 8000 | ALB API ターゲット |
| frontend | 80 | ALB Web ターゲット |

`docker-compose.prod.yml` の `ports` 設定はそのまま利用。EC2 セキュリティグループは **ALB SG からのみ** 8000/80 を許可し、インターネット直公開はしない。

---

## 2. ターゲットグループ

| TG 名 | ポート | ヘルスチェック |
|-------|--------|----------------|
| `edu-api` | 8000 | `GET /healthz` → 200 |
| `edu-web` | 80 | `GET /login` → 200 |

- API: 猶予 30s、間隔 30s、 unhealthy 2 回
- Web: 同上

---

## 3. ALB リスナー

| リスナー | ルール |
|----------|--------|
| :443 (HTTPS) | Host `api.example.com` → `edu-api` |
| :443 | Host `learn.example.com` → `edu-web` |
| :80 | 301 → HTTPS |

ACM 証明書 ARN を HTTPS リスナーにアタッチ。

---

## 4. Terraform（参考実装）

最小例: [`../../infra/terraform/alb/`](../../infra/terraform/alb/)

```bash
cd infra/terraform/alb
cp terraform.tfvars.example terraform.tfvars   # 編集
terraform init
terraform plan
terraform apply
```

適用後、出力された `alb_dns_name` を Route 53（または DNS プロバイダ）で `learn` / `api` の CNAME または ALIAS に設定。

**注意:** この Terraform は ALB + SG + TG + リスナーのみ。RDS / ElastiCache / EC2 本体は含まない。

---

## 5. デプロイ後確認

```bash
curl -sf https://api.example.com/healthz
curl -sf -o /dev/null -w '%{http_code}\n' https://learn.example.com/login
```

ALB ターゲットが `healthy` であること（AWS コンソール → Target groups）。

---

## 6. 運用メモ

| 操作 | 手順 |
|------|------|
| アプリ更新 | EC2 で `git pull && docker compose ... up -d --build` |
| スケールアウト | 同一 TG に EC2 を追加登録、または `--scale backend=N` |
| 証明書更新 | ACM 自動更新（DNS 検証の場合は Route 53 連携） |
| ロールバック | 前イメージ tag で `up -d`、TG deregistration delay 内なら ALB が旧インスタンスへ |

---

## 7. 関連

- Compose 本番: [production-deploy.md](./production-deploy.md)
- ECS/Fargate 移行: [ecs-fargate.md](./ecs-fargate.md)
- Caddy（ALB なし単一ホスト）: [`../../infra/caddy/Caddyfile`](../../infra/caddy/Caddyfile)
- CI: [github-ci-setup.md](./github-ci-setup.md)
