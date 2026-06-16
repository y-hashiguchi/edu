# HANDOVER — Sprint 23 Task 構造変更時 embeddings 整合（2026-06-11）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main` |
| スプリント | Sprint 23 — add_task / move_task 後の embedding 更新 |
| 前提 | Sprint 22 完了 |

## 実装サマリ

| 操作 | embedding 更新 |
|------|----------------|
| Task 追加 (`POST .../tasks`) | 新 task の `source_ref` のみ差分 seed（`enqueue_curriculum_embeddings`） |
| Task 並び替え (`POST .../tasks/{n}/move`) | course 全体 re-seed（`enqueue_curriculum_embeddings_full`） |

`source_ref` は 0-based task index を使うため、move_task 後は move_phase と同様に全件 refresh が必要。

### 主要ファイル

- `backend/app/api/admin/curriculum.py` — `post_task` / `reorder_task` 後 enqueue
- `backend/tests/test_admin_curriculum_api.py` — enqueue 呼び出し検証

## テストベースライン（ローカル）

| スイート | 結果 |
|----------|------|
| backend pytest | 497 passed |

## 将来候補

- delete_task 後の orphan embedding 整理 / full reseed
- CI HuggingFace 429 対策（embedding テスト mock 化）
- TLS / 外部 LB / マネージド DB への production-deploy 拡張
