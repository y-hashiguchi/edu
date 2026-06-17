# GitHub Actions CI セットアップ

**最終確認:** 2026-06-17

## 現状

| 項目 | 状態 |
|------|------|
| ワークフロー定義 | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) あり |
| `git remote` | `origin` → https://github.com/y-hashiguchi/edu |
| **visibility** | **PRIVATE**（ユーザー方針 2026-06-11） |
| CI（private 時） | **startup_failure の可能性大** — 下記 § startup_failure 参照 |
| ローカルゲート | backend **511 passed, 1 skipped** / frontend **108** / E2E **11** |
| 手動トリガ | `workflow_dispatch` 対応済み（runner 割当があれば） |

## ローカルベースライン（2026-06-17）

| スイート | 結果 |
|----------|------|
| backend pytest | **511 passed, 1 skipped** |
| frontend vitest | **108 passed (28 files)** |
| E2E Playwright | **11 passed** |
| frontend build | green |
| production Compose config | green |
| Terraform fmt/validate | green |
| production Docker build | backend + frontend green |
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

push または PR 作成後、GitHub の Actions タブで 4 job（`backend` / `frontend` / `docker-build` / `e2e`）が green であることを確認する。

## Actions startup_failure（0 jobs）— **private repo 運用時は想定内**

**症状:** 実行時間 0 秒、`jobs: []`、ログなし。

**原因:** private repo + アカウント Actions 制限で hosted runner が割り当てられない。

**本リポ方針（2026-06-11）:** **Private のまま運用**。CI green は保証しない。

**推奨ゲート（push 前）:**

```bash
cd backend && uv run pytest -q
cd frontend && npm test -- --run
make lint
make docker-build
make test-e2e
```

**CI を private で動かす場合:** https://github.com/settings/billing で Actions / spending limit / 支払い方法を設定する。

**参考（2026-06-14）:** 一時 public 化で CI green を確認済み（run `27491047097`）。private に戻すと再び startup_failure になり得る。

## workflow 構成

1. **backend** — postgres service + migrate + Ruff + `pytest -q`
2. **frontend** — `npm ci` + type lint + vitest + `npm audit --audit-level=critical`
3. **docker-build** — backend / frontend production image build
4. **e2e** — migrate + backend (8000) + preview (4173) + Playwright
   - `CLAUDE_STUB_MODE=true` で deterministic 採点
   - admin curriculum E2E は register 後 `scripts.promote_admin` を Playwright から実行

## ローカル E2E

```bash
make test-e2e
```

`make test-e2e` は既存の `ai_tutor` DB には触れず、専用の `ai_tutor_e2e` DB を作成して migration を適用し、stub 採点 + 同期採点の backend を一時起動してから Playwright を実行する。終了時に backend と `ai_tutor_e2e` DB は削除される。

`DATABASE_URL` は admin 昇格 CLI（`e2e/helpers.ts`）が API と同じ DB を参照するために必要なため、Makefile が frontend 側にも同じ E2E DB URL を渡す。
