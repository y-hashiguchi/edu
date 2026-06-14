# Sprint 10 follow-ups

**作成日:** 2026-06-14  
**完了:** 2026-06-11（Sprint 12 follow-up batch）

## 修正済み（review gate）

| ID | 内容 |
|----|------|
| HIGH-1 | `tag_heatmap` を active enrolled `user_ids` でスコープ |
| HIGH-2 | `average_score` を submission ごと最新 GradingAttempt 経由で決定 |
| MED-1 | E2E `login()` に optional `email` 引数 |
| MED-2 | `admin_cohort_rate_limit` を config に分離 |

## 修正済み（Sprint 12）

| ID | 内容 |
|----|------|
| LOW-1 | `app.core.email_mask.mask_email` — local 先頭 1 文字のみ残す（`ab@x.com` → `a***@x.com`）。cohort + promote_admin で共有 |
| LOW-2 | `anthropic_api_key` を stub モード時 optional。CI E2E job から `ANTHROPIC_API_KEY` 削除 |
| LOW-3 | cohort API を `_get_course_by_slug` に統一。registry/DB 不整合時は enrollment で warning ログ |

## Sprint 9 carry-over（変更なし）

- **LOW-2** multi-worker cache invalidation — horizontal scale 時
