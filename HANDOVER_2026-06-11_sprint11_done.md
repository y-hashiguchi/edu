# Sprint 11 完了 — 引き継ぎメモ

**作成日:** 2026-06-11  
**前提 HEAD:** `1e0013e` (Sprint 11 コミット済み)  
**前提テスト:** backend **438** / frontend **102** / E2E **7**（修正後）

---

## 1. Sprint 11 サマリ

**テーマ:** 予約 broadcast 通知（候補 D）

admin がコース一斉通知を **指定日時（JST 入力 → UTC 保存）** に予約し、arq 毎分 cron が due 行を `broadcast_to_course` で配信する。

| 成果物 | パス |
|--------|------|
| Spec | [`docs/superpowers/specs/2026-06-11-sprint-11-scheduled-broadcast-design.md`](docs/superpowers/specs/2026-06-11-sprint-11-scheduled-broadcast-design.md) |
| Plan | [`docs/superpowers/plans/2026-06-11-ai-tutor-curriculum-sprint-11.md`](docs/superpowers/plans/2026-06-11-ai-tutor-curriculum-sprint-11.md) |
| Migration | `b2c3d4e5f6a7` → `scheduled_broadcasts` |
| API | `POST/GET/DELETE /api/admin/notifications/.../schedule(d)` |
| Worker | `run_scheduled_broadcast_cron`（毎分） |
| UI | `AdminNotifyView` — 予約一斉タブ |

---

## 2. テストベースライン

```bash
cd backend && uv run pytest -q          # 438 passed
cd frontend && npm test -- --run        # 102 passed
# E2E（backend 起動 + migrate 済み）
cd frontend && VITE_API_BASE_URL=http://127.0.0.1:8000 \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_tutor \
  npx playwright test
```

---

## 3. 運用メモ

### 3.1 Migration

```bash
cd backend
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_tutor
export JWT_SECRET_KEY=... ANTHROPIC_API_KEY=...
uv run alembic upgrade head
```

### 3.2 予約配信を動かす

即時 `/broadcast` は API 同期。予約は **arq worker 必須**:

```bash
cd backend && arq app.worker.settings.WorkerSettings
```

`scheduled_broadcast_cron_enabled=true`（デフォルト）で毎分 due スキャン。

### 3.3 ローカル E2E

`.env` の `DATABASE_URL` が `postgres` ホストの場合は `127.0.0.1` に上書き。  
8000 が占有中なら既存 uvicorn を `--reload` 再起動するか PID を解放。

---

## 4. GitHub — **Private リポジトリ**

**ユーザー方針:** リポジトリは **Private** で運用。

| 項目 | 内容 |
|------|------|
| CI 症状 | private + Actions 制限 → **startup_failure**（0 jobs、ログなし） |
| 回避策 A | [GitHub Billing](https://github.com/settings/billing) で Actions 利用枠 / spending limit を有効化 |
| 回避策 B | 一時 public 化（2026-06-14 に実施済みだったが private に戻す場合は再発） |
| 回避策 C | **ローカル検証** — 上記 pytest / vitest / playwright を push 前ゲートとする |
| 手動 CI | private で runner が使えるようになれば `workflow_dispatch` で再実行 |

詳細: [`docs/infra/github-ci-setup.md`](docs/infra/github-ci-setup.md)

> **注意:** push 後 GitHub Actions が green でも private 制限下では startup_failure のままのことがある。ローカル 438/102/7 passed を正とする。

---

## 5. Sprint 10 follow-up / 次候補

| 項目 | 内容 |
|------|------|
| Sprint 10 LOW | [`docs/superpowers/specs/2026-06-14-sprint-10-followups.md`](docs/superpowers/specs/2026-06-14-sprint-10-followups.md) |
| Sprint 9 LOW-2 | multi-worker cache invalidation (Redis pub/sub) |
| ~~候補 B~~ | ai-era-se Phase 2-4 — **Sprint 9 migration で DB 済み** |

---

## 6. コミット

- `1e0013e` — `feat(sprint-11): add scheduled course broadcast notifications`
- **push:** 未実施（private repo — ローカルゲート推奨）

---

## 7. 引き継ぎチェックリスト

- [ ] `alembic upgrade head`（本番 / ステージング）
- [ ] arq worker デプロイ（予約配信）
- [ ] private repo なら CI 期待値をローカルゲートに切替
- [ ] コミットメッセージ例: `feat(sprint-11): scheduled course broadcast notifications`
