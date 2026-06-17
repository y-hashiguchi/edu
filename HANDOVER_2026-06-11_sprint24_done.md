# HANDOVER — Sprint 24 delete 後 embeddings 整理（2026-06-11）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main` |
| スプリント | Sprint 24 — delete_task / delete_phase 後 embedding 整理 |
| 前提 | Sprint 23 完了 |

## 実装サマリ

| 操作 | embedding 更新 |
|------|----------------|
| Task 削除 | course 全体 re-seed + orphan 削除（`enqueue_curriculum_embeddings_full`） |
| Phase 削除 | 同上 |

### prune ロジック

`prune_orphan_course_embeddings` が `curriculum_task` / `curriculum_skill` のうち、現行カリキュラムに存在しない `source_ref` を DB から削除。full reseed job の末尾で実行。

### 主要ファイル

- `backend/app/services/curriculum_embeddings.py` — `prune_orphan_course_embeddings`
- `backend/app/worker/curriculum_embeddings_job.py` — full job に prune 追加
- `backend/app/api/admin/curriculum.py` — `remove_task` / `remove_phase` 後 enqueue

## テストベースライン（ローカル）

| スイート | 結果 |
|----------|------|
| backend pytest | 498 passed |

## 将来候補

- CI HuggingFace 429 対策（embedding テスト mock 化）
- TLS / 外部 LB / マネージド DB への production-deploy 拡張
