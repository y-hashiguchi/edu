# HANDOVER — Sprint 13 完了（2026-06-11）

## 実装内容

### 入学バッチ（cohort_label）フィルタ

| 領域 | 内容 |
|------|------|
| **DB** | `enrollments.cohort_label`（nullable, migration `c3d4e5f6a7b8`） |
| **Service** | `compute_cohort_summary(cohort_label=…)` / `list_cohort_labels` |
| **API** | `GET .../cohort-labels`, `?cohort_label=` on summary + export |
| **Admin enroll** | `POST .../enrollments` に optional `cohort_label` |
| **Frontend** | コホート画面「入学バッチ」selector + CSV/集計連動 |

## テスト

| スイート | 結果 |
|----------|------|
| backend pytest | **453 passed** |
| frontend vitest | **103 passed** |

## Migration

```bash
cd backend && uv run alembic upgrade head
```

## 直前コミット

```
9c5be95 feat(sprint-12): add cohort summary CSV export and make verify gate
```

## 次候補

- 既存 enrollment の cohort_label 更新 API（PATCH）
- Sprint 6/5 保留項目
- `git push`（明示依頼時）
