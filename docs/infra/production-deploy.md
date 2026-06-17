# 本番デプロイ手順

**最終更新:** 2026-06-17（Sprint 26 — TLS / マネージド DB / スケール）

Docker Compose で **Postgres + Redis + API + arq worker + 静的 frontend** を 1 ホストに載せる最小構成。Sprint 26 以降は **TLS（Caddy）** と **マネージド DB** 用 overlay も同梱。

---

## デプロイパターン

| パターン | コマンド |
|----------|----------|
| 最小（Compose 内 Postgres/Redis） | `make prod` |
| HTTPS（Caddy + Let's Encrypt） | `make prod-tls` |
| マネージド Postgres/Redis | `make prod-managed`（`DATABASE_URL` / `REDIS_URL` を外部向けに設定） |
| HTTPS + マネージド DB | `make prod-tls-managed` |
| API 水平スケール | 上記 + `--scale backend=N`（TLS 時は Caddy が `backend` サービス名で LB） |

---

## 前提

| コンポーネント | 役割 |
|----------------|------|
| `postgres` | アプリ DB（pgvector）— `bundled-db` profile のみ |
| `redis` | arq キュー + curriculum cache pub/sub — 同上 |
| `backend` | FastAPI（migration 自動実行） |
| `grading-worker` | 非同期採点 + 予約 broadcast cron |
| `frontend` | Vite build → nginx 静的配信 |
| `caddy` | TLS 終端（`docker-compose.prod.tls.yml` 使用時） |

**必須 migration:** `alembic upgrade head`（backend 起動時に実行）。最新 head は `e5f6a7b8c9d0`（Sprint 22 ai-era-se description）。

---

## 1. 環境変数

`.env.example` をコピーし、本番用に上書きする。

```bash
cp .env.example .env
openssl rand -hex 32   # → JWT_SECRET_KEY
```

### 共通（必須）

| 変数 | 本番値 |
|------|--------|
| `ANTHROPIC_API_KEY` | 本番キー（**必須**） |
| `CLAUDE_STUB_MODE` | **`false`** |
| `EMBEDDING_STUB_MODE` | **`false`** |
| `JWT_SECRET_KEY` | ランダム 32+ byte hex |
| `DATABASE_URL` | 接続先（下記 § マネージド DB 参照） |
| `REDIS_URL` | 接続先 |
| `GRADING_ASYNC_ENABLED` | **`true`** |
| `CURRICULUM_CACHE_PUBSUB_ENABLED` | backend を 2+ replica にする場合 **`true`** |
| `CORS_ALLOW_ORIGINS` | フロントの公開 URL（例: `https://learn.example.com`） |
| `VITE_API_BASE_URL` | ブラウザから到達可能な API URL（**build 時**に焼き込み） |
| `CSP_POLICY` | 必要に応じて frontend ドメインを許可 |

### TLS 用（`make prod-tls`）

| 変数 | 例 |
|------|-----|
| `APP_DOMAIN` | `learn.example.com`（SPA） |
| `API_DOMAIN` | `api.example.com`（FastAPI） |
| `ACME_EMAIL` | Let's Encrypt 通知先 |
| `VITE_API_BASE_URL` | `https://api.example.com` |
| `CORS_ALLOW_ORIGINS` | `https://learn.example.com` |

DNS で `APP_DOMAIN` / `API_DOMAIN` がデプロイ先ホストを向いていること。80/443 がインターネットから到達可能であること（ACME HTTP-01）。

### bundled Postgres/Redis（`make prod`）

| 変数 | 本番値 |
|------|--------|
| `POSTGRES_PASSWORD` | 強力なパスワード |
| `DATABASE_URL` | `postgresql+asyncpg://USER:PASS@postgres:5432/ai_tutor` |
| `REDIS_URL` | `redis://redis:6379/0` |

---

## 2. 起動

### 最小構成

```bash
make prod
# または
docker compose -f docker-compose.prod.yml --profile bundled-db up -d --build
```

### HTTPS（Caddy）

```bash
make prod-tls
```

確認:

```bash
curl -sf https://api.example.com/healthz
curl -sf -o /dev/null -w '%{http_code}\n' https://learn.example.com/
docker compose -f docker-compose.prod.yml -f docker-compose.prod.tls.yml ps
```

### マネージド Postgres / Redis

Compose 内の `postgres` / `redis` を起動せず、外部 URL のみ使う。

