# HANDOVER — origin 同期 + CI green（2026-06-16）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main`（`origin/main` と同期済み） |
| 最新 HEAD | `e11235a` |
| GitHub Actions | **success**（backend / frontend / e2e） — [#27629342997](https://github.com/y-hashiguchi/edu/actions/runs/27629342997) |

## テストベースライン

| スイート | 結果 |
|----------|------|
| backend pytest | 497 passed |
| frontend vitest | 107 passed |
| Playwright E2E | 11 passed |

## 直近の主要機能（Sprint 11〜19 + follow-ups）

- 予約 broadcast（arq cron + admin UI）
- コホート CSV エクスポート + 入学バッチ（`cohort_label`）フィルタ
- enrollment `cohort_label` PATCH（受講者詳細 UI）
- **Sprint 14**: 入学バッチフィルタ E2E（`admin-cohort.spec.ts` 2 件目）
- **Sprint 15**: curriculum Phase 内 Task 追加・削除・並び替え → [`HANDOVER_2026-06-11_sprint15_done.md`](HANDOVER_2026-06-11_sprint15_done.md)
- **Sprint 16**: admin Course 追加・削除 + DB ベース enrollment → [`HANDOVER_2026-06-11_sprint16_done.md`](HANDOVER_2026-06-11_sprint16_done.md)
- **Sprint 17–19**: Phase 追加・削除 / embeddings 自動生成 / catalog 説明表示 → [`HANDOVER_2026-06-11_sprint17-19_done.md`](HANDOVER_2026-06-11_sprint17-19_done.md)
- **Sprint 20**: publish 時 task title 差分 embeddings 再生成（arq） → [`HANDOVER_2026-06-11_sprint20_done.md`](HANDOVER_2026-06-11_sprint20_done.md)
- **Sprint 21**: Phase 並び替え + embeddings 全件 refresh → [`HANDOVER_2026-06-11_sprint21_done.md`](HANDOVER_2026-06-11_sprint21_done.md)
- **Sprint 22**: ai-era-se 全シラバス catalog 説明同期 → [`HANDOVER_2026-06-11_sprint22_done.md`](HANDOVER_2026-06-11_sprint22_done.md)
- **Sprint 23**: add_task / move_task 後 embeddings 整合 → [`HANDOVER_2026-06-11_sprint23_done.md`](HANDOVER_2026-06-11_sprint23_done.md)
- **Sprint 24**: delete_task / delete_phase 後 embeddings 整理 → [`HANDOVER_2026-06-11_sprint24_done.md`](HANDOVER_2026-06-11_sprint24_done.md)
- **Sprint 25**: CI embedding stub（HF 429 回避） → [`HANDOVER_2026-06-11_sprint25_done.md`](HANDOVER_2026-06-11_sprint25_done.md)
- curriculum cache pub/sub（Redis、CI では無効 / notify は best-effort）
- Sprint 6 MED-2/MED-6（bulk weakness 閾値統一、admin-on-admin dashboard 404）

## ローカル起動

```bash
docker compose up -d postgres redis
cd backend && uv run alembic upgrade head
CLAUDE_STUB_MODE=true GRADING_ASYNC_ENABLED=false \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
make verify   # pytest + vitest
cd frontend && VITE_API_BASE_URL=http://127.0.0.1:8000 \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_tutor \
  npx playwright test
```

## 本番デプロイ

[`docs/infra/production-deploy.md`](docs/infra/production-deploy.md) を参照。

```bash
cp .env.example .env   # 本番シークレットを設定
make prod              # docker compose prod overlay
docker compose exec backend uv run python scripts/seed_embeddings.py  # 初回のみ（新規 course は API 作成時に自動 seed）
```

必須: migration head、`grading-worker`（採点 + 予約 broadcast）、`CLAUDE_STUB_MODE=false`、本番 `ANTHROPIC_API_KEY`。

## DB 不整合時

`alembic_version` のみでテーブルが空の場合（**pytest 実行後に dev DB を共有していると発生し得る**）:

```bash
docker compose exec -T postgres psql -U postgres -d ai_tutor \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
cd backend && uv run alembic upgrade head
```

## 次候補

- ~~Sprint 15: curriculum Phase/Task 追加・削除・並び替え~~ → [`HANDOVER_2026-06-11_sprint15_done.md`](HANDOVER_2026-06-11_sprint15_done.md)
- ~~Sprint 16: Course 追加・削除~~ → [`HANDOVER_2026-06-11_sprint16_done.md`](HANDOVER_2026-06-11_sprint16_done.md)
- ~~Phase 追加~~ / ~~embeddings 自動生成~~ / ~~catalog UI~~ → [`HANDOVER_2026-06-11_sprint17-19_done.md`](HANDOVER_2026-06-11_sprint17-19_done.md)
- ~~publish 時 embeddings 差分再生成~~ → [`HANDOVER_2026-06-11_sprint20_done.md`](HANDOVER_2026-06-11_sprint20_done.md)
- ~~Phase 並び替え~~ → [`HANDOVER_2026-06-11_sprint21_done.md`](HANDOVER_2026-06-11_sprint21_done.md)
- ~~ai-era-se コンテンツ拡充~~ → [`HANDOVER_2026-06-11_sprint22_done.md`](HANDOVER_2026-06-11_sprint22_done.md)
- ~~add_task / move_task embeddings 整合~~ → [`HANDOVER_2026-06-11_sprint23_done.md`](HANDOVER_2026-06-11_sprint23_done.md)
- ~~delete_task / delete_phase embeddings 整理~~ → [`HANDOVER_2026-06-11_sprint24_done.md`](HANDOVER_2026-06-11_sprint24_done.md)
- ~~CI HuggingFace 429 対策~~ → [`HANDOVER_2026-06-11_sprint25_done.md`](HANDOVER_2026-06-11_sprint25_done.md)
- TLS / 外部 LB / マネージド DB への production-deploy 拡張
