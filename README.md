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
- Sprint 5: `docs/superpowers/plans/2026-06-08-ai-tutor-curriculum-sprint-5.md`
- Sprint 6: `docs/superpowers/plans/2026-06-09-ai-tutor-curriculum-sprint-6.md`
- Sprint 7: `docs/superpowers/plans/2026-06-10-ai-tutor-curriculum-sprint-7.md`
- Sprint 9: `docs/superpowers/plans/2026-06-13-ai-tutor-curriculum-sprint-9.md`
- Sprint 10: `docs/superpowers/plans/2026-06-14-ai-tutor-curriculum-sprint-10.md`
- Sprint 11: `docs/superpowers/plans/2026-06-11-ai-tutor-curriculum-sprint-11.md`
- 引き継ぎ（最新）: [`HANDOVER_2026-06-11_sprint11_done.md`](HANDOVER_2026-06-11_sprint11_done.md)

## 実装進捗

- [x] Sprint 0: スケルトン + カリキュラム配信 + AIチューター対話MVP
- [x] Sprint 1: PostgreSQL + JWT 認証 + 進捗管理 + 会話履歴永続化
- [x] Sprint 2: 課題提出 + AI採点 (Claude JSON) + RAG (pgvector + fastembed)
- [x] Sprint 3: ファイル/画像添付提出 + Claude Vision multimodal 採点 + 採点履歴 + 再採点 API
- [x] Sprint 4: 管理者ダッシュボード（admin RBAC + 受講者一覧 + 提出ドリルダウン + コメント + 通知）+ Sprint 3 security MED 5 件 + CSP middleware + per-IP rate limit (slowapi)
- [x] Sprint 4 security follow-up: Sprint 4 review で出た MEDIUM × 5 件（learner mark-read レート制限 / admin route 通知遷移防御 / list_for_admin 404 整合 / promote_admin email マスク / router guard 統合）
- [x] Sprint 5: 受講者ダッシュボード（弱点分析 + レコメンド + AI 一言 + 進捗サマリ）+ TaskItem skill_tags 拡張 + curriculum_task 用 RAG ヘルパー `search_curriculum_tasks` + `user_nudges` キャッシュテーブル + Sprint 5 review で出た HIGH × 3 件同梱修正
- [x] Sprint 6: 受講者×講師の双方向コミュニケーション（コメント返信スレッド + admin NotificationCenter 統合 + admin 受講者 dashboard + admin users 一覧の「もう一押し」column）+ Sprint 6 review で出た HIGH × 3 件同梱修正
- [x] Sprint 7: マルチコース化（courses / enrollments テーブル + 5 テーブルへの course_id FK + Python レジストリ + `?course=` スコープ + 登録時コース選択 + ダッシュボードコーススコープ化 + ai-driven-dev 既存移設 + ai-era-se Phase 1 8 課題パイロット）
- [x] Sprint 8: 採点非同期化（Redis + arq worker、提出 API は即時返却、フロントはポーリングで結果反映）
- [x] Sprint 7 follow-up / INFRA: vitest CVE パッチ（`>=3.2.5`）、Playwright headless smoke E2E、GitHub Actions CI
- [x] Sprint 9: カリキュラム編集 admin GUI（…）+ Sprint 9 review HIGH × 3 件同梱修正
- [x] Sprint 10: コホート集計 admin dashboard（`GET /api/admin/courses/{slug}/cohort-summary` + `/admin/cohort` ビュー）
- [x] Sprint 11: 予約 broadcast 通知（`scheduled_broadcasts` + arq cron + admin 予約一斉 UI）

> Sprint 5 で curriculum タスク構造が `list[str]` から `list[TaskItem]` に変わったため、既存環境では `make seed-embeddings` を再実行して embeddings.content を最新タイトルに揃えてください。
> Sprint 7 で embeddings/progress/submissions/chat_history/user_nudges に `course_id` 列が必要になりました。既存ユーザは `make migrate` で自動的に `ai-driven-dev` コースに enroll + バックフィルされます。

