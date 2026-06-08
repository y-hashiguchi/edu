# AI駆動型開発 補足カリキュラム — AIチューター

FastAPI + Vue.js + PostgreSQL による AI駆動型開発カリキュラム学習支援ツールのリファレンス実装。

## セットアップ

```bash
cp .env.example .env
# .env を編集:
#   ANTHROPIC_API_KEY   Claude API キー
#   JWT_SECRET_KEY      openssl rand -hex 32 で生成した値
```

## 開発起動

### Docker Composeで起動（推奨）

```bash
make dev                # postgres + backend + frontend を起動 (alembic upgrade head を自動実行)
make seed-embeddings    # Sprint 2 用 — カリキュラム埋め込みを 1 回だけ DB に投入 (28 行)
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs
- Postgres: localhost:5432（user/password: postgres/postgres）

### ローカル直接起動

```bash
# Postgres
docker compose up -d postgres

# Backend
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## マイグレーション

```bash
make migrate                   # alembic upgrade head
make revision M="add foo"      # autogenerate
make db-shell                  # psql に接続
make seed-embeddings           # カリキュラムを embeddings テーブルに投入
```

## テスト

```bash
make test                      # backend + frontend
make test-backend              # pytest（postgres を自動起動）
make test-frontend             # vitest
```

## ディレクトリ構成

設計書: `docs/design/`
- 01 システム基本設計
- 02 詳細設計
- 03 DB設計
- 04 IF設計
- 05 画面設計
- 06 テスト設計

実装計画:
- Sprint 0: `docs/superpowers/plans/2026-06-01-ai-tutor-curriculum-sprint-0.md`
- Sprint 1: `docs/superpowers/plans/2026-06-02-ai-tutor-curriculum-sprint-1.md`
- Sprint 2: `docs/superpowers/plans/2026-06-03-ai-tutor-curriculum-sprint-2.md`
- Sprint 3: `docs/superpowers/plans/2026-06-04-ai-tutor-curriculum-sprint-3.md`
- Sprint 4: `docs/superpowers/plans/2026-06-06-ai-tutor-curriculum-sprint-4.md`

## 実装進捗

- [x] Sprint 0: スケルトン + カリキュラム配信 + AIチューター対話MVP
- [x] Sprint 1: PostgreSQL + JWT 認証 + 進捗管理 + 会話履歴永続化
- [x] Sprint 2: 課題提出 + AI採点 (Claude JSON) + RAG (pgvector + fastembed)
- [x] Sprint 3: ファイル/画像添付提出 + Claude Vision multimodal 採点 + 採点履歴 + 再採点 API
- [x] Sprint 4: 管理者ダッシュボード（admin RBAC + 受講者一覧 + 提出ドリルダウン + コメント + 通知）+ Sprint 3 security MED 5 件 + CSP middleware + per-IP rate limit (slowapi)
- [x] Sprint 4 security follow-up: Sprint 4 review で出た MEDIUM × 5 件（learner mark-read レート制限 / admin route 通知遷移防御 / list_for_admin 404 整合 / promote_admin email マスク / router guard 統合）

### 管理者の昇格

開発・運用環境で受講者を admin に昇格させる:

```bash
cd backend
uv run python -m scripts.promote_admin instructor@example.com
```

冪等。既に admin の場合は `already admin` を出力して 0 を返す。

詳細は `docs/superpowers/plans/` を参照。