```bash
# .env 例（RDS + ElastiCache）
DATABASE_URL=postgresql+asyncpg://app:SECRET@db.xxxx.ap-northeast-1.rds.amazonaws.com:5432/ai_tutor?ssl=require
REDIS_URL=rediss://:TOKEN@redis.xxxx.cache.amazonaws.com:6379/0

make prod-managed
```

**注意:**

- pgvector 拡張が有効な Postgres が必要（`CREATE EXTENSION vector`）
- migration は backend 起動時に 1 回実行される。複数 replica 同時起動時は最初の 1 台だけ migration を走らせる運用も検討
- `submission_uploads` volume は **local ストレージ時のみ** 必要（Sprint 27: S3 利用時は省略可）

### S3 アップロード（multi-replica 推奨）

backend を複数 replica にする場合、提出ファイルは共有オブジェクトストレージへ。

```bash
# .env
UPLOAD_STORAGE_BACKEND=s3
S3_UPLOAD_BUCKET=your-bucket
S3_UPLOAD_PREFIX=uploads
S3_UPLOAD_REGION=ap-northeast-1
# IAM role または AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
```

- DB の `submission_files.file_path` には `s3://bucket/key` を保存
- ローカル disk モード（`UPLOAD_STORAGE_BACKEND=local`）は従来どおり `upload_dir` + Compose volume
- `grading-worker` も同じ env を読むため、worker から S3 へ到達できること

### API 水平スケール

TLS 構成では Caddy が `backend:8000` に reverse proxy する。Compose の組み込み DNS が replica 間でラウンドロビンする。

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.prod.tls.yml \
  --profile bundled-db up -d --build --scale backend=3
```

要件:

- `CURRICULUM_CACHE_PUBSUB_ENABLED=true`
- 共有: Postgres, Redis、アップロード（S3 または `submission_uploads` volume）
- 外部 LB（ALB 等）を使う場合は TLS overlay の代わりに LB で終端し、ターゲットグループに `:8000` / `:80` を登録 → [alb-deploy.md](./alb-deploy.md)

---

## 3. 初回のみ — embeddings 投入

カリキュラム RAG 用。migration 後 1 回。

```bash
docker compose -f docker-compose.prod.yml exec backend \
  uv run python scripts/seed_embeddings.py
```

（TLS overlay 使用時も `-f` は prod のみで可 — サービス名は同一）

---

## 4. 管理者作成

```bash
docker compose -f docker-compose.prod.yml exec backend \
  uv run python -m scripts.promote_admin admin@example.com
```

事前に `/login` から対象ユーザを登録しておく。

---

## 5. 運用チェックリスト

### 起動順・依存

1. Postgres / Redis（bundled またはマネージド）が reachable
2. `backend`（migration 完了）
3. `grading-worker`
4. `frontend`（+ `caddy` if TLS）

### 予約 broadcast

`grading-worker` が動いていないと `scheduled_broadcasts` は処理されない。

### 非同期採点

`GRADING_ASYNC_ENABLED=true` かつ worker 稼働が前提。

### アップロード永続化

`submission_uploads` volume をバックアップ対象に含める。

---

## 6. アップグレード

```bash
git pull
docker compose -f docker-compose.prod.yml --profile bundled-db build
docker compose -f docker-compose.prod.yml --profile bundled-db up -d
```

TLS 利用時は `-f docker-compose.prod.tls.yml` も付与。schema 変更は backend 再起動時の migration を確認。

---

## 7. ロールバック

- **アプリのみ:** 前の git tag に checkout して `up -d --build`
- **DB:** Alembic downgrade は本番では原則非推奨。バックアップからリストア

---

## 8. 関連

- ALB + マネージド AWS: [alb-deploy.md](./alb-deploy.md)
- Compose 定義: [`docker-compose.prod.yml`](../../docker-compose.prod.yml), [`docker-compose.prod.tls.yml`](../../docker-compose.prod.tls.yml)
- Caddy 設定: [`infra/caddy/Caddyfile`](../../infra/caddy/Caddyfile)
- ローカル開発: [README.md](../../README.md)
- CI: [github-ci-setup.md](./github-ci-setup.md)
- 引き継ぎ: [HANDOVER_2026-06-14_local-dev-ready.md](../../HANDOVER_2026-06-14_local-dev-ready.md)
