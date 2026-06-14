# HANDOVER — Sprint 12 完了（2026-06-11）

## 実装内容

### コホート CSV エクスポート（Sprint 10 out-of-scope 解消）

| 領域 | 内容 |
|------|------|
| **Service** | `backend/app/services/cohort_csv.py` — summary / stuck / tag 3 セクション CSV |
| **API** | `GET /api/admin/courses/{slug}/cohort-summary/export` → `text/csv` + attachment |
| **Frontend** | `AdminCohortView.vue`「CSV エクスポート」ボタン + `api.downloadCohortCsv` |
| **Tests** | `test_cohort_csv.py`, `test_admin_cohort_api.py` export 3 件, `AdminCohortView.spec.ts` |

### 運用

| 領域 | 内容 |
|------|------|
| **Makefile** | `make verify` — backend + frontend テスト（private CI 代替ゲート） |

## 直前までのコミット（未 push 想定）

```
5011de8 feat(cache): sync curriculum cache across workers via Redis pub/sub
dca32fa fix(follow-ups): tighten email mask and simplify cohort course lookup
96b6fc1 docs: record Sprint 11 commit ref in handover
1e0013e feat(sprint-11): add scheduled course broadcast notifications
```

## ローカル検証

```bash
make verify          # backend pytest + frontend vitest
make test-e2e        # backend 起動後（CLAUDE_STUB_MODE=true）
```

## 次候補

- `git push`（明示依頼時）
- cohort term / 入学バッチフィルタ（`cohort_label` 列が必要）
- Sprint 6/5 判断保留項目（bulk weakness threshold 等）
