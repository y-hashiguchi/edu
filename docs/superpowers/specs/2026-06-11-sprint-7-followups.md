# Sprint 7 follow-up tickets

> 起点: `docs/superpowers/specs/2026-06-10-sprint-7-multi-course-architecture-design.md`
> 完了 sprint: Sprint 7 (commits 31812b4..ff73e1b, merged main TBD)
> ベースライン: backend 345 / frontend 81 (Sprint 7 完了時 — target は 338 / 79 で両方達成超過)
> 起点ハンドオフメモ: `docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md` (Task 22 で削除)

## HIGH

なし。Sprint 7 内で発生した CRITICAL 問題は同 sprint 内で同梱修正済み。

## MEDIUM

### MED-1: `progress.complete_phase` / `progress.is_phase_unlocked` を course スコープ化

Task 12 で route 層は `CourseContext` 依存になったが、`app/services/progress.py` の `complete_phase(db, user_id, phase)` と `is_phase_unlocked(db, user_id, phase)` は単一コース時の (user_id, phase) シグネチャのまま。複数コース enroll 時に同一 phase 番号の進行状態が混在しうる。

- 影響: 1 ユーザが 2 コースに enroll してかつ両コースで同一 phase 番号がある場合のみ。現状の 2 コース構成では ai-era-se Phase 1 (週次 8 課題) vs ai-driven-dev Phase 1 (環境 3 課題) が衝突する潜在パス。
- 対応: 両関数に `course_id: uuid.UUID` 必須引数を追加し、各クエリに `.where(Progress.course_id == course_id)` を追加。`api/progress.py` と `api/chat.py`、`api/submissions.py` の呼び出し側を更新。
- 工数: 半日

### MED-2: `services/rag.py:search_curriculum_tasks` の `course_id` フィルタ追加

Task 11 で `recommendation.py` から RAG 検索結果を `course_task_lookup` でフィルタする防御を入れたが、`Embedding` クエリ自体に `course_id` 条件がない。ハンドオフメモの follow-up 候補。

- 影響: 2 コースの埋め込み内容が類似していると、cosine 類似度上位に他コースの行が混入し、フィルタ後に推薦数が想定より少なくなる
- 対応: `search_curriculum_tasks(db, embedder, query, phase=None, k=10, course_id=None)` を追加し、ユーザのアクティブコースを必須化
- 工数: 半日

### MED-3: `admin/AdminSubmissionDetailView.vue` のダウンロード URL がデフォルトコースで決め打ち

`AdminSubmissionDetailView` の admin file download path に `course_slug='ai-driven-dev'` がハードコード。`AdminSubmissionDetail` payload に `course_slug` が含まれていないため。

- 影響: SE コースの submission の admin file download が `?course=ai-driven-dev` で要求されるため、admin の他コース閲覧パスとして矛盾するが、enrollment 不要なので 200 は返る。視認性低い不整合
- 対応: backend `AdminSubmissionDetail` schema に `course_slug: str` を追加 → frontend 側で `submission.course_slug` を引数に渡す
- 工数: 1 時間

### MED-4: `compute_top_weakness_tags_bulk` 戻り値の二重 (user_id, course_id) → top tag 化

現状: `(uid, cid)` ペアを受け取って `{uid: top_tag}` を返す。同じ uid が複数 (uid, cid) ペアにあると後勝ち。admin/users 一覧では各ユーザ "primary course" 1 つだけ渡しているので問題ないが、将来コース別の弱点を admin に出すなら戻り値も `(uid, cid)` キーに拡張要。

- 影響: 将来の admin UI 拡張時に発覚
- 対応: 仕様変更時に戻り値型を `dict[tuple[uuid.UUID, uuid.UUID], str | None]` に
- 工数: 1 時間

## LOW

### LOW-1: ai-era-se Phase 2-4 投入

シラバス第 9〜48 週分を `backend/app/data/courses/ai_era_se.py` に追加。Phase 2 (実践、12 週) / Phase 3 (AI 活用、16 週) / Phase 4 (自律発信、12 週)。各フェーズの `system_prompt` 末尾に Phase 別 評価基準を埋め込む。

- 投入順: パイロット (Phase 1) 完走後に Phase 2 → Phase 3 → Phase 4
- 工数: 各フェーズ 1 日 (本文転記が中心)

### LOW-2: `POST /api/admin/users/{id}/enrollments` admin 経由の追加 enroll API

現状は SQL 直叩きでないと追加 enroll できない。

- 対応: 新規 router 1 本 + `services/enrollment.enroll_user` 再利用 + schema 1 件 (`AdminEnrollRequest`) + admin guard
- 工数: 半日

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
