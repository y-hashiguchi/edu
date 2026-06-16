# HANDOVER — Sprint 20 publish embeddings 差分再生成（2026-06-11）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main` |
| スプリント | Sprint 20 — publish 時 embeddings 差分再生成（arq） |
| 前提 | Sprint 17–19 完了（`bbb938a`） |

## 実装サマリ

### 動作

1. admin が task **title** の draft を publish
2. `publish_course` が変更タスクの `source_ref` を `PublishResult.embedding_source_refs` に収集
3. publish API が cache reload 後 `enqueue_curriculum_embeddings` を呼ぶ
4. arq worker（または `GRADING_ASYNC_ENABLED=false` 時は inline）が `seed_course_embeddings_refs` で差分のみ re-embed

title 以外の draft（skill_tags / description 等）のみの publish では embedding job は走らない。

### 主要ファイル

| ファイル | 役割 |
|----------|------|
| `backend/app/services/curriculum_edit.py` | `PublishResult.embedding_source_refs` |
| `backend/app/services/curriculum_embeddings.py` | `task_embedding_source_ref`, `seed_course_embeddings_refs` |
| `backend/app/worker/curriculum_embeddings_job.py` | arq entrypoint |
| `backend/app/worker/enqueue.py` | `enqueue_curriculum_embeddings` |
| `backend/app/worker/settings.py` | worker functions に job 追加 |
| `backend/app/api/admin/curriculum.py` | publish 後 enqueue |

### Tests

| ファイル | 内容 |
|----------|------|
| `test_curriculum_edit_service.py` | refs 収集 / title 以外 skip |
| `test_curriculum_embeddings.py` | refs フィルタ upsert |
| `test_curriculum_embeddings_enqueue.py` | inline enqueue + publish API |
| `test_admin_curriculum_api.py` | idempotent publish で mock |

## テストベースライン（ローカル）

| スイート | 結果 |
|----------|------|
| backend pytest | 492 passed |

## 未実施 / 将来候補

- Phase 並び替え（Task move と同様）
- add_task 直後の embedding seed（publish フロー外）
- move_task 後の source_ref インデックス整合（全 course reseed）
