# HANDOVER — Sprint 16 Course 追加・削除（2026-06-11）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main`（`origin/main` 同期済み） |
| 最新 HEAD | `1ad1ad0` |
| Sprint 16 本体 | `fd71652` |
| GitHub Actions | **success** — [#27606460017](https://github.com/y-hashiguchi/edu/actions/runs/27606460017) |
| スプリント | Sprint 16 — admin Course 追加・削除 |
| 前提 | Sprint 15（Task 追加・削除・並び替え）完了 |

## テストベースライン（CI）

| スイート | 結果 |
|----------|------|
| backend pytest | 478 passed |
| frontend vitest | 105 passed |
| Playwright E2E | 10 passed |

## 実装サマリ

### Backend

| 操作 | API | 仕様 |
|------|-----|------|
| 追加 | `POST /api/admin/curriculum/courses` | slug / title / description。4 phase × 1 task scaffold。cache reload + pub/sub |
| 削除 | `DELETE /api/admin/curriculum/courses/{slug}` | `ai-driven-dev` / `ai-era-se` は 409。enrollment / submission ありは 409。cache evict (`-{slug}` pub/sub) |

**主要ファイル:**
- `backend/app/services/curriculum_course.py` — `add_course`, `delete_course`
- `backend/app/api/admin/curriculum.py` — create / delete routes
- `backend/app/schemas/admin_curriculum.py` — `AdminCourseCreateRequest/Out`
- `backend/app/data/courses/runtime.py` — `evict_course`
- `backend/app/services/curriculum_cache_pubsub.py` — `-{slug}` で evict 伝播
- `backend/app/services/enrollment.py` — `_get_course_by_slug` を DB のみに（`COURSE_REGISTRY` 依存除去）
- `backend/app/api/auth.py` — register の course 検証を DB + cache reload に
- `backend/app/api/admin/users.py` — admin enroll も DB ベースに

### Frontend

- `AdminCurriculumListView.vue` — 「+ コースを追加」フォーム、保護以外のコースに削除ボタン
- `stores/admin_curriculum.ts` — `createCourse`, `deleteCourse`
- `types/admin_curriculum.ts` — `PROTECTED_COURSE_SLUGS`, create DTOs

### Tests（ローカル）

| スイート | 追加・更新 |
|----------|------------|
| `test_curriculum_course_service.py` | 新規 4 件 |
| `test_admin_curriculum_api.py` | create/delete API 4 件 |
| `test_auth_api_course.py` | dynamic course register 1 件 |
| `admin-curriculum.spec.ts` | course create/delete E2E 1 件 |

**E2E 修正:** DELETE 204 後に `page.reload()`（Sprint 15 task delete と同パターン、`f2c6a29`）

## コミット履歴

```
1ad1ad0 docs(handover): record Sprint 16 CI green at f2c6a29
f2c6a29 fix(e2e): reload curriculum list after course delete for stable assert
fd71652 feat(sprint-16): add admin course create/delete and DB-based enrollment
6281e8a docs(handover): record Sprint 15 CI green at 0af99bb
```

## 未実施（次セッション）

- [x] `HANDOVER_2026-06-14_local-dev-ready.md` HEAD 更新

## 将来候補

- Phase 追加（`submissions.phase BETWEEN 1 AND 4` CHECK migration 要）
- 新規 course 作成時の embeddings 自動生成
- catalog UI で動的 course の説明文表示
