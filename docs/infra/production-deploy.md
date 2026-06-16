# 本番デプロイ手順

**最終更新:** 2026-06-16（Sprint 14 完了後）

Docker Compose で **Postgres + Redis + API + arq worker + 静的 frontend** を 1 ホストに載せる最小構成（`docker-compose.prod.yml` 単体）。TLS / 外部 LB / マネージド DB は環境に合わせてこの手順の外側で追加する。

---

## 前提

| コンポーネント | 役割 |
|----------------|------|
| `postgres` | アプリ DB（pgvector） |
| `redis` | arq キュー + curriculum cache pub/sub |
| `backend` | FastAPI（migration 自動実行） |
| `grading-worker` | 非同期採点 + 予約 broadcast cron |
| `frontend` | Vite build → nginx 静的配信 |

**必須 migration:** `alembic upgrade head`（backend 起動時に実行）。最新 head は `c3d4e5f6a7b8`（`enrollment.cohort_label`）。

---

## 1. 環境変数

`.env.example` をコピーし、本番用に上書きする。

```bash
cp .env.example .env
openssl rand -hex 32   # → JWT_SECRET_KEY
```

| 変数 | 本番値 |
|------|--------|
| `ANTHROPIC_API_KEY` | 本番キー（**必須**） |
| `CLAUDE_STUB_MODE` | **`false`**（絶対に true にしない） |
| `JWT_SECRET_KEY` | ランダム 32+ byte hex |
| `POSTGRES_PASSWORD` | 強力なパスワード |
| `DATABASE_URL` | `postgresql+asyncpg://USER:PASS@postgres:5432/ai_tutor` |
| `REDIS_URL` | `redis://redis:6379/0` |
| `GRADING_ASYNC_ENABLED` | **`true`** |
| `CURRICULUM_CACHE_PUBSUB_ENABLED` | **`true`**（backend を複数 replica にする場合） |
| `CORS_ALLOW_ORIGINS` | フロントの公開 URL（例: `https://learn.example.com`） |
| `VITE_API_BASE_URL` | ブラウザから到達可能な API URL（**build 時**に焼き込み。例: `https://api.example.com`） |
| `CSP_POLICY` | 必要に応じて frontend ドメインを許可 |

---

## 2. 起動

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

確認:

```bash
curl -sf http://localhost:8000/healthz
curl -sf -o /dev/null -w '%{http_code}\n' http://localhost:${FRONTEND_PORT:-80}/
docker compose ps
```

---

## 3. 初回のみ — embeddings 投入

カリキュラム RAG 用。migration 後 1 回。

```bash
docker compose exec backend uv run python scripts/seed_embeddings.py
```

---

## 4. 管理者作成

```bash
docker compose exec backend uv run python -m scripts.promote_admin admin@example.com
```

事前に `/login` から対象ユーザを登録しておく。

---

## 5. 運用チェックリスト

### 起動順・依存

1. `postgres` / `redis` healthy
2. `backend`（migration 完了）
3. `grading-worker`（採点 + 予約 broadcast cron）
4. `frontend`

### 予約 broadcast

`grading-worker` が動いていないと `scheduled_broadcasts` は処理されない。worker ログを監視する。

### 非同期採点

`GRADING_ASYNC_ENABLED=true` かつ worker 稼働が前提。worker 停止中は提出がキューに滞留する。

### multi-worker API

backend を水平スケールする場合:

- 共有: Postgres, Redis, `submission_uploads` volume
- `CURRICULUM_CACHE_PUBSUB_ENABLED=true` で curriculum publish 後の cache 同期
- 各 replica で `alembic upgrade head` は 1 回だけ実行されるようデプロイ設計（Compose 単体では backend 1  replica 想定）

### アップロード永続化

`submission_uploads` volume をバックアップ対象に含める。

---

## 6. アップグレード

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

schema 変更がある場合は backend 再起動時の `alembic upgrade head` を確認する。破壊的 migration は事前にステージングで検証する。

---

## 7. ロールバック

- **アプリのみ:** 前のイメージ tag / git tag に checkout して `up -d --build`
- **DB:** Alembic downgrade は本番では原則非推奨。バックアップからリストア

---

## 8. 関連

- ローカル開発: [README.md](../../README.md)
- CI: [github-ci-setup.md](./github-ci-setup.md)
- 引き継ぎ: [HANDOVER_2026-06-14_local-dev-ready.md](../../HANDOVER_2026-06-14_local-dev-ready.md)
