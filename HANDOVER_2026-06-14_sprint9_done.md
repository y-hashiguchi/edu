# AI Tutor プロジェクト引き継ぎドキュメント

**最終更新:** 2026-06-14
**プロジェクト:** `/Volumes/Seagate3TB/projects/edu`
**main HEAD:** `baf9bf4`
**Branch 状態:** clean (Sprint 9 + follow-up を main にマージ済み)

> 前回引き継ぎ (2026-06-01 Sprint 0 開始時) は `HANDOVER_ai_tutor_curriculum.md` を参照。本書は Sprint 9 完了時点での状態。

---

## 1. プロジェクト概要

FastAPI + Vue 3 + PostgreSQL + pgvector の AI 駆動型開発カリキュラム学習支援ツール (リファレンス実装)。Claude API を採点 + 対話 + ナッジに使い、マルチコース (`ai-driven-dev` / `ai-era-se`) 構成。

### スタック

| 層 | 採用 |
|----|------|
| Backend | FastAPI + async SQLAlchemy + asyncpg + Alembic + pgvector + fastembed + slowapi + arq + Redis |
| Frontend | Vue 3 + Pinia + TypeScript + Vue Router + vite 8 + vitest 4 |
| Auth | JWT (Bearer) + bcrypt + `is_admin` フラグベース RBAC |
| AI | Claude API (採点=Sonnet, ナッジ=Haiku、stub mode は CI 用 `CLAUDE_STUB_MODE`) |
| Test | pytest (backend 411 passed) / vitest (frontend 94 passed) / Playwright (E2E **5 passed**) |
| Infra | Docker Compose (`make dev`) + GitHub Actions CI |

詳細は `~/.claude/projects/-Volumes-Seagate3TB-projects-edu/memory/edu_stack_and_conventions.md` を参照。

---

## 2. 開発フロー (確立済み運用ルール)

```
brainstorming → spec → writing-plans → subagent-driven-development → review (HIGH 同 sprint 内修正 / MED/LOW follow-up doc 化) → main FF マージ
```

- **HIGH issues**: 同 sprint 内で修正してからマージ
- **MEDIUM / LOW issues**: `docs/superpowers/specs/YYYY-MM-DD-sprint-X-followups.md` に記録、別 sprint で消化
- **subagent dispatch には必ず CRITICAL ANTI-HALLUCINATION GUARDS** を明記:
  1. plan の「共通の前提」セクションを唯一の真実とする
  2. 修正ファイル allowlist の外を変更しない
  3. 各 Step 開始前に `git status`
  4. 既存 service ファイル (Sprint 7 以降は `get_course()` 経由) は変更しない
  5. `types.py` / `ai_driven_dev.py` / `ai_era_se.py` は変更しない (`__init__.py` rewire 除く)
  6. Alembic seed は `COURSE_REGISTRY` を import しない (dict literal で凍結)
  7. 外部プロトタイプは存在しないと仮定
- **git 操作 (commit / PR / merge) はユーザ明示要求時のみ**

詳細は memory: `edu_sprint_workflow.md` / `edu_review_handling.md`。

---

## 3. これまでの Sprint 完了状況

| Sprint | 内容 | 状態 |
|--------|------|------|
| 0 | スケルトン + カリキュラム配信 + AIチューター対話 MVP | 完了 |
| 1 | PostgreSQL + JWT + 進捗管理 + 会話履歴永続化 | 完了 |
| 2 | 課題提出 + Claude JSON 採点 + RAG (pgvector + fastembed) | 完了 |
| 3 | ファイル/画像添付 + Vision multimodal 採点 + 採点履歴 + 再採点 | 完了 |
| 4 | admin ダッシュボード (RBAC + 受講者一覧 + コメント + 通知) + CSP + per-IP rate limit | 完了 |
| 5 | 受講者 dashboard (弱点分析 + レコメンド + AI 一言 + 進捗サマリ) + TaskItem skill_tags | 完了 |
| 6 | 双方向コミュニケーション (コメント返信スレッド + admin NotificationCenter) | 完了 |
| 7 | マルチコース化 (`courses` / `enrollments` + course_id FK + ai-era-se Phase 1 パイロット) | 完了 |
| 8 | 採点非同期化 (Redis + arq worker) | 完了 |
| **9** | **カリキュラム編集 admin GUI (curriculum_phases / curriculum_tasks + draft→publish + cache + RBAC) + follow-up MED×5 + LOW×3** | **完了** |
| **10** | **コホート集計 admin dashboard（spec/plan 作成済み — 実装未着手）** | **計画済** |

---

## 4. Sprint 9 で実装した主要設計 (継続的に重要)

### 4.1 Curriculum データモデル

