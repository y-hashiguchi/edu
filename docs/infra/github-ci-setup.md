# GitHub Actions CI セットアップ

**最終確認:** 2026-06-11（Sprint 11 完了後）

## 現状

| 項目 | 状態 |
|------|------|
| ワークフロー定義 | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) あり |
| `git remote` | `origin` → https://github.com/y-hashiguchi/edu |
| **visibility** | **PRIVATE**（ユーザー方針 2026-06-11） |
| CI（private 時） | **startup_failure の可能性大** — 下記 § startup_failure 参照 |
| ローカルゲート | backend **438** / frontend **102** / E2E **7**（Sprint 11 後） |
| 手動トリガ | `workflow_dispatch` 対応済み（runner 割当があれば） |

## ローカルベースライン（2026-06-11 — Sprint 11）

| スイート | 結果 |
|----------|------|
| backend pytest | **438 passed** |
| frontend vitest | **102 passed (27 files)** |
| E2E Playwright | **7 passed** |
| frontend build | green |
| npm audit (critical) | 0 vulnerabilities |

## remote 設定手順

```bash
cd /Volumes/Seagate3TB/projects/edu

# 既存 GitHub リポジトリに接続する場合
git remote add origin git@github.com:<org>/<repo>.git
git push -u origin main

# 新規作成する場合（gh CLI）
gh repo create <repo-name> --private --source=. --remote=origin --push
```

push または PR 作成後、GitHub の Actions タブで 3 job（`backend` / `frontend` / `e2e`）が green であることを確認する。

## Actions startup_failure（0 jobs）— **private repo 運用時は想定内**

**症状:** 実行時間 0 秒、`jobs: []`、ログなし。

**原因:** private repo + アカウント Actions 制限で hosted runner が割り当てられない。

**本リポ方針（2026-06-11）:** **Private のまま運用**。CI green は保証しない。

**推奨ゲート（push 前）:**

```bash
cd backend && uv run pytest -q
cd frontend && npm test -- --run
# backend 起動後
cd frontend && VITE_API_BASE_URL=http://127.0.0.1:8000 npx playwright test
```

**CI を private で動かす場合:** https://github.com/settings/billing で Actions / spending limit / 支払い方法を設定する。

**参考（2026-06-14）:** 一時 public 化で CI green を確認済み（run `27491047097`）。private に戻すと再び startup_failure になり得る。

## workflow 構成

1. **backend** — postgres service + migrate + `pytest -q`
2. **frontend** — `npm ci` + vitest + `npm audit --audit-level=critical`
3. **e2e** — migrate + backend (8000) + preview (4173) + Playwright
   - `CLAUDE_STUB_MODE=true` で deterministic 採点
   - admin curriculum E2E は register 後 `scripts.promote_admin` を Playwright から実行

## ローカル E2E

```bash
docker compose up -d postgres
cd backend && uv run alembic upgrade head

# stub 採点 + 同期採点で backend 起動（grading-worker 不要）
CLAUDE_STUB_MODE=true GRADING_ASYNC_ENABLED=false \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_tutor \
  REDIS_URL=redis://127.0.0.1:6379/0 \
  JWT_SECRET_KEY=test-secret ANTHROPIC_API_KEY=test-key \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# 別ターミナル
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:8000 \
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_tutor \
npm run test:e2e
```

`DATABASE_URL` は admin 昇格 CLI（`e2e/helpers.ts`）が API と同じ DB を参照するために必要。
