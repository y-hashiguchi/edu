# AI Tutor プロジェクト引き継ぎドキュメント

**最終更新:** 2026-06-14  
**プロジェクト:** `/Volumes/Seagate3TB/projects/edu`  
**main HEAD:** `93a2a00`  
**Branch 状態:** clean（Sprint 10 + INFRA E2E を main にコミット済み）

> 前回引き継ぎ: [`HANDOVER_2026-06-14_sprint9_done.md`](HANDOVER_2026-06-14_sprint9_done.md)

---

## 1. プロジェクト概要

FastAPI + Vue 3 + PostgreSQL + pgvector の AI 駆動型開発カリキュラム学習支援ツール。Claude API を採点・対話・ナッジに使用。マルチコース (`ai-driven-dev` / `ai-era-se`)。

| 層 | 採用 |
|----|------|
| Backend | FastAPI + async SQLAlchemy + pgvector + arq + Redis |
| Frontend | Vue 3 + Pinia + TypeScript + vite 8 + vitest 4 |
| Auth | JWT + bcrypt + `is_admin` RBAC |
| Test | pytest **426** / vitest **100** / Playwright **6** |
| Infra | Docker Compose + GitHub Actions CI（remote 未設定） |

---

## 2. Sprint 完了状況（〜10）

| Sprint | 内容 | 状態 |
|--------|------|------|
| 0–8 | （略 — Sprint 9 handover 参照） | 完了 |
| 9 | カリキュラム編集 admin GUI + cache + draft→publish | 完了 |
| **10** | **コホート集計 admin dashboard** | **完了** |
| 10+ INFRA | CI workflow_dispatch + E2E helpers + admin-curriculum skip 解消 | 完了 (`7d3ae4b`) |

---

## 3. Sprint 10 で実装した主要設計

### 3.1 集計 API

- `GET /api/admin/courses/{course_slug}/cohort-summary`
- 指標: `enrolled_count`, `average_score`, `completion_rate`, `stuck_learners`, `tag_heatmap`
- stuck 閾値: `cohort_stuck_inactive_days=7`（`config.py`）
- 集計は **active enrollment の user_ids でスコープ**（tag_heatmap 含む）
- `average_score`: submission ごと最新 GradingAttempt → user ごと最新提出の 2 段階 DISTINCT
- Rate limit: `admin_cohort_rate_limit`（120/min）

### 3.2 Frontend

- Route: `/admin/cohort`（Admin ナビ「コホート」）
- Store: `stores/admin_cohort.ts`
- View: `AdminCohortView.vue`（コース selector + サマリカード + stuck テーブル + tag ヒートマップ）

### 3.3 主要ファイル

```
backend/app/services/cohort_summary.py
backend/app/schemas/admin_cohort.py
backend/app/api/admin/cohort.py
backend/tests/test_cohort_summary_service.py
backend/tests/test_admin_cohort_api.py
frontend/src/views/admin/AdminCohortView.vue
frontend/src/stores/admin_cohort.ts
frontend/e2e/admin-cohort.spec.ts
frontend/e2e/helpers.ts
docs/superpowers/specs/2026-06-14-sprint-10-cohort-dashboard-design.md
docs/superpowers/plans/2026-06-14-ai-tutor-curriculum-sprint-10.md
docs/superpowers/specs/2026-06-14-sprint-10-followups.md
```

---

## 4. 現在のテスト数

| 指標 | 値 |
|------|-----|
| backend pytest | **426 passed** |
| frontend vitest | **100 passed (26 files)** |
| E2E Playwright | **6 passed** |
| build | green |

---

## 5. 残課題 / 次 Sprint 候補

### 5.1 Sprint 10 follow-up（LOW）

[`docs/superpowers/specs/2026-06-14-sprint-10-followups.md`](docs/superpowers/specs/2026-06-14-sprint-10-followups.md)

- メールマスク短アドレス、CI API key プレースホルダ、コース二重ルックアップ

### 5.2 Sprint 9 carry-over

- **LOW-2** multi-worker cache invalidation — マルチワーカー化時に Redis pub/sub 等

### 5.3 Sprint 11 候補

| 候補 | 内容 | 推奨度 |
|------|------|--------|
| **B. ai-era-se Phase 2-4 投入** | Phase 1 (8 課題) 以外を GUI から投入・運用検証 | 中 |
| **C. マルチワーカー cache (INFRA)** | Sprint 9 LOW-2 同梱 | 低（同梱可） |
| **D. broadcast 通知高度化** | `scheduled_at` + arq スケジュール配信 | 中 |

---

## 6. INFRA / E2E 運用メモ

### 6.1 GitHub Actions

- **remote:** https://github.com/y-hashiguchi/edu（push 済み）
- **CI:** `startup_failure`（0 jobs）— アカウント Actions 課金/制限を要確認（[docs/infra/github-ci-setup.md](docs/infra/github-ci-setup.md)）

### 6.2 ローカル E2E（Colima + 外部ディスク）

- `docker compose up --build backend` は Colima マウントエラーになる場合あり（`/Volumes/Seagate3TB`）
- **回避:** ホスト uvicorn + `DATABASE_URL=...@127.0.0.1:5432/...`

```bash
cd backend && set -a && . ../.env && set +a && \
  export DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_tutor" \
         REDIS_URL="redis://127.0.0.1:6379/0" \
         CLAUDE_STUB_MODE=true GRADING_ASYNC_ENABLED=false && \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

cd frontend && VITE_API_BASE_URL=http://127.0.0.1:8000 npx playwright test
```

`promote_admin` CLI には `DATABASE_URL` / `JWT_SECRET_KEY` / `ANTHROPIC_API_KEY` が必要（`e2e/helpers.ts` 参照）。

---

## 7. 直近 git log

```
93a2a00 feat(sprint-10): add admin cohort summary dashboard
7d3ae4b chore(infra): enable admin E2E in CI with promote helper
2a2264a docs: add Sprint 9 done handover for next AI assistant
```

---

## 8. 引き継ぎチェックリスト（新 AI 用）

- [ ] 本書 + Sprint 10 spec/plan/followups を読む
- [ ] `pytest -q` / `npm test -- --run` で 426 / 100 を確認
- [ ] E2E は backend 再起動後に 6 passed を確認
- [ ] 次 Sprint は brainstorming → spec → plan → 実装
- [ ] commit / push / PR はユーザ明示要求時のみ
