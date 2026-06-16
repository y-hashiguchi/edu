# HANDOVER — Sprint 16 Course 追加・削除（2026-06-11）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main`（未 push — ローカル実装完了） |
| スプリント | Sprint 16 — admin Course 追加・削除 |
| 前提 | Sprint 15（Task 追加・削除・並び替え）完了 |

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
| `admin_curriculum.store.spec.ts` | create/delete store 2 件 |

**backend pytest（フル）:** 478 passed

## 未実施（次セッション）

- [x] git commit / push / CI（本セッションで実施）
- [x] Playwright E2E（course create → list 表示 → delete）
- [ ] `HANDOVER_2026-06-14_local-dev-ready.md` HEAD 更新（CI green 後）

## 将来候補

- Phase 追加（`submissions.phase BETWEEN 1 AND 4` CHECK migration 要）
- 新規 course 作成時の embeddings 自動生成
- catalog UI で動的 course の説明文表示
