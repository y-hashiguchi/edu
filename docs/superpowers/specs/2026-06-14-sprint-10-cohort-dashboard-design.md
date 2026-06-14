# Sprint 10 — コホート集計 admin dashboard アーキテクチャ設計

**作成日:** 2026-06-14
**前提 HEAD:** `2a2264a` (Sprint 9 完了 + Cursor Agent 引き継ぎ Phase 0/1)
**前提テスト:** backend 411 passed / frontend 94 passed / E2E 5 passed

---

## 1. ゴールと非目標

### ゴール

admin が **コース単位** で受講コホート全体の学習状況を把握できる集計 dashboard を追加する。Sprint 5/6 の個別受講者 dashboard（`GET /api/admin/users/{id}/dashboard`）の **上に載るコース横断ビュー** として設計し、運用者が「今コース全体で何が起きているか」を一目で見られるようにする。

### 含むもの (in-scope)

1. **Backend 集計 API** — `GET /api/admin/courses/{course_slug}/cohort-summary`（名称は plan で確定）
   - active enrollment 数
   - 平均スコア（最新 graded submission ベース、course スコープ）
   - フェーズ完了率（progress.completed / total phases）
   - stuck 受講者一覧（例: Phase N で 7 日以上 inactive、または提出 0）
   - skill_tags 弱点ヒートマップ（コース内 tag 別平均スコア Top N）
2. **集計ロジック** — 既存 [`admin_query.py`](../../backend/app/services/admin_query.py) / [`weakness.py`](../../backend/app/services/weakness.py) のパターンを **拡張**（新ドメイン乱立を避ける）
3. **Admin frontend** — `/admin/courses/:courseSlug/cohort` または `/admin/cohort?course=` ビュー
   - コース selector（Sprint 7 の course 一覧再利用）
   - サマリカード + stuck テーブル + tag ヒートマップ（テーブル/バッジで十分、chart ライブラリは不要）
4. **RBAC** — 既存 `get_current_admin` + `@limiter.limit`
5. **テスト** — service 単体 + API integration + vitest 1〜2 件

### 含まないもの (out-of-scope)

- 期別（cohort term / 入学バッチ）フィルタ — 将来 enrollment に `cohort_label` を足す sprint で対応
- リアルタイム SSE/WebSocket
- CSV エクスポート
- マルチワーカー cache invalidation (Sprint 9 LOW-2)
- ai-era-se Phase 2-4 コンテンツ投入（候補 B、別 track）
- broadcast 通知スケジュール（候補 D）

### 非機能要件

- backend 411 / frontend 94 を regression ゼロ維持
- 新規 backend ≈15 件、frontend ≈6 件、E2E 1 件（admin cohort smoke）
- 集計クエリは course_id で必ずスコープ（Sprint 7 パターン踏襲）
- N+1 禁止 — bulk 集計は 2〜3 クエリ以内

---

## 2. データソースと集計定義

### 既存テーブル（新規 migration 不要）

| テーブル | 用途 |
|---------|------|
| `enrollments` | active 受講者母集団 (`course_id`, `status='active'`) |
| `submissions` | 最新 score、提出日時 |
| `progress` | phase status（locked / in_progress / submitted / completed） |
| `curriculum_tasks` | skill_tags（published 列、runtime cache 経由でも可） |

### 指標定義（確定案）

| 指標 | 定義 |
|------|------|
| **enrolled_count** | `enrollments` where `course_id` + `status='active'` |
| **average_score** | 各 user の course 内 latest graded submission の平均（graded_at NOT NULL, score NOT NULL） |
| **completion_rate** | `completed_phases / total_phases` を user ごとに算出し平均（progress 行ベース） |
| **stuck_learners** | active enrollment かつ (a) 提出 0 かつ enroll から 7 日超、または (b) 最終提出から 7 日超かつ Phase 未完了 |
| **tag_heatmap** | submission → task の skill_tags を join し tag 別平均 score（MIN 提出数 2 は Sprint 5 `MIN_TAG_SUBMISSIONS` と整合） |

### stuck 閾値

- 定数 `COHORT_STUCK_INACTIVE_DAYS = 7`（`config.py`、テストでは 1 日に override 可）
- 将来 admin UI から変更する必要が出たら Sprint 11+

---

## 3. API 設計

### `GET /api/admin/courses/{course_slug}/cohort-summary`

**Query:** なし（Sprint 10）。course は path param（Sprint 9 と同 regex: `^[a-z0-9_-]{1,80}$`）

**Response 200:**

```json
{
  "course_slug": "ai-driven-dev",
  "course_title": "AI駆動型開発 補足カリキュラム",
  "enrolled_count": 42,
  "average_score": 73.5,
  "completion_rate": 0.35,
  "stuck_learners": [
    {
      "user_id": "...",
      "display_name": "山田",
      "email_masked": "ya***@example.com",
      "last_activity_at": "2026-06-01T12:00:00Z",
      "current_phase": 2,
      "submission_count": 3,
      "reason": "inactive_7d"
    }
  ],
  "tag_heatmap": [
    { "tag": "git", "average_score": 62.0, "submission_count": 18 }
  ]
}
```

**Errors:** 404 unknown slug / 403 non-admin

**Rate limit:** read 120/min（Sprint 9 admin curriculum read と同水準）

---

## 4. Frontend 設計

### Route

`/admin/cohort` — コース selector + 集計パネル（デフォルト: 最初の active コース or `ai-driven-dev`）

Admin ナビ（[`AdminLayout.vue`](../../frontend/src/layouts/AdminLayout.vue)）に「コホート」リンク追加。

### Store

`frontend/src/stores/admin_cohort.ts` — `fetchSummary(courseSlug)`、loading/error 状態

### Components（最小）

- `AdminCohortView.vue` — ページ本体
- 既存 `WeaknessCard` / `ProgressSummaryCard` は **個人向け** のため流用しない。数値カードは view 内に inline 実装（Sprint 10 scope 最小化）

---

## 5. セキュリティ / プライバシー

- stuck 一覧の email は **マスク**（Sprint 4 `promote_admin` と同パターン）
- 集計 API は admin のみ。learner 向け API には露出しない
- course_slug path regex で fast-fail（Sprint 9 LOW-1 踏襲）

---

## 6. テスト計画

| 層 | 内容 |
|----|------|
| backend unit | `compute_cohort_summary()` — 0 enroll / stuck 判定 / tag 集計 |
| backend API | admin 200 / learner 403 / unknown slug 404 |
| frontend vitest | store fetch + view render（mock API） |
| E2E | admin login → cohort ページ → enrolled_count 表示（数値 > 0 は seed 依存なので存在 assert のみ） |

---

## 7. 依存関係と実装順

1. `services/cohort_summary.py`（または `admin_query.py` へ関数追加 — plan で allowlist 確定）
2. schemas + API route
3. frontend store + view + router
4. tests + E2E
5. README + HANDOVER 更新

---

## 8. Sprint 9 follow-up との関係

- **LOW-2** (multi-worker cache): 本 sprint では触らない。cohort 集計は DB 直読みのため cache 不整合の影響を受けない
- Sprint 6 carry-over **MED-2 / MED-6** (判断保留): 本 sprint スコープ外

---

## 9. 成功基準

- admin が `/admin/cohort` で ai-driven-dev の enrolled / 平均スコア / stuck / tag ヒートマップを確認できる
- backend **≥426** passed、frontend **≥100** passed、E2E **6** passed
- HIGH review 指摘は同 sprint 内修正、MED/LOW は follow-up doc 化
