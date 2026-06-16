# HANDOVER — Sprint 21 Phase 並び替え（2026-06-11）

## 状態

| 項目 | 値 |
|------|-----|
| branch | `main` |
| 最新 HEAD | `cc03ffd` |
| スプリント | Sprint 21 — admin Phase 並び替え |
| 前提 | Sprint 20 完了 |
| GitHub Actions | **success** — [#27628515482](https://github.com/y-hashiguchi/edu/actions/runs/27628515482) |

## 実装サマリ

| 操作 | API | 仕様 |
|------|-----|------|
| 並び替え | `POST /api/admin/curriculum/{slug}/phases/{phase_no}/move` | body: `{ to_phase_no }`。submission / progress / chat / embedding.phase をリマップ |

Phase 移動後は `source_ref` 内の phase 番号も変わるため、**course 全体の embeddings を arq で再 seed**（`enqueue_curriculum_embeddings_full`）。

### 主要ファイル

- `backend/app/services/curriculum_edit.py` — `move_phase`, `InvalidPhaseMoveError`
- `backend/app/api/admin/curriculum.py` — move route
- `backend/app/worker/curriculum_embeddings_job.py` — `run_curriculum_embeddings_full_job`
- `frontend/src/components/admin/CurriculumPhaseEditor.vue` — ↑↓ ボタン
- `frontend/src/stores/admin_curriculum.ts` — `movePhase`

## テストベースライン（ローカル）

| スイート | 結果 |
|----------|------|
| backend pytest | 495 passed |
| frontend vitest | 107 passed |

## 将来候補

- add_task 直後の embedding seed
- move_task 後の source_ref 整合
