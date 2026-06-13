# Sprint 9 Follow-ups

Sprint 9 (admin curriculum editing GUI) の code-reviewer / security-reviewer で出た MEDIUM / LOW 項目を別スプリントで処理するためのチケット集。HIGH × 3 は同 sprint 内 (`854a252`) で処理済み。

参照:
- Spec: `docs/superpowers/specs/2026-06-13-sprint-9-curriculum-editing-design.md`
- Plan: `docs/superpowers/plans/2026-06-13-ai-tutor-curriculum-sprint-9.md`
- Branch HEAD: `feature/sprint-9` (post-fix `854a252`)

---

## MED-1: draft 列に `min_length=1` を付与

**Source:** code-reviewer (MEDIUM)
**File:** `backend/app/schemas/admin_curriculum.py:80-90` (`AdminPhaseUpdateRequest`, `AdminTaskUpdateRequest`)

`title` / `description` / `goal` / `system_prompt` などは `str | None = Field(default=None, max_length=...)` で `min_length=1` がない。`{"title": ""}` を受け付けて `draft_title = ""` になる。publish で `title = ""` になり実質 NOT NULL を裏切る。

**Fix:** 各 nullable str field に `min_length=1` を付与。`{"title": ""}` は 422。`{"title": null}` は引き続き「draft クリア」として有効。

```python
title: str | None = Field(default=None, min_length=1, max_length=200)
```

`deliverable` / `week_label` は仕様上 "空文字 = 明示的に空" のセンチネル運用なので除外。

---

## MED-2: `normalized_skill_tags()` の silent truncation を 422 に

**Source:** code-reviewer (MEDIUM)
**File:** `backend/app/schemas/admin_curriculum.py:107-108`

50 文字超のタグを silent に drop しているため、ユーザは入力が消えた理由を知る術がない。debounce store は API レスポンスを正として上書きするので、知らない間にタグが消える UX 劣化。

**Fix:** `len(t) > 50` を検出したら `ValueError` を上げて 422 にする (Pydantic validator パターン)。重複除去はそのまま残す。

---

## MED-3: read endpoints に rate-limit を付与

**Source:** security-reviewer (MEDIUM)
**File:** `backend/app/api/admin/curriculum.py:72`, `91`

`list_courses` と `get_detail` に `@limiter.limit(...)` が付いていない。compromised admin token / ループスクリプトで draft 含む全コース内容を無制限に enumerate できる。`get_detail` は 4 DB round-trip で重い。

**Fix:** 既存の `admin_curriculum_write_rate_limit` (120/min) を read にも適用、または新たに `admin_curriculum_read_rate_limit` を追加。

---

## MED-4: registry fallback を per-slug 判定に

**Source:** code-reviewer (MEDIUM)
**File:** `backend/app/data/courses/__init__.py:62-66`

現状 `if runtime._CACHE:` で cache が一つでも入っていれば fallback off。部分的な `reload_from_db` 失敗 (例: 1 course だけ入った状態) で `get_course("ai-era-se")` が `CourseNotFoundError` になる。

**Fix:** `slug not in runtime._CACHE` のときも fallback を試す。ただし production では cache が常に完備されるため影響は限定的、優先度低。

---

## MED-5: `system_prompt` 脅威モデルを文書化

**Source:** security-reviewer (MEDIUM)
**File:** `backend/app/api/admin/curriculum.py:133`, `backend/app/api/chat.py` の system_prompt 注入箇所

`system_prompt` (8000 chars) はそのまま Claude prompt に注入される。compromised admin が学習者全員の chat 挙動を改変・PII 漏洩・grading 偏向できる、という threat model がコード上に明示されていない。

**Fix:** route と column に privileged field である旨のコメント追加。`admin_curriculum_systemprompt_rate_limit` のような更に厳しめ limit、もしくは 2FA 要件を検討 (後者は別スプリント案件)。

---

## LOW-1: `course_slug` Path param に regex 制約

**Source:** security-reviewer (LOW)
**File:** `backend/app/api/admin/curriculum.py:93, 131, 164, 199, 223`

`course_slug: str = Path(...)` に pattern 指定がない。ORM の WHERE は parameterized で安全だが、極端に長い slug でも DB round-trip までは届く。

**Fix:** `Path(..., pattern=r"^[a-z0-9_-]{1,80}$")` で fast-fail。

---

## LOW-2: Multi-worker 環境での cache 不整合 (記録のみ)

**Source:** security-reviewer (LOW)
**File:** `backend/app/data/courses/runtime.py:14-15`

publish は当該ワーカーの process-local cache しか更新しない。uvicorn を multi-worker で運用すると他ワーカーは再起動 or 再 reload まで旧値を返す。現状は single-worker 運用前提なので OK。

**Fix:** horizontal scale 時に Redis pub/sub or SIGUSR1 trigger reload を追加。Sprint 10+ 候補。

---

## LOW-3: Alembic seed の `course_id` UUIDs を Sprint 7 migration と相互参照

**Source:** code-reviewer (LOW)
**File:** `backend/alembic/versions/20260613_53858e23cd1b_sprint9_curriculum_editing.py:34-35`

`AI_DRIVEN_DEV_UUID` / `AI_ERA_SE_UUID` の literal が Sprint 7 migration の seed と一致することを保証する仕組みがない。今は手動で確認しているだけ。

**Fix:** Sprint 7 migration の revision id をコメント参照、または `test_curriculum_seed_migration.py` に 「migration 適用後に courses 表で UUID 一致」を assert するテストを追加。

---

## LOW-4: `store.publish()` の戻り値拡充 (or 削除)

**Source:** code-reviewer (HIGH の関連事項。HIGH-1 は param 統一のみ実施)
**File:** `frontend/src/stores/admin_curriculum.ts:82`, `frontend/src/views/admin/AdminCurriculumEditView.vue:66-68`

view が `published_phase_count` / `published_task_count` を message に出すために `api.adminPublishCurriculum` を直接叩いている。store の publish action は view から呼ばれず、debounce-PUT エラーは `store.saveError` 経由、publish エラーは view ローカル `message` 経由で channel が分裂。

**Fix:** store の `publish` を `PublishResult` 返却に変更し view から `store.publish()` 経由で受ける。エラー channel も `store.publishError` に統一。

---

## ステータス

| ID | Severity | Source | Owner | 状態 |
|----|----------|--------|-------|------|
| MED-1 | M | code-reviewer | TBD | open |
| MED-2 | M | code-reviewer | TBD | open |
| MED-3 | M | security-reviewer | TBD | open |
| MED-4 | M | code-reviewer | TBD | open |
| MED-5 | M | security-reviewer | TBD | open (doc only) |
| LOW-1 | L | security-reviewer | TBD | open |
| LOW-2 | L | security-reviewer | TBD | open (Sprint 10+) |
| LOW-3 | L | code-reviewer | TBD | open |
| LOW-4 | L | code-reviewer | TBD | open |

HIGH × 3 (publish cache-after-commit / audit log / route param `:courseSlug`) は同 sprint 内コミット `854a252` で対応済み。