- 既存の Python レジストリ (`backend/app/data/courses/{ai_driven_dev,ai_era_se}.py`) は **起動時 cache 構築のフォールバック用** に残置
- 実 runtime ソースは DB の 2 テーブル: `curriculum_phases` / `curriculum_tasks`
- **Same-row draft/published パターン**: published 列と `draft_*` 列が同じ行に並ぶ
- **編集セマンティクス**: PUT body は `model_dump(exclude_unset=True)` で送信、service は `if field in payload` で「省略=変更なし、明示 None=draft クリア、値=draft 設定」を判別
- **skill_tags は JSONB** で `list[str]` ラウンドトリップ
- **deliverable / week_label の空文字 = 明示的に空** のセンチネル運用 (publish 時 NULL に正規化)

### 4.2 In-process cache (`runtime._CACHE`)

- 起動時 lifespan で `runtime.reload_from_db(db)` → cache 構築 (空テーブルなら RuntimeError で起動失敗)
- `publish_course` 後に **`runtime.reload_course(db, slug)` を route 層で `db.commit()` の後** に呼ぶ (Sprint 9 review HIGH で order 確定)
- **registry fallback は per-slug** (`runtime._CACHE.get(slug)` → None なら `COURSE_REGISTRY[slug]`)。これにより部分 reload 失敗時にも別 course を取得可能 (Sprint 9 follow-up MED-4)

### 4.3 Admin curriculum API (`backend/app/api/admin/curriculum.py`)

- 6 routes: GET 一覧 / GET 詳細 / PUT phase / PUT task / POST publish / POST discard
- 全 route が `Depends(get_current_admin)` + `@limiter.limit(...)` + course_slug regex (`^[a-z0-9_-]{1,80}$`)
- Rate limit: write 120/min、publish 10/min
- publish/discard は admin email + 影響行数を `INFO` ログ出力 (audit)
- `system_prompt` (8000 chars) は privileged field — route 直前に脅威モデルコメント

### 4.4 Frontend 構成

- Store: `frontend/src/stores/admin_curriculum.ts`
- **500ms debounce + per-(phase|task) key + merge + latest-wins**
- `publish()` は `PublishOut` を返却 (view が件数 message を出すため)
- Components: `AdminCurriculumListView` → `AdminCurriculumEditView` → `CurriculumPhaseEditor` → `CurriculumTaskEditor` + `SkillTagInput`
- Route: `/admin/curriculum` / `/admin/curriculum/:courseSlug` (`props: true`)

---

## 5. 現在のテスト数 + 主要ファイル

| 指標 | 値 |
|------|-----|
| backend pytest | **411 passed** |
| frontend vitest | **94 passed (24 files)** |
| E2E Playwright | **4 passed + 1 skipped** (`admin-curriculum.spec.ts` は CI に admin 昇格手順がないため skip) |
| build | green (frontend `npm run build` ~500ms) |
| security audit | npm 0 vulnerabilities |

### 主要新規ファイル (Sprint 9)
```
backend/app/models/curriculum_phase.py
backend/app/models/curriculum_task.py
backend/app/data/courses/runtime.py
backend/app/services/curriculum_edit.py
backend/app/schemas/admin_curriculum.py
backend/app/api/admin/curriculum.py
backend/alembic/versions/20260613_53858e23cd1b_sprint9_curriculum_editing.py
frontend/src/stores/admin_curriculum.ts
frontend/src/types/admin_curriculum.ts
frontend/src/components/admin/{SkillTagInput,CurriculumPhaseEditor,CurriculumTaskEditor}.vue
frontend/src/views/admin/{AdminCurriculumListView,AdminCurriculumEditView}.vue
docs/superpowers/specs/2026-06-13-sprint-9-curriculum-editing-design.md
docs/superpowers/plans/2026-06-13-ai-tutor-curriculum-sprint-9.md
docs/superpowers/specs/2026-06-14-sprint-9-followups.md
```

---

## 6. 残課題 / 次にやるべきこと

### 6.1 Sprint 9 残 follow-up

- **LOW-2 (multi-worker cache invalidation)**: 現状 uvicorn single-worker 前提。本番マルチワーカー化時に Redis pub/sub or SIGUSR1 trigger reload を追加。Sprint 10+ で対応予定。

### 6.2 Sprint 10 — コホート集計 dashboard（完了）

**2026-06-11 実装:**
- Backend: `services/cohort_summary.py` + `GET /api/admin/courses/{slug}/cohort-summary`
- Frontend: `/admin/cohort`（`AdminCohortView.vue` + `stores/admin_cohort.ts`）
- E2E: `frontend/e2e/admin-cohort.spec.ts`（6 件目）
- Review follow-ups: [`docs/superpowers/specs/2026-06-14-sprint-10-followups.md`](docs/superpowers/specs/2026-06-14-sprint-10-followups.md)
- 目標テスト: backend **426** / frontend **100** / E2E **6**

Spec/plan:
- [`docs/superpowers/specs/2026-06-14-sprint-10-cohort-dashboard-design.md`](docs/superpowers/specs/2026-06-14-sprint-10-cohort-dashboard-design.md)
- [`docs/superpowers/plans/2026-06-14-ai-tutor-curriculum-sprint-10.md`](docs/superpowers/plans/2026-06-14-ai-tutor-curriculum-sprint-10.md)

