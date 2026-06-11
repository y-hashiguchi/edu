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

### LOW-1: ai-era-se Phase 2-4 投入

シラバス第 9〜48 週分を `backend/app/data/courses/ai_era_se.py` に追加。Phase 2 (実践、12 週) / Phase 3 (AI 活用、16 週) / Phase 4 (自律発信、12 週)。各フェーズの `system_prompt` 末尾に Phase 別 評価基準を埋め込む。

- 投入順: パイロット (Phase 1) 完走後に Phase 2 → Phase 3 → Phase 4
- 工数: 各フェーズ 1 日 (本文転記が中心)

### LOW-3: `scripts/seed_embeddings.py` の `source_ref` をコース付きに統一

Task 16 で seed_embeddings は course 別ループに変更したが、ai-driven-dev は `phase:N:task:N` 形式のままで ai-era-se だけ `course:slug:phase:N:task:N` 形式。

- 対応: 既存行を `course:ai-driven-dev:phase:N:task:N` に書き換える migration + scripts も統一
- 工数: 半日

### LOW-4: broadcast 通知のコーススコープ化

broadcast 機能本体は Sprint 8+ で実装予定だが、その際 `course_id` 別にスコープする設計が必要。

### LOW-5: HomeView.spec.ts の Vue Router warning

Task 17-20 で実装した HomeView spec が `No match found for location with path ""` を出す。テスト自体は通るが warning が増える。

- 対応: `router.push` を spec 内で呼ぶか、テスト router のフォールバックルートを定義
- 工数: 30 分

### LOW-6: Sprint 6 follow-up からのキャリーオーバー

Sprint 6 で持ち越した残件:
- MED-2 (bulk weakness threshold documentation) — 判断保留
- MED-6 (admin-on-admin dashboard threat model) — 判断保留
- LOW-4 (vitest CVE upgrade)
- LOW-5 (Playwright headless 環境整備)

### LOW-7: 採点ジョブの非同期化 / curriculum 編集機能

Sprint 6 で挙げられた長期候補。Sprint 7 で着手せず。

## INFRA

### INFRA-1: Playwright headless 環境整備 (Sprint 5 carry-over)

MCP playwright 駆動の手動 E2E に依存している状態。CI で自動 smoke E2E を回したい。
