# Sprint 11 — 予約 broadcast 通知 実装プラン

**Goal:** [spec](../specs/2026-06-11-sprint-11-scheduled-broadcast-design.md) に従い、admin 向け予約一斉通知を追加する。

**前提 HEAD:** `5e744e3`
**前提テスト:** backend 426 / frontend 100 / E2E 6

---

## 共通の前提（ANTI-HALLUCINATION — subagent 必読）

1. 本セクションと linked spec が **唯一の真実**
2. 各 Task の **修正ファイル allowlist 以外は変更禁止**
3. 各 Step 開始前に `git status` を実行
4. 既存 `broadcast_to_course` / link validator / rate limit パターンを **再利用**
5. **`types.py` / `ai_driven_dev.py` / `ai_era_se.py` は変更しない**
6. 新規 Alembic migration **1 本のみ**（`scheduled_broadcasts`）
7. 外部プロトタイプは存在しない

---

## Task 1: migration + model + config

**Files (allowlist):**
- Create: `backend/alembic/versions/20260611_*_scheduled_broadcasts.py`
- Create: `backend/app/models/scheduled_broadcast.py`
- Modify: `backend/app/models/__init__.py`（export のみ）
- Modify: `backend/app/config.py`（spec §6 の 4 定数）

**Steps:**
1. `ScheduledBroadcast` SQLAlchemy model
2. Alembic upgrade/downgrade
3. `alembic upgrade head` ローカル確認

**Commit:** `feat(sprint-11): scheduled_broadcasts table`

---

## Task 2: schedule service + tests

**Files (allowlist):**
- Create: `backend/app/services/scheduled_broadcast.py`
- Create: `backend/tests/test_scheduled_broadcast_service.py`
- Modify: `backend/app/schemas/notification.py`（Schedule DTO のみ）

**Steps:**
1. `create_scheduled_broadcast(...)` — validation + insert pending
2. `cancel_scheduled_broadcast(...)` — pending only
3. `list_scheduled_broadcasts(...)` — filter + order
4. `process_due_scheduled_broadcasts(db)` — SKIP LOCKED + broadcast + status update
5. pytest 6 件

**Commit:** `feat(sprint-11): scheduled broadcast service`

---

## Task 3: admin API + tests

**Files (allowlist):**
- Modify: `backend/app/api/admin/notifications.py`
- Create: `backend/tests/test_admin_scheduled_broadcast_api.py`

**Steps:**
1. POST `/broadcast/schedule`
2. GET `/scheduled`
3. DELETE `/scheduled/{id}`
4. API tests 5 件

**Commit:** `feat(sprint-11): admin scheduled broadcast API`

---

## Task 4: arq cron job

**Files (allowlist):**
- Create: `backend/app/worker/scheduled_broadcast_job.py`
- Modify: `backend/app/worker/settings.py`（cron_jobs 追加）
- Create: `backend/tests/test_scheduled_broadcast_job.py`

**Steps:**
1. `process_due_scheduled_broadcasts` arq wrapper（SessionLocal 取得）
2. `WorkerSettings.cron_jobs` — `scheduled_broadcast_cron_enabled` でガード
3. test 1 件（due 1 行 → sent）

**Commit:** `feat(sprint-11): arq cron for scheduled broadcasts`

---

## Task 5: frontend types + API + store

**Files (allowlist):**
- Modify: `frontend/src/types/notification.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/stores/admin.ts`
- Create: `frontend/src/__tests__/adminScheduledBroadcast.spec.ts`

**Steps:**
1. types + api helpers
2. store actions: `scheduleBroadcast`, `fetchScheduledBroadcasts`, `cancelScheduledBroadcast`
3. vitest 2 件

**Commit:** `feat(sprint-11): frontend scheduled broadcast store`

---

## Task 6: AdminNotifyView UI

**Files (allowlist):**
- Modify: `frontend/src/views/admin/AdminNotifyView.vue`

**Steps:**
1. 3 タブ（個別 / 即時一斉 / 予約一斉）
2. datetime-local (JST) → ISO UTC POST
3. 予約一覧 + キャンセル

**Commit:** `feat(sprint-11): admin notify scheduled broadcast UI`

---

## Task 7: E2E + docs + regression

**Files (allowlist):**
- Create: `frontend/e2e/admin-scheduled-broadcast.spec.ts`
- Modify: `README.md`（1 行追記）
- Create: `HANDOVER_2026-06-11_sprint11_done.md`（Task 完了後）

**Steps:**
1. E2E: admin login → schedule tab → create → list shows pending
2. `pytest -q` → 438+ passed
3. `npm test -- --run` → 104+ passed
4. `npx playwright test` → 7+ passed
5. HANDOVER 作成

**Commit:** `test(sprint-11): scheduled broadcast E2E + handover`

---

## Review gate（Task 7 後）

- [ ] spec の out-of-scope ファイル未変更
- [ ] idempotent 配信テストあり
- [ ] JST ラベル UI 確認
- [ ] CI green（push はユーザ依頼時）

---

## 見積もり

| Task | 目安 |
|------|------|
| 1–4 backend | 半日 |
| 5–6 frontend | 半日 |
| 7 E2E + docs | 2h |
