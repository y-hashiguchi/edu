# Sprint 7 follow-up tickets

> 起点: `docs/superpowers/specs/2026-06-10-sprint-7-multi-course-architecture-design.md`
> 完了 sprint: Sprint 7 (commits 31812b4..ff73e1b, merged main TBD)
> ベースライン: backend 345 / frontend 81 (Sprint 7 完了時 — target は 338 / 79 で両方達成超過)
> 起点ハンドオフメモ: `docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md` (Task 22 で削除)

## HIGH

なし。Sprint 7 内で発生した CRITICAL 問題は同 sprint 内で同梱修正済み。

## MEDIUM

### ✅ MED-1: `progress.complete_phase` / `progress.is_phase_unlocked` を course スコープ化 — **2026-06-11 完了**

`is_phase_unlocked`、`complete_phase`、`list_progress`、`_get`、`maybe_mark_submitted` に `course_id` 引数（Optional）を追加。`complete_phase` には次フェーズ存在チェック用に `course_slug` も追加し、コースレジストリから phase 存在を判定する設計に。`api/submissions.py`、`api/chat.py`、`api/progress.py`、`services/submission.py` の呼び出し側を更新。完了 commit: TBD.

### ✅ MED-2: `services/rag.py:search_curriculum_tasks` の `course_id` フィルタ追加 — **2026-06-11 完了**

`search_context`、`search_curriculum_tasks` の両方に `course_id` 引数（Optional）を追加し、`.where(Embedding.course_id == course_id)` を SQL に注入。`api/chat.py` と `services/recommendation.py` の呼び出し側を更新。完了 commit: TBD.

### ✅ MED-3: `admin/AdminSubmissionDetailView.vue` のダウンロード URL がデフォルトコースで決め打ち — **2026-06-11 完了**

Backend: `AdminSubmissionDetail` schema に `course_slug: str` を追加、`admin_query.get_submission_detail` で Course も join、`api/admin/submissions.py` で値を埋める。Frontend: `types/admin.ts` に `course_slug` 追加、`AdminSubmissionDetailView.vue` で `store.selectedSubmission?.course_slug` を使用。完了 commit: TBD.

### ✅ MED-4: `compute_top_weakness_tags_bulk` 戻り値の二重 (user_id, course_id) — **2026-06-11 完了**

サイレントなデータロスを防ぐため、重複 user_id が `user_course_pairs` に含まれた場合は `ValueError` を投げるようにバリデーション追加。将来の `(uid, cid)`-keyed バージョンへの移行パスを docstring に明記。完了 commit: TBD.

## LOW

### ✅ LOW-2: `POST /api/admin/users/{id}/enrollments` admin 経由の追加 enroll API — **2026-06-11 完了**

新規 router 1 本（`AdminEnrollRequest` schema、403 / 422 / 404 / 409 / 201 マッピング）+ `enroll_user` + `initialize_progress_for_course` 再利用。新規テスト 5 件追加。完了 commit: TBD.

### ✅ LOW-1: ai-era-se Phase 2-4 投入 — **2026-06-11 完了**

`ai_era_se.py` に Phase 2〜4（計 10+8+5 課題）を追加。Alembic で既存 enroll 受講者に phase 2-4 の locked progress をバックフィル。

### ✅ LOW-3: `scripts/seed_embeddings.py` の `source_ref` をコース付きに統一 — **2026-06-11 完了**

`course:{slug}:phase:N:task:N` 形式に統一。Alembic で ai-driven-dev 既存行をプレフィックス付与。`rag.parse_curriculum_task_coords` が両形式をパース。

### ✅ LOW-4: broadcast 通知のコーススコープ化 — **2026-06-11 完了**

`POST /api/admin/notifications/broadcast` + `notifications.course_id` 列 + AdminNotifyView の「コース一斉送信」タブ。

### ✅ LOW-5: HomeView.spec.ts の Vue Router warning — **2026-06-11 完了**

テスト router に `/` フォールバックを追加し、`router.push` で初期ルートを設定。

### LOW-6: Sprint 6 follow-up からのキャリーオーバー — **部分完了 2026-06-11**

| 項目 | 状態 |
|------|------|
| MED-2 (bulk weakness threshold) | ✅ 2026-06-14 完了 |
| MED-6 (admin-on-admin dashboard) | ✅ 2026-06-14 完了 |
| LOW-4 (vitest CVE GHSA-5xrq-8626-4rwp) | ✅ vitest `^3.2.6` に upgrade、CI で `npm audit --audit-level=critical` |
| LOW-5 / INFRA-1 (Playwright headless CI) | ✅ `frontend/e2e/smoke.spec.ts` + `.github/workflows/ci.yml` |

### LOW-7: 採点ジョブの非同期化 / curriculum 編集機能

- 採点非同期化 → **Sprint 8 完了**（Redis + arq worker）
- curriculum 編集機能（admin GUI）→ 未着手（別 sprint、LOW-6 prompt injection 防御と同梱予定）
