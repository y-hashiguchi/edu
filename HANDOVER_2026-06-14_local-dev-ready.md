# HANDOVER — ローカル dev 復旧 + 未 push 9 commits（2026-06-14）

## テストベースライン

| スイート | 結果 |
|----------|------|
| backend pytest | 459 passed |
| frontend vitest | 103 passed |
| Playwright E2E | 7 passed |

## 未 push コミット（`origin/main` より ahead）

```
d2ec753 fix(notify): refresh scheduled list after booking to avoid duplicates
26d1af2 feat(admin): allow PATCH of enrollment cohort_label from user detail
d9b1779 feat(sprint-13): add enrollment cohort_label filter for cohort dashboard
9c5be95 feat(sprint-12): add cohort summary CSV export and make verify gate
5011de8 feat(cache): sync curriculum cache across workers via Redis pub/sub
dca32fa fix(follow-ups): tighten email mask and simplify cohort course lookup
96b6fc1 docs: record Sprint 11 commit ref in handover
1e0013e feat(sprint-11): add scheduled course broadcast notifications
```

## ローカル起動手順

```bash
docker compose up -d postgres redis

# DB 不整合時（alembic_version のみ等）
docker compose exec -T postgres psql -U postgres -d ai_tutor \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

cd backend
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_tutor
uv run alembic upgrade head

CLAUDE_STUB_MODE=true GRADING_ASYNC_ENABLED=false \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
# E2E
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:8000 \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/ai_tutor \
  npx playwright test

# ユニットのみ
make verify
```

## 予約 broadcast 運用

- arq worker 必須: `make worker` または docker `grading-worker`
- cron 毎分で `scheduled_broadcasts` を処理

## Private リポ CI

- GitHub Actions は private だと startup_failure になり得る
- push 前ゲート: `make verify` + E2E（backend 起動後）
