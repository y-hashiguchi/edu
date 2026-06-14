# Sprint 10 — コホート集計 admin dashboard 実装プラン

**Goal:** [spec](../specs/2026-06-14-sprint-10-cohort-dashboard-design.md) に従い、admin 向けコース単位コホート集計 dashboard を追加する。

**前提 HEAD:** `2a2264a`
**前提テスト:** backend 411 / frontend 94 / E2E 5

---

## 共通の前提（ANTI-HALLUCINATION — subagent 必読）

1. 本セクションと linked spec が **唯一の真実**
2. 各 Task の **修正ファイル allowlist 以外は変更禁止**
3. 各 Step 開始前に `git status` を実行
4. 既存 service の course 解決は `get_course()` / `CourseContext` パターンを維持
5. **`types.py` / `ai_driven_dev.py` / `ai_era_se.py` は変更しない**
6. 新規 Alembic migration **不要**（集計のみ）
7. 外部プロトタイプは存在しない

---

## Task 1: cohort 集計 service

**Files (allowlist):**
- Create: `backend/app/services/cohort_summary.py`
- Create: `backend/tests/test_cohort_summary_service.py`
- Modify: `backend/app/config.py`（`cohort_stuck_inactive_days: int = 7` のみ）

**Steps:**
1. `compute_cohort_summary(db, *, course_id, course_slug)` を実装
2. stuck / tag_heatmap / average_score / completion_rate を spec 定義どおり
3. pytest 8〜10 件

**Commit:** `feat(sprint-10): cohort summary aggregation service`

---

## Task 2: schema + admin API

**Files (allowlist):**
- Create: `backend/app/schemas/admin_cohort.py`
- Create: `backend/app/api/admin/cohort.py`
- Modify: `backend/app/main.py`（router include のみ）
- Create: `backend/tests/test_admin_cohort_api.py`

**Steps:**
1. Pydantic response models
2. `GET /api/admin/courses/{course_slug}/cohort-summary`
3. `get_current_admin` + rate limit + course_slug regex
4. API tests 5 件

**Commit:** `feat(sprint-10): admin cohort-summary API`

---

## Task 3: frontend store + types

**Files (allowlist):**
- Create: `frontend/src/types/admin_cohort.ts`
- Create: `frontend/src/stores/admin_cohort.ts`
- Modify: `frontend/src/lib/api.ts`（admin fetch helper 1 関数）
- Create: `frontend/src/__tests__/admin_cohort.store.spec.ts`

**Commit:** `feat(sprint-10): admin cohort store + API client`

---

## Task 4: AdminCohortView + ナビ

**Files (allowlist):**
- Create: `frontend/src/views/admin/AdminCohortView.vue`
- Modify: `frontend/src/router/admin.ts`
- Modify: `frontend/src/layouts/AdminLayout.vue`（nav link 1 行）
- Create: `frontend/src/__tests__/AdminCohortView.spec.ts`

**Commit:** `feat(sprint-10): admin cohort dashboard view`

---

## Task 5: E2E + docs

**Files (allowlist):**
- Create: `frontend/e2e/admin-cohort.spec.ts`
- Modify: `README.md`（Sprint 10 1 行 + cohort 運用）
- Modify: `HANDOVER_2026-06-14_sprint9_done.md` → 新 HANDOVER 追記 or Sprint 10 セクション

**Steps:**
1. admin promote helper 再利用（`e2e/helpers.ts`）
2. cohort ページ smoke
3. 全 regression: `make test` + `npx playwright test`

**Commit:** `test(sprint-10): admin cohort E2E smoke + docs`

---

## Task 6: review gate

- code-reviewer + security-reviewer
- HIGH → 同 sprint 修正
- MED/LOW → `docs/superpowers/specs/2026-06-XX-sprint-10-followups.md`

---

## 検証コマンド

```bash
make test
cd frontend && npx playwright test
cd frontend && npm run build
```

**目標:** backend ≥426 / frontend ≥100 / E2E 6 passed

---

## 見積もり

| Task | 規模 |
|------|------|
| 1 service | M |
| 2 API | M |
| 3 store | S |
| 4 view | M |
| 5 E2E + docs | S |
| 6 review | S |

**合計:** 1 PR（feature/sprint-10）→ main FF マージ
