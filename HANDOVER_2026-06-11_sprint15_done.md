# HANDOVER — Sprint 15 完了（2026-06-11）

## 実装内容

### Curriculum Task 構造編集（Sprint 9 out-of-scope）

| 操作 | API | 備考 |
|------|-----|------|
| **追加** | `POST .../phases/{phase_no}/tasks` | Phase 末尾に published task を即 INSERT |
| **削除** | `DELETE .../tasks/{task_no}` | 提出あり → 409、最後の 1 件 → 409 |
| **並び替え** | `POST .../tasks/{task_no}/move` `{ to_task_no }` | submission の task_no も更新 |

- Phase 追加・削除は MVP 外（`submissions.phase BETWEEN 1 AND 4` CHECK のため）
- 構造変更後は `runtime.reload_course` + Redis cache notify（publish と同様）
- コンテンツ編集（draft → publish）フローは従来どおり

## 触った主要ファイル

- `backend/app/services/curriculum_edit.py` — `add_task` / `delete_task` / `move_task`
- `backend/app/api/admin/curriculum.py` — 3 エンドポイント
- `frontend/src/components/admin/CurriculumPhaseEditor.vue` — 「+ Task を追加」
- `frontend/src/components/admin/CurriculumTaskEditor.vue` — ↑↓ / 削除
- `frontend/e2e/admin-curriculum.spec.ts` — 追加・削除 E2E（2 件目）

## テスト

| スイート | 結果 |
|----------|------|
| backend pytest | **469 passed** |
| frontend vitest | **103 passed** |
| Playwright E2E | **9 passed**（+1、要 API + DB 起動）

## ローカル確認

```bash
make verify
cd frontend && VITE_API_BASE_URL=http://127.0.0.1:8000 \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_tutor \
  npx playwright test e2e/admin-curriculum.spec.ts
```

## 次候補

- Course 追加・削除
- Phase 追加（CHECK 制約 migration 要）
- embeddings 自動再生成（Task タイトル変更時）
- `git commit` / `push` / CI（明示依頼時）