### 6.3 INFRA carry-over

- CI 初回実走: **remote 未設定** — [docs/infra/github-ci-setup.md](docs/infra/github-ci-setup.md) 参照。`workflow_dispatch` 追加済み（2026-06-14）
- ローカルベースライン（2026-06-11）: backend **426** / frontend **100** / E2E **6** 想定
- admin-curriculum E2E: skip 解除 + `promote_admin` ヘルパー（`frontend/e2e/helpers.ts`）

---

## 7. 重要な運用情報

### 7.1 Docker runtime

- **Colima** を使用 (memory: `docker_runtime.md` 参照。旧 `HANDOVER_ai_tutor_curriculum.md` の Rancher Desktop 記載と異なる)

### 7.2 開発コマンド

```bash
make dev                # postgres + backend + frontend + redis + grading-worker
make migrate            # alembic upgrade head
make seed-embeddings    # curriculum を embeddings テーブルに投入
make test               # backend + frontend
make worker             # arq worker をローカル直接起動

cd backend && uv run pytest -q                              # backend regression
cd frontend && npm test -- --run                            # frontend regression
cd frontend && npm run build                                # frontend build verify
cd frontend && npx playwright test                          # E2E
cd backend && uv run python -m scripts.promote_admin <email>  # admin 昇格
```

### 7.3 環境変数の要点

- `CLAUDE_STUB_MODE=true`: E2E + CI 用に Claude を stub。送信 body の "stub:weak/ok/great" マーカーでスコア固定 (55/75/92)
- `GRADING_ASYNC_ENABLED=true`: arq worker で非同期採点 (デフォルト)。テストでは `false`
- `RATE_LIMIT_ENABLED=true`: slowapi 有効。テストでは `false`
- `BCRYPT_ROUNDS=4`: CI 速度のため

### 7.4 ユーザ運用ルール (重要)

- **応答は日本語**、Japanese diacritics 厳守 (`för` を `fur` にしない等)
- **terse confirmation 文化**: 「続けて」「進めて」「はい」「推奨通りに」「1」だけで進行可能
- **git commit / push / PR / merge は明示要求時のみ実行** (自動で実施しない)
- **AskUserQuestion を活用** して分岐点で確認する (terse 応答で進行可能なように設計)
- HIGH issue は同 sprint 内修正、MED/LOW は follow-up doc 化が確立済みパターン

---

## 8. memory 構造 (`~/.claude/projects/-Volumes-Seagate3TB-projects-edu/memory/`)

| ファイル | 役割 |
|---------|------|
| `MEMORY.md` | インデックス。最初に読む |
| `docker_runtime.md` | Colima 採用の事実 |
| `edu_sprint_workflow.md` | Sprint 0〜9 完了状態 + コマンド一覧 + subagent guard |
| `edu_stack_and_conventions.md` | 技術スタックと配置パターン |
| `edu_review_handling.md` | HIGH/MED/LOW の処理ルール |
| `edu_sprint5_followups.md` | Sprint 5 follow-up 残件 |
| `edu_sprint7_followups.md` | Sprint 7 follow-up + Sprint 8/9 までの統合状態 |
| `edu_sprint10_candidate.md` | **次 sprint 候補** |

---

## 9. 直近の git log (参考)

```
baf9bf4 docs(sprint-9): mark MED 1-5 + LOW 1/3/4 as done in follow-up tracker
76b524c refactor(sprint-9): LOW-4 — store.publish() returns PublishOut
c40cd73 docs(sprint-9): MED-5 + LOW-3 — system_prompt threat model + UUID cross-check
45bc37c fix(sprint-9): MED-4 — registry fallback per-slug, not cache-empty-only
3f9cc41 fix(sprint-9): MED-3 + LOW-1 — read rate-limit + course_slug regex
cb9276b fix(sprint-9): MED-1 + MED-2 schema validation hardening
4e48928 docs(sprint-9): follow-up doc (MED×5 + LOW×4) + README update for curriculum editing
854a252 fix(sprint-9): review HIGH × 3 — cache-after-commit + audit log + route param
```

---

## 10. 引き継ぎチェックリスト (新 AI 用)

- [ ] `MEMORY.md` を読む
- [ ] `docs/superpowers/specs/2026-06-13-sprint-9-curriculum-editing-design.md` で curriculum 編集設計を理解
- [ ] `docs/superpowers/specs/2026-06-14-sprint-9-followups.md` で残 LOW-2 を確認
- [ ] `edu_sprint10_candidate.md` を読んで次 sprint の方向性を把握
- [ ] ユーザが「次の Sprint を始める」と言ったら brainstorming skill を起動して候補 A (コホート集計) を提案
- [ ] terse confirmation で進行する文化を尊重する (大量の確認質問を投げない)
- [ ] commit / merge は明示要求時のみ
