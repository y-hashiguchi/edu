# GitHub Actions CI セットアップ

**最終確認:** 2026-06-14（Cursor Agent Phase 0/1）

## 現状

| 項目 | 状態 |
|------|------|
| ワークフロー定義 | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) あり |
| `git remote` | **未設定**（2026-06-14 時点） |
| CI 初回実走 | remote push 待ち |
| 手動トリガ | `workflow_dispatch` 対応済み |

## ローカルベースライン（2026-06-14 再確認）

| スイート | 結果 |
|----------|------|
| backend pytest | **411 passed** |
| frontend vitest | **94 passed (24 files)** |
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

# stub 採点を有効にして backend 起動
CLAUDE_STUB_MODE=true GRADING_ASYNC_ENABLED=false \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  JWT_SECRET_KEY=test-secret ANTHROPIC_API_KEY=test-key \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8001

# 別ターミナル
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:8001 \
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
npm run test:e2e
```

`DATABASE_URL` は admin 昇格 CLI（`e2e/helpers.ts`）が API と同じ DB を参照するために必要。
