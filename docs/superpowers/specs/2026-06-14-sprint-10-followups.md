# Sprint 10 follow-ups

**作成日:** 2026-06-14  
**対象:** コホート集計 dashboard（Sprint 10）

## 修正済み（review gate）

| ID | 内容 |
|----|------|
| HIGH-1 | `tag_heatmap` を active enrolled `user_ids` でスコープ |
| HIGH-2 | `average_score` を submission ごと最新 GradingAttempt 経由で決定 |
| MED-1 | E2E `login()` に optional `email` 引数 |
| MED-2 | `admin_cohort_rate_limit` を config に分離 |

## 残 follow-up

### LOW-1 — 短いメールのマスク

`_mask_email` は `local[:2]` を残すため `ab@x.com` などがほぼ全露出。  
`promote_admin.py` と同パターンを維持するか、`local[0]***` に統一するか Sprint 11 で判断。

### LOW-2 — CI の `ANTHROPIC_API_KEY` プレースホルダ

`.github/workflows/ci.yml` の `sk-ant-ci-placeholder` を GitHub secret 化するか、`CLAUDE_STUB_MODE=true` 時にキー省略可能かを確認。

### LOW-3 — コース二重ルックアップ

`get_course()` + DB `Course` クエリ。registry/DB 不整合時のログ改善は Sprint 11+。

## Sprint 9 carry-over（変更なし）

- **LOW-2** multi-worker cache invalidation — Sprint 11+