## マルチコース運用（Sprint 7〜）

- 2 コース運用: `ai-driven-dev`（既存 4 フェーズ、各 3 課題）と `ai-era-se`（Phase 1 パイロット、8 課題）
- 新規登録時にコース必須選択: `/login` → 新規登録 → コース select
- API は `?course={slug}` クエリでスコープ。未指定時は `ai-driven-dev` に解決
- フロント URL は `/courses/:slug/phases/:phase` 構成。旧 `/phases/:phase` は `ai-driven-dev` への redirect で互換維持
- 追加 enroll: `POST /api/admin/users/{id}/enrollments`（admin UI の受講者詳細からも操作可能）
- コース一斉通知: `POST /api/admin/notifications/broadcast`（`course_slug` で active 受講者に配信）
- 予約一斉通知 (Sprint 11): `POST /api/admin/notifications/broadcast/schedule` + arq 毎分 cron
- `make seed-embeddings` の `source_ref` は全コース `course:{slug}:phase:N:task:N` 形式に統一済み

### CI / E2E

- `.github/workflows/ci.yml`: backend pytest、frontend vitest、`npm audit --audit-level=critical`、Playwright E2E（**6 passed** 想定）
- 初回 CI 実走: [docs/infra/github-ci-setup.md](docs/infra/github-ci-setup.md) 参照（remote 未設定時は push 不可）
- ローカル E2E: `docker compose up -d postgres backend`（`CLAUDE_STUB_MODE=true` 推奨）のあと `cd frontend && npm run test:e2e`

### コホート集計（Sprint 10）

- Admin: `/admin/cohort` — コース selector + 受講者数 / 平均スコア / フェーズ完了率 / stuck 一覧 / skill tag ヒートマップ
- API: `GET /api/admin/courses/{course_slug}/cohort-summary`（admin RBAC + rate limit）
- stuck 閾値: `COHORT_STUCK_INACTIVE_DAYS=7`（`backend/app/config.py`）
- vitest **4.x** / vite **8.x**（dev 専用）。`vitest --ui` はローカル専用

### 非同期採点（Sprint 8）

- `docker compose up` で `redis` + `grading-worker` が起動（`GRADING_ASYNC_ENABLED=true` がデフォルト）
- 提出 POST は保存後すぐ 201 を返し、採点はワーカーがバックグラウンド実行
- ローカル直接起動時は Redis を立て、`make worker` でワーカーを別ターミナル起動
- テストは `GRADING_ASYNC_ENABLED=false` で同期採点（Redis 不要）

### 管理者の昇格

開発・運用環境で受講者を admin に昇格させる:

```bash
cd backend
uv run python -m scripts.promote_admin instructor@example.com
```

冪等。既に admin の場合は `already admin` を出力して 0 を返す。

### カリキュラム編集（Sprint 9〜）

- admin GUI: `/admin/curriculum` → コース選択 → title / description / skill_tags / deliverable / system_prompt を編集
- 編集は debounce 500ms で `draft_*` 列に保存（公開には影響しない）
- 「公開」ボタンで draft を published 列に COPY し、in-process cache を再ロード
- 「ドラフト破棄」で未公開の編集を全て NULL に戻す
- DB 永続化: `curriculum_phases` / `curriculum_tasks` 2 テーブル。Python レジストリ
  (`backend/app/data/courses/{ai_driven_dev,ai_era_se}.py`) は起動時 cache 構築の
  フォールバック用に残置
- 起動時に `reload_from_db` で in-process cache を構築。空テーブルなら RuntimeError で停止
- multi-worker: publish 後 Redis pub/sub (`edu:curriculum:cache:invalidate`) で他 worker も reload（`CURRICULUM_CACHE_PUBSUB_ENABLED`、デフォルト true）

詳細は `docs/superpowers/plans/` を参照。
