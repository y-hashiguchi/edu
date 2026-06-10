# AIチューターカリキュラム Sprint 7 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI tutor を 1 コース固定から複数コース並走可能な基盤に切り替える。既存「AI駆動型開発 補足カリキュラム」(`ai-driven-dev`) と新規「AI時代SE育成カリキュラム」(`ai-era-se`) Phase 1 (8 課題) を同時運用できるようにし、登録時にコース選択、ダッシュボード・進捗・チャット・提出すべてをコース別に分離する。

**Architecture:** `courses` / `enrollments` テーブル新設、主要 5 テーブル (`progress` / `submissions` / `chat_history` / `embeddings` / `user_nudges`) に `course_id` FK 追加。カリキュラム定義は DB ではなく `backend/app/data/courses/` の Python レジストリ。API は `?course={slug}` クエリでスコープ。フロント URL は `/courses/:slug/phases/:phase` 構成、旧 `/phases/:phase` は `ai-driven-dev` への redirect。既存ユーザは Alembic マイグレーション 1 リビジョンで `ai-driven-dev` に auto-enroll + 既存行に `course_id` バックフィル。

**Tech Stack:**
- Backend: 既存（FastAPI / async SQLAlchemy / asyncpg / Alembic / Anthropic SDK / pgvector / fastembed / slowapi）。新規依存ゼロ。
- Frontend: 既存（Vue 3 / Pinia / TypeScript / Vue Router）のみ。
- 新規 SQL: 標準 PostgreSQL のみ（`gen_random_uuid()` を使用、`pgcrypto` extension は既存）。

---

## 設計書

実装中は以下の設計書を参照すること:

- 上位設計: `docs/superpowers/specs/2026-06-10-sprint-7-multi-course-architecture-design.md`（本計画書の根拠、コミット `5722606`）
- 起点ハンドオフメモ: `docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md`（参考のみ、Task 22 で削除予定）
- シラバス原文: `/Volumes/4TB_NAS/syllabus_weekly_12months.md`（Phase 1〜4 の週次テーブル）

---

## 主要意思決定（Sprint 7 計画時点）

| # | 判断項目 | 選択 | 理由 |
|---|---|---|---|
| 1 | 主軸 | マルチコース化 + ダッシュボードコーススコープ化 | spec ゴール |
| 2 | コース定義 | Python レジストリ (`backend/app/data/courses/`) | 既存 `curriculum.py` パターンの自然な拡張、DB スキーマ最小 |
| 3 | API スコープ | `?course={slug}` クエリ | 既存 API 破壊最小化、path 変更を回避 |
| 4 | 未指定時 | `DEFAULT_COURSE_SLUG = "ai-driven-dev"` | 既存ユーザの後方互換 |
| 5 | 既存ユーザの enroll | 全ユーザ (admin 含む) を migration で auto-enroll | `course_id` NOT NULL 保証 |
| 6 | `course_id` NULL 化 | 5 テーブルすべて NOT NULL | 漏洩・誤 join 防止 |
| 7 | `submissions.task_no` CHECK | 廃止 (ai-era-se は 8 課題) | コース別に上限が異なる |
| 8 | `embeddings.course_id` | NOT NULL、global 内容も ai-driven-dev でバックフィル | `seed_embeddings` 改修は follow-up へ切り出し |
| 9 | `user_nudges` PK | 単一 `user_id` → 複合 `(user_id, course_id)` | コースごとに別 nudge を許容 |
| 10 | `ai-era-se` 投入範囲 | Phase 1 (8 課題) のみパイロット | spec 同意 |
| 11 | AI 活用ルール 5 条 | 全 `ai-era-se` フェーズ `system_prompt` にリテラル注入 | grader の動作変更を最小化 |
| 12 | grader prompt | コース別に切替、`ai-driven-dev` は既存 prompt 温存 | 既存 grading 結果のレグレ回避 |
| 13 | `instructor_comments` | `course_id` 列なし、`submission_id` 経由で一意決定 | Sprint 6 設計を尊重 |
| 14 | `notifications` | `course_id` 列なし、コース横断 | mention は個人宛、コース範囲外 |
| 15 | フロント URL | `/courses/:slug/phases/:phase`、旧 `/phases/:phase` は redirect | spec ゴール、ブックマーク互換 |
| 16 | active course 永続化 | localStorage (`ai-tutor.activeCourse`) | リロード時の UX |
| 17 | admin の他コース閲覧 | enrollment 不要、`is_admin=True` で full access | サポート業務に必要 |
| 18 | テスト戦略 | TDD 厳格 + 既存 conftest 改修 + 新規 ≈40 件 | Sprint 4/5/6 と同水準 |
| 19 | subagent 防御 | 各 Task に CRITICAL ANTI-HALLUCINATION GUARDS を明記 | Sprint 6 Task 4 の前科 |
| 20 | ハンドオフメモの扱い | 最終 Task で削除、spec を単一ソースに | 二重管理回避 |

---

## スコープ境界

**含む（Sprint 7）：**

- DB:
  - `courses` テーブル新規（id, slug, title, description, sort_order, created_at）
  - `enrollments` テーブル新規（user_id, course_id, status, enrolled_at、UNIQUE）
  - 5 テーブルへの `course_id` 列追加: `progress` / `submissions` / `chat_history` / `embeddings` / `user_nudges`
  - `submissions` の UNIQUE と CHECK 制約再構築（`task_no BETWEEN 1 AND 5` 削除）
  - `progress` / `user_nudges` の UNIQUE 制約再構築
  - `chat_history` / `embeddings` の index 再構築
- バックエンド:
  - `backend/app/data/courses/` パッケージ（`types.py` / `__init__.py` / `ai_driven_dev.py` / `ai_era_se.py`）
  - `backend/app/data/curriculum.py` を shim 化（`ai-driven-dev` を re-export）
  - `app/services/enrollment.py`（新規）
  - `app/core/course_deps.py`（新規、`CourseContext`）
  - `app/api/courses.py`（新規、catalog + my courses）
  - `app/api/auth.py` の register に `course_slug` 必須化
  - `app/services/progress.py`, `submission.py`, `weakness.py`, `recommendation.py`, `nudge.py`, `progress_summary.py`, `dashboard.py` を `course_id` 必須に
  - `app/memory/chat_store.py` を `course_id` 必須に
  - `app/api/me_dashboard.py`, `app/api/admin/user_dashboard.py` を course スコープに
  - `app/api/curriculum.py`, `progress.py`, `chat.py`, `submissions.py` に `?course=` 適用
  - `app/api/admin/users.py` のレスポンスに `enrollments` 追加
  - `app/schemas/course.py`（新規）、`auth.py`, `chat.py`, `admin.py` の調整
  - `app/main.py` に courses router 登録
- フロントエンド:
  - `types/course.ts`（新規）、`stores/course.ts`（新規）、`views/CourseListView.vue`（新規）
  - `lib/api.ts` に `withCourse` / `listCourseCatalog` / `listMyCourses` / 各 API に `courseSlug` 引数追加
  - `stores/auth.ts` に `courseSlug` 引数追加
  - `views/LoginView.vue` にコース選択 `<select>`
  - `views/HomeView.vue`, `views/PhaseChatView.vue`, `components/PhaseCard.vue` を courseSlug 対応
  - `views/AdminUserDetailView.vue` にコース切替セレクタ
  - `views/AdminUsersView.vue` の `top_weakness_tag` 列はバックエンド既定（sort_order 最小 active course）
  - `router/index.ts` ルート再構成 + 旧 `/phases/:phase` redirect
- テスト: backend 新規 ≈40 件、frontend 新規 ≈15 件、conftest 全面改修
- 設計書: 既存 `docs/design/03-db-design.md` 等への Sprint 7 セクション追記は **本 sprint では行わない**（ドキュメントは spec を参照させる）
- Cursor ハンドオフメモ (`docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md`) を最終タスクで削除
- README 更新（Sprint 7 完了マーク + マルチコース運用手順）

**含まない（後続スプリント）：**

- `ai-era-se` Phase 2〜4 投入 → パイロット成功後
- `POST /api/admin/users/{id}/enrollments` → admin 経由の追加 enroll API
- `scripts/seed_embeddings.py` の `source_ref` をコース付き形式 (`course:{slug}:phase:{n}:task:{m}`) に変更
- broadcast 通知のコーススコープ化
- 採点ジョブの非同期化、curriculum 編集機能 → Sprint 6 follow-up からのキャリーオーバー
- Playwright headless 環境整備 → Sprint 5 INFRA carry-over
- Sprint 6 follow-up 残（MED-2, MED-6, LOW-4 vitest CVE, LOW-5 INFRA）

---

## ファイル構造（差分のみ）

```
edu/
├── README.md                                                              # Modify: Sprint 7 完了マーク + マルチコース運用手順
├── docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md     # Delete (Task 22)
├── backend/
│   ├── app/
│   │   ├── data/
│   │   │   ├── courses/
│   │   │   │   ├── __init__.py                                             # Create: COURSE_REGISTRY
│   │   │   │   ├── types.py                                                # Create: TaskItem / PhaseData / CourseData
│   │   │   │   ├── ai_driven_dev.py                                        # Create: 既存 curriculum.py からの移設
│   │   │   │   └── ai_era_se.py                                            # Create: Phase 1 8 課題 + AI_USAGE_RULES
│   │   │   └── curriculum.py                                               # Modify: shim 化 (ai-driven-dev re-export)
│   │   ├── models/
│   │   │   ├── course.py                                                   # Create
│   │   │   ├── enrollment.py                                               # Create
│   │   │   ├── submission.py                                               # Modify: course_id 列 + 制約再構築
│   │   │   ├── progress.py                                                 # Modify: course_id 列 + UNIQUE 再構築
│   │   │   ├── chat_history.py                                             # Modify: course_id 列 + index 再構築
│   │   │   ├── embedding.py                                                # Modify: course_id 列 + index 再構築
│   │   │   └── user_nudge.py                                               # Modify: 複合 PK (user_id, course_id)
│   │   ├── schemas/
│   │   │   ├── course.py                                                   # Create
│   │   │   ├── auth.py                                                     # Modify: RegisterRequest.course_slug
│   │   │   ├── chat.py                                                     # Modify: phase 上限緩和
│   │   │   └── admin.py                                                    # Modify: enrollments + top_weakness_tag
│   │   ├── services/
│   │   │   ├── enrollment.py                                               # Create
│   │   │   ├── progress.py                                                 # Modify: initialize_progress_for_course
│   │   │   ├── submission.py                                               # Modify: course_id 必須
│   │   │   ├── weakness.py                                                 # Modify: course_id 必須
│   │   │   ├── recommendation.py                                           # Modify: course_id 必須
│   │   │   ├── nudge.py                                                    # Modify: course_id 必須
│   │   │   ├── progress_summary.py                                         # Modify: course_id 必須
│   │   │   └── dashboard.py                                                # Modify: course_id 必須
│   │   ├── memory/chat_store.py                                            # Modify: course_id 必須
│   │   ├── core/course_deps.py                                             # Create
│   │   ├── api/
│   │   │   ├── courses.py                                                  # Create
│   │   │   ├── auth.py                                                     # Modify: course_slug 必須 + enroll_user
│   │   │   ├── curriculum.py                                               # Modify: ?course=
│   │   │   ├── progress.py                                                 # Modify: ?course=
│   │   │   ├── chat.py                                                     # Modify: ?course=
│   │   │   ├── submissions.py                                              # Modify: ?course= + task_no 上限緩和
│   │   │   ├── me.py                                                       # Modify: ?course= 含む既存ルート
│   │   │   ├── me_dashboard.py                                             # Modify: ?course= 必須
│   │   │   └── admin/
│   │   │       ├── users.py                                                # Modify: enrollments + top_weakness_tag コース別
│   │   │       └── user_dashboard.py                                       # Modify: ?course= 必須
│   │   └── main.py                                                         # Modify: courses router 登録
│   ├── alembic/versions/
│   │   └── 20260610_<rev>_sprint7_multi_course.py                          # Create
│   └── tests/
│       ├── conftest.py                                                     # Modify: courses seed + default_course_id + enroll
│       ├── test_course_registry.py                                         # Create
│       ├── test_course_models.py                                           # Create
│       ├── test_enrollment_service.py                                      # Create
│       ├── test_course_deps.py                                             # Create
│       ├── test_courses_api.py                                             # Create
│       ├── test_auth_api_course.py                                         # Create
│       ├── test_dashboard_api_multi_course.py                              # Create
│       ├── test_admin_user_dashboard_multi_course.py                       # Create
│       ├── test_submission_se_8tasks.py                                    # Create
│       └── test_alembic_sprint7_upgrade.py                                 # Create
└── frontend/
    └── src/
        ├── types/course.ts                                                 # Create
        ├── stores/course.ts                                                # Create
        ├── stores/auth.ts                                                  # Modify: courseSlug
        ├── stores/dashboard.ts                                             # Modify: activeSlug
        ├── stores/curriculum.ts                                            # Modify: activeSlug
        ├── stores/chat.ts                                                  # Modify: activeSlug
        ├── stores/admin.ts                                                 # Modify: fetchUserDashboard(userId, courseSlug)
        ├── lib/api.ts                                                      # Modify: withCourse, listCourseCatalog, listMyCourses
        ├── views/
        │   ├── LoginView.vue                                               # Modify: course select
        │   ├── CourseListView.vue                                          # Create
        │   ├── HomeView.vue                                                # Modify: courseSlug prop
        │   ├── PhaseChatView.vue                                           # Modify: courseSlug prop
        │   └── AdminUserDetailView.vue                                     # Modify: コース切替セレクタ
        ├── components/
        │   └── PhaseCard.vue                                               # Modify: /courses/:slug/phases/:n リンク
        ├── router/index.ts                                                 # Modify: 新ルート + 旧 redirect
        └── __tests__/
            ├── course.store.spec.ts                                        # Create
            ├── CourseListView.spec.ts                                      # Create
            ├── LoginView.spec.ts                                           # Create
            ├── HomeView.spec.ts                                            # Modify
            └── AdminUserDetailView.spec.ts                                 # Modify
```

---

## 共通の前提

- **作業ブランチ:** `feature/sprint-7`（main から派生、現 HEAD = `5722606`）
- **環境:** Docker Compose の `postgres` を起動。backend は `uv run uvicorn` でホスト起動可。
- **テスト DB:** `ai_tutor_test`。Sprint 7 マイグレーションは `Base.metadata.create_all` 経由でテストに反映される（Alembic は本番 DB のみ）。
- **既存テスト件数（ベースライン）:** backend 298 / frontend 64
- **目標テスト件数:** backend **338** / frontend **79**
- **コミット規約:** Sprint 1〜6 と同じ `feat|fix|test|chore|docs|refactor(scope): ...`。本スプリントの scope は `sprint-7`。
- **コマンド実行ディレクトリ:** 特記なき限り `/Volumes/Seagate3TB/projects/edu`。

### 既存スキーマ事実（subagent 暴走防止用 — そのまま転記）

- **`Submission`** (`backend/app/models/submission.py`):
  - 列: `id`, `user_id`, `phase`, `task_no`, `content`, `ai_feedback`, `score`, `submitted_at`, `graded_at`
  - 制約: `UNIQUE (user_id, phase, task_no)`, `CHECK phase BETWEEN 1 AND 4`, `CHECK task_no BETWEEN 1 AND 5`, `CHECK score IS NULL OR score BETWEEN 0 AND 100`
- **`Progress`** (`backend/app/models/progress.py`):
  - 列: `id`, `user_id`, `phase`, `status`, `started_at`, `completed_at`
  - 制約: `UNIQUE (user_id, phase)`
- **`ChatHistory`** (`backend/app/models/chat_history.py`):
  - 列: `id`, `user_id`, `phase`, `role`, `content`, `created_at`
  - index: `ix_chat_history_user_phase_created (user_id, phase, created_at)`
- **`Embedding`** (`backend/app/models/embedding.py`):
  - 列: `id`, `user_id (nullable)`, `source_type`, `source_ref`, `phase (nullable)`, `content`, `embedding (Vector 384)`, `created_at`
  - index: `ix_embeddings_user_phase (user_id, phase)`, `ix_embeddings_vector_hnsw`
- **`UserNudge`** (`backend/app/models/user_nudge.py`):
  - PK: `user_id`（単一）
  - 列: `user_id`, `body`, `generated_at`, `input_signature`
- **`InstructorComment`** (`backend/app/models/instructor_comment.py`):
  - 列: `id`, `submission_id`, `author_user_id`, `body`, `created_at`, `updated_at`, `parent_id` (Sprint 6)
  - **Sprint 7 では変更しない**（submission 経由で course_id 一意決定）
- **`Notification`**: **Sprint 7 では変更しない**（コース横断）
- **`User`**: 列 `id`, `email`, `name`, `password_hash`, `is_admin`, `created_at`
- **`CURRICULUM`** (`backend/app/data/curriculum.py`): `MappingProxyType` で 4 フェーズの `TypedDict` を持つ。`get_phase(n)`, `get_task_title(p, t)`, `get_task_skill_tags(p, t)`, `iter_all_phase_task_pairs()` をエクスポート
- **Auth flow**: `register` → `User` 作成 → `initialize_progress(db, user.id)` で 4 フェーズの `Progress` 作成 → commit。Sprint 7 で `course_slug` 必須化 + `enroll_user` 呼び出しを追加
- **既存 router 登録順** (`app/main.py:72-84`): health → auth → curriculum → progress → submissions → chat → admin_users → admin_submissions → admin_comments → admin_notifications → admin_user_dashboard → me → me_dashboard
- **最新 Alembic リビジョン**: `57242832bf0f` (`20260610_..._sprint6_followup_comment_self_loop_check.py`)

### 既存テスト fixture（`conftest.py`）

- `client`: `TestClient(app)`
- `_setup_db` (session-scoped, autouse): `Base.metadata.create_all` を一回実行
- `db_session`: 各テスト前に全テーブル TRUNCATE、`AsyncSession` を yield
- `auth_user`: 受講者 1 名作成、`initialize_progress` 呼び出し、コミット
- `auth_token`, `auth_client`
- `admin_user` (is_admin=True), `admin_token`, `admin_client`
- 上記すべてに **Sprint 7 で `course_id` バックフィルが必要**

### Cursor プロトタイプから引き継いだ既知の落とし穴（必読）

ハンドオフメモ `docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md` で得られた経験則。Task 6 / Task 16 / それ以降の実装で参照すること:

**よくある失敗パターン:**

| 症状 | 対処 |
|---|---|
| `null value in column "course_id"` | テスト内の `Submission` / `ChatHistory` / `Progress` / `UserNudge` / `Embedding` 直接生成箇所に `course_id=default_course_id` を必ず追加 |
| `CourseNotFoundError` | conftest の courses seed が commit される前に API 呼び出し。`db_session` fixture 内 truncate 直後に courses を再 seed する順序を厳守 |
| `IntegrityError` on enrollments (user_id, course_id) | conftest の `auth_user` / `admin_user` が enroll 後に再 enroll されるパス。`enroll_user` 呼び出しを 1 回だけにする |
| pytest が 15 分以上ハング | **pytest を同時に複数起動しない**（`TRUNCATE` / `DROP TABLE` がデッドロック）。`pytest -q` の単一プロセスのみ |
| 無効 phase で 422 ではなく 404 | コース定義にない phase は `PhaseNotFoundError` → HTTP 404。Pydantic で弾かない（コースごとに上限が異なる） |
| activeSlug が null のまま fetch で 401/403 | フロント `router.beforeEach` で `course.hydrateActiveFromStorage()` → `fetchMyCourses()` 待機 → 判定の順を厳守 |

**特定の修正済み test:**

- `tests/test_comment_thread_service.py` (Sprint 6 で追加) の `sub_b` 直接生成箇所に `course_id=default_course_id` を付与必要 — Task 16 で明示的に修正対象
- その他 `tests/test_*` 配下で `Submission(`, `Progress(`, `ChatHistory(`, `UserNudge(`, `Embedding(` を直接生成しているテストは grep で洗い出して同じ修正を適用

**検証コマンドの厳守事項:**

```bash
# 並行実行を避ける。並行で起動するとデッドロックする。
docker compose up -d postgres
cd backend && uv run pytest -q
```

**ハンドオフメモ自体の扱い:**

- 起点: Cursor IDE で別セッションが実施した未コミットの設計実装メモ
- 本 Sprint 中は参考のみ、現 main HEAD = `94837f3` を **唯一の真実**
- Task 22 で `docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md` を `git rm` 削除

---

### CRITICAL ANTI-HALLUCINATION GUARDS（subagent 全 Task 共通）

Sprint 6 Task 4 で subagent が `courses` テーブル / `Submission.course_id` 等を仕様外で書き換える事故が発生。各 Task の subagent プロンプトに以下を **必ず** 明記すること:

1. **既存スキーマは上記「既存スキーマ事実」セクションを唯一の真実とせよ**。コード中で見えない属性は **存在しないと仮定**。
2. **修正ファイル allowlist は本 Task の「Files:」セクションに列挙したもののみ**。それ以外は read のみ可、write は禁止。
3. **各 Step 開始前に `git status` を実行**。allowlist 外の差分が出ていたら即停止して報告。
4. **Cursor IDE ハンドオフメモは参考のみ、現 main HEAD = `5722606` を基準**。メモと現実が食い違ったら現実を優先。
5. **新規テーブル / 列を書く前に Task 1〜6 でその基盤が作られたかを確認**。基盤がない状態で `course_id` を参照するコードを書かない。

---

## Task 0: ブランチ作成と環境確認

**Files:**
- なし（git のみ）

- [ ] **Step 1: feature ブランチを切る**

```bash
git checkout main
git pull --ff-only || true
git checkout -b feature/sprint-7
```

- [ ] **Step 2: バックエンド全件テストが現状で通ることを確認**

```bash
docker compose up -d postgres
sleep 5
cd backend && uv run pytest -q
```

Expected: `298 passed`。

- [ ] **Step 3: フロントテストとビルドが現状で通ることを確認**

```bash
cd ../frontend && npm run build && npm test -- --run
```

Expected: ビルド成功、`64 passed`。

- [ ] **Step 4: 開発 DB のマイグレーション状況を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && set -a && . ../.env && set +a && \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  uv run alembic current
```

Expected: 最新リビジョン `57242832bf0f`（Sprint 6 follow-up MED-1 で追加された `sprint6_followup_comment_self_loop_check`）。

- [ ] **Step 5: ハンドオフメモが untracked のまま存在することを確認**

```bash
git status --short docs/superpowers/plans/
```

Expected: `?? docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md`。Task 22 で削除する。

---

## Task 1: `Course` / `Enrollment` モデル作成 + フィールドテスト

**Files:**
- Create: `backend/app/models/course.py`
- Create: `backend/app/models/enrollment.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/tests/test_course_models.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_course_models.py` を新規作成:

```python
"""Sprint 7 model tests — Course / Enrollment."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User


@pytest.mark.asyncio
async def test_course_persists_with_unique_slug(db_session):
    c = Course(
        slug="ai-driven-dev",
        title="AI駆動型開発 補足カリキュラム",
        description=None,
        sort_order=0,
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    assert c.id is not None

    dup = Course(slug="ai-driven-dev", title="dup", sort_order=1)
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_enrollment_links_user_to_course(db_session):
    user = User(email="u@e.com", name="U", password_hash=hash_password("p"))
    course = Course(slug="ai-era-se", title="SE", sort_order=1)
    db_session.add_all([user, course])
    await db_session.flush()

    enr = Enrollment(user_id=user.id, course_id=course.id)
    db_session.add(enr)
    await db_session.commit()
    await db_session.refresh(enr)
    assert enr.status == "active"
    assert enr.enrolled_at is not None


@pytest.mark.asyncio
async def test_enrollment_unique_user_course_pair(db_session):
    user = User(email="u@e.com", name="U", password_hash=hash_password("p"))
    course = Course(slug="c1", title="C1", sort_order=0)
    db_session.add_all([user, course])
    await db_session.flush()
    db_session.add(Enrollment(user_id=user.id, course_id=course.id))
    await db_session.commit()

    db_session.add(Enrollment(user_id=user.id, course_id=course.id))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_user_delete_cascades_enrollment(db_session):
    user = User(email="u@e.com", name="U", password_hash=hash_password("p"))
    course = Course(slug="c1", title="C1", sort_order=0)
    db_session.add_all([user, course])
    await db_session.flush()
    db_session.add(Enrollment(user_id=user.id, course_id=course.id))
    await db_session.commit()

    await db_session.delete(user)
    await db_session.commit()
    remaining = (
        await db_session.execute(select(Enrollment))
    ).scalars().all()
    assert remaining == []
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_course_models.py -q
```

Expected: 失敗（`Course` / `Enrollment` モジュール未存在）。

- [ ] **Step 3: `Course` モデルを作成**

`backend/app/models/course.py` を新規作成:

```python
"""Course definition (Sprint 7).

Curriculum content lives in `app/data/courses/`. This table only stores
identity + display metadata so foreign keys (progress / submissions /
chat_history / embeddings / user_nudges / enrollments) can reference a
real row. The two known courses are seeded by the Sprint 7 migration
with fixed UUIDs."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
```

- [ ] **Step 4: `Enrollment` モデルを作成**

`backend/app/models/enrollment.py` を新規作成:

```python
"""User x Course enrollment (Sprint 7).

A user MUST have an enrollment for every course they interact with —
progress / submissions / chat_history all carry course_id and we enforce
that the learner is actively enrolled in `course_deps.get_course_context`.
Admins bypass the enrollment check (sales / support use case).

ON DELETE on user_id is CASCADE so a hard-deleted user doesn't leave
orphan enrollments. ON DELETE on course_id is RESTRICT — we never
hard-delete a course (data retention)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", name="uq_enrollments_user_course"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # 'active' | 'paused' | 'completed'
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
```

- [ ] **Step 5: `models/__init__.py` で両モデルを登録**

`backend/app/models/__init__.py` を読んで、既存の import 行と並べて以下を追加:

```python
from app.models.course import Course  # noqa: F401
from app.models.enrollment import Enrollment  # noqa: F401
```

import 順は alphabetical 推奨。既存と同じ pattern で並べる。

- [ ] **Step 6: テスト緑を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_course_models.py -q
```

Expected: `4 passed`。

- [ ] **Step 7: 全テスト緑**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q
```

Expected: `302 passed`（298 + 新規 4）。

- [ ] **Step 8: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/models/course.py backend/app/models/enrollment.py backend/app/models/__init__.py backend/tests/test_course_models.py
git commit -m "feat(sprint-7): add Course and Enrollment ORM models"
```

---

## Task 2: カリキュラムレジストリ基盤 (`backend/app/data/courses/`)

**Files:**
- Create: `backend/app/data/courses/__init__.py`
- Create: `backend/app/data/courses/types.py`
- Create: `backend/app/data/courses/ai_driven_dev.py`
- Modify: `backend/app/data/curriculum.py`
- Create: `backend/tests/test_course_registry.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_course_registry.py` を新規作成:

```python
"""Sprint 7 — course registry contract tests."""

import uuid

import pytest

from app.data.courses import (
    COURSE_REGISTRY,
    DEFAULT_COURSE_SLUG,
    get_course,
    get_phase,
    get_phases,
)
from app.data.courses.types import CourseData, PhaseData, TaskItem


def test_default_course_is_ai_driven_dev():
    assert DEFAULT_COURSE_SLUG == "ai-driven-dev"
    assert DEFAULT_COURSE_SLUG in COURSE_REGISTRY


def test_ai_driven_dev_course_shape():
    c = get_course("ai-driven-dev")
    assert isinstance(c, CourseData)
    assert c.slug == "ai-driven-dev"
    assert c.id == uuid.UUID("00000000-0000-4000-8000-000000000001")
    assert len(c.phases) == 4
    for p in c.phases:
        assert isinstance(p, PhaseData)
        assert len(p.tasks) >= 1
        for t in p.tasks:
            assert isinstance(t, TaskItem)


def test_get_phases_returns_tuple():
    phases = get_phases("ai-driven-dev")
    assert isinstance(phases, tuple)
    assert len(phases) == 4


def test_get_phase_picks_one_by_number():
    p = get_phase("ai-driven-dev", 1)
    assert p.phase == 1
    assert "開発環境" in p.title


def test_get_course_raises_on_unknown_slug():
    from app.data.courses import CourseNotFoundError

    with pytest.raises(CourseNotFoundError):
        get_course("does-not-exist")


def test_get_phase_raises_on_unknown_phase():
    from app.data.courses import PhaseNotFoundError

    with pytest.raises(PhaseNotFoundError):
        get_phase("ai-driven-dev", 99)


def test_course_data_is_frozen():
    c = get_course("ai-driven-dev")
    with pytest.raises(Exception):
        c.title = "mutated"  # type: ignore[misc]
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_course_registry.py -q
```

Expected: 失敗（`app.data.courses` モジュール未存在）。

- [ ] **Step 3: `types.py` を作成**

`backend/app/data/courses/types.py` を新規作成:

```python
"""Sprint 7 — frozen value objects for the course registry.

These are deliberately frozen to make accidental mutation a TypeError.
Mirror of `Course` ORM model identity (id, slug, title) so the same
fixed UUIDs flow into FK references when the migration seeds the table."""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskItem:
    task_no: int
    title: str
    description: str
    skill_tags: tuple[str, ...] = ()
    deliverable: str | None = None
    week_label: str | None = None


@dataclass(frozen=True)
class PhaseData:
    phase: int
    title: str
    goal: str
    tasks: tuple[TaskItem, ...]
    system_prompt: str


@dataclass(frozen=True)
class CourseData:
    id: uuid.UUID
    slug: str
    title: str
    description: str
    sort_order: int
    phases: tuple[PhaseData, ...]
```

- [ ] **Step 4: `ai_driven_dev.py` を作成（既存 `curriculum.py` から移設）**

`backend/app/data/courses/ai_driven_dev.py` を新規作成:

```python
"""ai-driven-dev course definition (Sprint 7 — moved from curriculum.py).

The content is the literal Sprint 0 curriculum used in Sprint 4-6.
Migrating it to the frozen-dataclass shape is purely structural — no
text changes. The 4-phase shape is preserved; downstream consumers
must access via the registry, not by importing CURRICULUM."""

import uuid

from app.data.courses.types import CourseData, PhaseData, TaskItem


AI_DRIVEN_DEV_COURSE = CourseData(
    id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
    slug="ai-driven-dev",
    title="AI駆動型開発 補足カリキュラム",
    description="既存 Java/Python 経験者向けの AI 駆動型開発習得カリキュラム",
    sort_order=0,
    phases=(
        PhaseData(
            phase=1,
            title="開発環境の近代化",
            goal="AIツールを使いこなすための「土台」を固める",
            tasks=(
                TaskItem(
                    task_no=1,
                    title="Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成",
                    description="Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成",
                    skill_tags=("Git/GitHub",),
                ),
                TaskItem(
                    task_no=2,
                    title="VSCode拡張（GitLens・REST Client・GitHub Copilot）の導入と動作確認",
                    description="VSCode拡張（GitLens・REST Client・GitHub Copilot）の導入と動作確認",
                    skill_tags=("開発環境",),
                ),
                TaskItem(
                    task_no=3,
                    title="curlでREST APIを叩き、JSONレスポンス構造をまとめる",
                    description="curlでREST APIを叩き、JSONレスポンス構造をまとめる",
                    skill_tags=("API基礎",),
                ),
            ),
            system_prompt=(
                "あなたはAI駆動型開発を教える教育AIチューターです。\n"
                "対象はJava/Python基礎・HTML/CSS/JS・DB基礎修了済みの研修生です。\n"
                "現在のフェーズ：Phase1「開発環境の近代化」。\n"
                "Git・VSCode・REST APIの基礎を教えます。\n"
                "指導方針：\n"
                "- 既存の知識（Java/Python）と紐付けて説明する\n"
                "- 手を動かさせることを重視する\n"
                "- 答えをすぐ教えず、まず考えさせる\n"
                "- 3〜5文程度で日本語で返答する"
            ),
        ),
        PhaseData(
            phase=2,
            title="AIツール活用マスター",
            goal="「AIと一緒にコードを書く」体験を積む",
            tasks=(
                TaskItem(
                    task_no=1,
                    title="Cursor IDEで顧客管理API（CRUD）をゼロから作成。AIとのやり取りログを記録",
                    description="Cursor IDEで顧客管理API（CRUD）をゼロから作成。AIとのやり取りログを記録",
                    skill_tags=("AI協調", "API基礎"),
                ),
                TaskItem(
                    task_no=2,
                    title="同機能をGitHub Copilotでも実装し、2つのAIの違いをまとめる",
                    description="同機能をGitHub Copilotでも実装し、2つのAIの違いをまとめる",
                    skill_tags=("AI協調", "開発環境"),
                ),
                TaskItem(
                    task_no=3,
                    title="ClaudeにコードレビューさせてPDCA",
                    description="ClaudeにコードレビューさせてPDCA",
                    skill_tags=("AI協調", "コードレビュー"),
                ),
            ),
            system_prompt=(
                "あなたはAI駆動型開発を教える教育AIチューターです。\n"
                "対象はJava/Python基礎・HTML/CSS/JS・DB基礎修了済みの研修生です。\n"
                "現在のフェーズ：Phase2「AIツール活用マスター」。\n"
                "Cursor IDE・GitHub Copilot・Claudeの実践的な使い方を指導します。\n"
                "指導方針：\n"
                "- プロンプトの良し悪しを具体例で教える\n"
                "- AIを鵜呑みにしない批判的思考を育てる\n"
                "- 実際に手を動かさせる課題を出す\n"
                "- 3〜5文程度で日本語で返答する"
            ),
        ),
        PhaseData(
            phase=3,
            title="AI協調型開発ワークフロー",
            goal="実際の開発タスクにAIを組み込む",
            tasks=(
                TaskItem(
                    task_no=1,
                    title="Phase2で作ったAPIをAIにレビューさせ、セキュリティ・パフォーマンス・可読性の観点で整理",
                    description="Phase2で作ったAPIをAIにレビューさせ、セキュリティ・パフォーマンス・可読性の観点で整理",
                    skill_tags=("コードレビュー", "AI協調"),
                ),
                TaskItem(
                    task_no=2,
                    title="仕様書（箇条書き）からテストコードを自動生成し、不足ケースを3つ指摘",
                    description="仕様書（箇条書き）からテストコードを自動生成し、不足ケースを3つ指摘",
                    skill_tags=("テスト", "AI協調"),
                ),
                TaskItem(
                    task_no=3,
                    title="AIとペアで新機能（検索機能など）を実装。会話ログも提出",
                    description="AIとペアで新機能（検索機能など）を実装。会話ログも提出",
                    skill_tags=("AI協調", "設計"),
                ),
            ),
            system_prompt=(
                "あなたはAI駆動型開発を教える教育AIチューターです。\n"
                "対象はJava/Python基礎・HTML/CSS/JS・DB基礎修了済みの研修生です。\n"
                "現在のフェーズ：Phase3「AI協調型開発ワークフロー」。\n"
                "AIペアプログラミング・コードレビュー・テスト自動生成を教えます。\n"
                "指導方針：\n"
                "- AIの出力を検証する習慣をつけさせる\n"
                "- 開発品質の観点（セキュリティ・テスト・可読性）を意識させる\n"
                "- ソクラテス式で深く考えさせる\n"
                "- 3〜5文程度で日本語で返答する"
            ),
        ),
        PhaseData(
            phase=4,
            title="AIアプリ開発実践",
            goal="「AIを使う」から「AIを組み込む」へ",
            tasks=(
                TaskItem(
                    task_no=1,
                    title="Claude APIでチャットボット作成（会話履歴保持・システムプロンプト設定）",
                    description="Claude APIでチャットボット作成（会話履歴保持・システムプロンプト設定）",
                    skill_tags=("LLM活用",),
                ),
                TaskItem(
                    task_no=2,
                    title="RAGデモ作成（Python + ChromaDB + Claude API）",
                    description="RAGデモ作成（Python + ChromaDB + Claude API）",
                    skill_tags=("RAG/ベクトル検索", "LLM活用"),
                ),
                TaskItem(
                    task_no=3,
                    title="業務課題を解決するAIツールの企画書作成（課題・解決策・技術構成・効果試算）",
                    description="業務課題を解決するAIツールの企画書作成（課題・解決策・技術構成・効果試算）",
                    skill_tags=("業務応用", "設計"),
                ),
            ),
            system_prompt=(
                "あなたはAI駆動型開発を教える教育AIチューターです。\n"
                "対象はJava/Python基礎・HTML/CSS/JS・DB基礎修了済みの研修生です。\n"
                "現在のフェーズ：Phase4「AIアプリ開発実践」。\n"
                "Claude/OpenAI API連携・RAG・PythonでのAIツール開発を教えます。\n"
                "指導方針：\n"
                "- 実装の具体的な手順をステップで示す\n"
                "- RAGの概念をわかりやすく説明する\n"
                "- 企画力・提案力も育てる\n"
                "- 3〜5文程度で日本語で返答する"
            ),
        ),
    ),
)
```

- [ ] **Step 5: `__init__.py` を作成（レジストリ + エラー型 + アクセサ）**

`backend/app/data/courses/__init__.py` を新規作成:

```python
"""Sprint 7 — course registry.

Public API:
  COURSE_REGISTRY: dict[slug, CourseData]
  DEFAULT_COURSE_SLUG: 'ai-driven-dev'
  get_course(slug) -> CourseData
  get_phases(slug) -> tuple[PhaseData, ...]
  get_phase(slug, phase_no) -> PhaseData
  CourseNotFoundError / PhaseNotFoundError
"""

from app.data.courses.ai_driven_dev import AI_DRIVEN_DEV_COURSE
from app.data.courses.ai_era_se import AI_ERA_SE_COURSE
from app.data.courses.types import CourseData, PhaseData, TaskItem


class CourseNotFoundError(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"course slug {slug!r} not found")
        self.slug = slug


class PhaseNotFoundError(Exception):
    def __init__(self, slug: str, phase: int) -> None:
        super().__init__(f"phase {phase} not found in course {slug!r}")
        self.slug = slug
        self.phase = phase


DEFAULT_COURSE_SLUG: str = "ai-driven-dev"

COURSE_REGISTRY: dict[str, CourseData] = {
    AI_DRIVEN_DEV_COURSE.slug: AI_DRIVEN_DEV_COURSE,
    AI_ERA_SE_COURSE.slug: AI_ERA_SE_COURSE,
}


def get_course(slug: str) -> CourseData:
    try:
        return COURSE_REGISTRY[slug]
    except KeyError:
        raise CourseNotFoundError(slug) from None


def get_phases(slug: str) -> tuple[PhaseData, ...]:
    return get_course(slug).phases


def get_phase(slug: str, phase_no: int) -> PhaseData:
    for p in get_course(slug).phases:
        if p.phase == phase_no:
            return p
    raise PhaseNotFoundError(slug, phase_no)


__all__ = [
    "COURSE_REGISTRY",
    "CourseData",
    "CourseNotFoundError",
    "DEFAULT_COURSE_SLUG",
    "PhaseData",
    "PhaseNotFoundError",
    "TaskItem",
    "get_course",
    "get_phase",
    "get_phases",
]
```

- [ ] **Step 6: `curriculum.py` を shim 化**

`backend/app/data/curriculum.py` の全内容を以下に置き換える:

```python
"""Backward-compatible shim (Sprint 7).

Sprint 0 had a single CURRICULUM TypedDict mapping. Sprint 7 replaced
it with the courses registry. Existing consumers that import CURRICULUM
/ get_phase / get_task_title / get_task_skill_tags / iter_all_phase_task_pairs
keep working — all four functions delegate to the ai-driven-dev course
via the registry.

NEW CODE: import from `app.data.courses` directly, pass a course slug.
"""

from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import TypedDict

from app.data.courses import (
    DEFAULT_COURSE_SLUG,
    get_course,
)


class TaskItem(TypedDict):
    title: str
    skill_tags: list[str]


class PhaseData(TypedDict):
    title: str
    goal: str
    duration: str
    skills: list[str]
    tasks: list[TaskItem]
    system_prompt: str


def _build_legacy_curriculum() -> Mapping[int, PhaseData]:
    course = get_course(DEFAULT_COURSE_SLUG)
    out: dict[int, PhaseData] = {}
    for p in course.phases:
        out[p.phase] = PhaseData(
            title=p.title,
            goal=p.goal,
            duration="",
            skills=[],
            tasks=[
                TaskItem(title=t.title, skill_tags=list(t.skill_tags))
                for t in p.tasks
            ],
            system_prompt=p.system_prompt,
        )
    return MappingProxyType(out)


CURRICULUM: Mapping[int, PhaseData] = _build_legacy_curriculum()


def get_phase(phase_no: int) -> PhaseData:
    try:
        return CURRICULUM[phase_no]
    except KeyError:
        valid = sorted(CURRICULUM.keys())
        raise KeyError(
            f"Phase {phase_no} not found. Valid phases: {valid}"
        ) from None


def get_task_title(phase_no: int, task_no: int) -> str:
    tasks = get_phase(phase_no)["tasks"]
    if task_no < 1 or task_no > len(tasks):
        raise KeyError(
            f"task_no {task_no} out of range for phase {phase_no} "
            f"(1..{len(tasks)})"
        )
    return tasks[task_no - 1]["title"]


def get_task_skill_tags(phase_no: int, task_no: int) -> list[str]:
    tasks = get_phase(phase_no)["tasks"]
    if task_no < 1 or task_no > len(tasks):
        raise KeyError(
            f"task_no {task_no} out of range for phase {phase_no} "
            f"(1..{len(tasks)})"
        )
    return list(tasks[task_no - 1]["skill_tags"])


def iter_all_phase_task_pairs() -> Iterator[tuple[int, int]]:
    for phase_no in sorted(CURRICULUM.keys()):
        for i in range(len(CURRICULUM[phase_no]["tasks"])):
            yield phase_no, i + 1
```

- [ ] **Step 7: 既存テストへの影響を確認（ここで一回赤を引いたら緑に戻す）**

ai_era_se はまだ存在しないので `__init__.py` の import が失敗する。次の Task 3 で実装する前提で、本 Task の最後でテストを通すには `__init__.py` の `from app.data.courses.ai_era_se import AI_ERA_SE_COURSE` 行を **一時的にコメントアウト** すること:

`backend/app/data/courses/__init__.py` の冒頭:

```python
from app.data.courses.ai_driven_dev import AI_DRIVEN_DEV_COURSE
# from app.data.courses.ai_era_se import AI_ERA_SE_COURSE  # Task 3 で有効化
```

そして:

```python
COURSE_REGISTRY: dict[str, CourseData] = {
    AI_DRIVEN_DEV_COURSE.slug: AI_DRIVEN_DEV_COURSE,
    # AI_ERA_SE_COURSE.slug: AI_ERA_SE_COURSE,  # Task 3 で有効化
}
```

`test_course_registry.py` の `test_default_course_is_ai_driven_dev` と `test_ai_driven_dev_course_shape` は通る。`test_course_data_is_frozen` も通る。それ以外（`test_get_phases_returns_tuple` 等）も `ai-driven-dev` のみで通る。

- [ ] **Step 8: テスト緑を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_course_registry.py -q
```

Expected: `7 passed`。

- [ ] **Step 9: 全テスト緑（既存 curriculum.py を使うコードは shim 経由で動く）**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q
```

Expected: `309 passed`（302 + 新規 7）。既存の curriculum テスト群も shim 経由で全て緑になる。

- [ ] **Step 10: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/data/courses/__init__.py backend/app/data/courses/types.py backend/app/data/courses/ai_driven_dev.py backend/app/data/curriculum.py backend/tests/test_course_registry.py
git commit -m "feat(sprint-7): course registry foundation (types + ai-driven-dev + shim)"
```

---

## Task 3: `ai-era-se` Phase 1（8 課題）+ AI 活用ルール 5 条

**Files:**
- Create: `backend/app/data/courses/ai_era_se.py`
- Modify: `backend/app/data/courses/__init__.py`（Task 2 でコメントアウトした 2 行を解除）
- Modify: `backend/tests/test_course_registry.py`（ai-era-se 用テストを追加）

- [ ] **Step 1: failing test を追加**

`backend/tests/test_course_registry.py` の末尾に以下を追加:

```python
def test_ai_era_se_course_present():
    c = get_course("ai-era-se")
    assert c.slug == "ai-era-se"
    assert c.id == uuid.UUID("00000000-0000-4000-8000-000000000002")
    assert c.sort_order == 1
    # Pilot: Phase 1 only, 8 tasks
    assert len(c.phases) == 1
    p = c.phases[0]
    assert p.phase == 1
    assert len(p.tasks) == 8


def test_ai_era_se_phase1_system_prompt_contains_ai_usage_rules():
    p = get_phase("ai-era-se", 1)
    # 5 rules, literal text from syllabus
    assert "コピペ禁止" in p.system_prompt
    assert "動けばOKは禁止" in p.system_prompt
    assert "プロンプトはバージョン管理" in p.system_prompt
    assert "AIが見逃した問題" in p.system_prompt
    assert "毎週の作業ログ" in p.system_prompt


def test_ai_era_se_phase1_task_titles_match_syllabus():
    p = get_phase("ai-era-se", 1)
    titles = [t.title for t in p.tasks]
    assert "Git・ターミナル・VS Code 基礎" in titles[0]
    assert "PHPフレームワーク比較" in titles[1]
    assert "HTTP・API・DB" in titles[2]
    assert "業務DB読解" in titles[3]
    assert "Docker・ローカル環境構築" in titles[4]
    assert "AWSインフラ概念" in titles[5]
    assert "SQL実践" in titles[6]
    assert "フェーズ1振り返り" in titles[7]
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_course_registry.py -q
```

Expected: 失敗（`get_course("ai-era-se")` で `CourseNotFoundError`）。

- [ ] **Step 3: `ai_era_se.py` を作成**

`backend/app/data/courses/ai_era_se.py` を新規作成:

```python
"""ai-era-se course definition (Sprint 7).

Pilot scope: Phase 1 only (8 weekly tasks). AI usage rules from the
syllabus are injected literally into the system prompt of every phase
so the tutor consistently reinforces the same 5 rules. Phase 2-4 are
deferred (see follow-up doc)."""

import uuid

from app.data.courses.types import CourseData, PhaseData, TaskItem


AI_USAGE_RULES = (
    "【AI 活用ルール】\n"
    "1. AIに聞いた内容は必ず自分の言葉で再説明できること（コピペ禁止）\n"
    "2. AIが生成したコードは理解してから使うこと（動けばOKは禁止）\n"
    "3. プロンプトはバージョン管理すること（Gitで管理、改善履歴を残す）\n"
    "4. AIが見逃した問題を自分で探す習慣を付けること\n"
    "5. 「AIに任せた場面」と「自分で判断した場面」を毎週の作業ログに記録すること"
)


_SE_TUTOR_BASE = (
    "あなたは AI 時代の SE 育成を担う AI チューターです。\n"
    "対象は初級エンジニア（プログラミング経験 1 年未満）で、業務プロジェクト"
    "（MFRS / Nichinichi Anshin / IES）を題材に学びます。\n"
    f"\n{AI_USAGE_RULES}\n"
)


_PHASE_1_EVAL = (
    "\n【Phase 1 評価基準】\n"
    "- Gitの基本操作（clone・branch・commit・push）が一人でできる\n"
    "- HTTP・APIの仕組みを口頭で説明できる\n"
    "- SQLで基本的なSELECT・JOINが書ける\n"
    "- Dockerで開発環境を起動できる"
)


_PHASE_1_TASKS: tuple[TaskItem, ...] = (
    TaskItem(
        task_no=1,
        week_label="第1週",
        title="Git・ターミナル・VS Code 基礎",
        description=(
            "3プロジェクトのリポジトリをcloneしてブランチを切る。"
            "コミット・プッシュを体験する"
        ),
        deliverable="Git操作が一人でできる",
        skill_tags=("Git/GitHub", "開発環境"),
    ),
    TaskItem(
        task_no=2,
        week_label="第2週",
        title="PHPフレームワーク比較",
        description=(
            "Phalcon・Laravel・Yiiが1プロジェクト内に共存する理由を調査し、"
            "設計思想の違いを比較表にまとめる"
        ),
        deliverable="比較レポート1枚 / AIで調査→自分の言葉で要約",
        skill_tags=("AI協調", "業務応用"),
    ),
    TaskItem(
        task_no=3,
        week_label="第3週",
        title="HTTP・API・DBの仕組み",
        description=(
            "センサーデータ（温度・湿度・人感）がDBに届くまでの経路を"
            "図に起こす。curlでAPIレスポンスを確認する"
        ),
        deliverable="データフロー図 / 用語不明点をAIに質問",
        skill_tags=("API基礎",),
    ),
    TaskItem(
        task_no=4,
        week_label="第4週",
        title="業務DB読解",
        description=(
            "IES 96テーブルから受注関連主要テーブルを特定し、"
            "「予定注文→確定注文→案件→完了計上」のER図を手書きで作成する"
        ),
        deliverable="ER図（手書きOK） / テーブル定義の読み方をAIで確認",
        skill_tags=("DB基礎",),
    ),
    TaskItem(
        task_no=5,
        week_label="第5週",
        title="Docker・ローカル環境構築",
        description=(
            "3プロジェクトそれぞれのDocker Compose環境を立ち上げ、"
            "動作確認する。エラーが出たら自力で解決する"
        ),
        deliverable="3環境が起動できる / エラーログをAIに貼って解決練習",
        skill_tags=("開発環境",),
    ),
    TaskItem(
        task_no=6,
        week_label="第6週",
        title="AWSインフラ概念",
        description=(
            "MFRSのAWS構成（ALB→EC2→RDS）を図に起こす。"
            "ALB・ターゲットグループ・セキュリティグループの役割を説明できるようにする"
        ),
        deliverable="AWS構成図 / 各サービスの役割をAIで補足確認",
        skill_tags=("インフラ",),
    ),
    TaskItem(
        task_no=7,
        week_label="第7週",
        title="SQL実践 (SELECT・JOIN)",
        description=(
            "IESのテスト環境（ekap_test）で受注データを実際にSELECTし、"
            "受注件数・委託先別集計などのクエリを書く"
        ),
        deliverable="SQLクエリ5本以上 / クエリの書き方をAIと一緒に考える",
        skill_tags=("DB基礎",),
    ),
    TaskItem(
        task_no=8,
        week_label="第8週",
        title="フェーズ1振り返り発表",
        description=(
            "学んだことを1枚のスライドにまとめて社内ミニ発表。"
            "「AIを使った場面・使わなかった場面」を必ず含める"
        ),
        deliverable="発表スライド1枚 / メンター1on1",
        skill_tags=("発信",),
    ),
)


AI_ERA_SE_COURSE = CourseData(
    id=uuid.UUID("00000000-0000-4000-8000-000000000002"),
    slug="ai-era-se",
    title="AI時代SE育成カリキュラム",
    description=(
        "12 ヶ月のSE育成カリキュラム。Phase 1（8 課題）は土台づくり。"
        "MFRS / Nichinichi Anshin / IES を題材にする。"
    ),
    sort_order=1,
    phases=(
        PhaseData(
            phase=1,
            title="土台づくり",
            goal="開発環境・業務の仕組み・AIとの最初の対話を体感する",
            tasks=_PHASE_1_TASKS,
            system_prompt=(
                _SE_TUTOR_BASE
                + "\n現在のフェーズ：Phase 1「土台づくり」（第1〜8週）。\n"
                "指導方針：\n"
                "- 用語が新しい受講者を前提に、専門語を必ず噛み砕く\n"
                "- 「答えを返す」より「次の問いを立てさせる」\n"
                "- 3〜5文程度で日本語で返答する"
                + _PHASE_1_EVAL
            ),
        ),
    ),
)
```

- [ ] **Step 4: `__init__.py` のコメントアウト 2 行を解除**

`backend/app/data/courses/__init__.py` を編集:

- 冒頭の `# from app.data.courses.ai_era_se import AI_ERA_SE_COURSE` の `#` を外す
- `COURSE_REGISTRY` 辞書の `# AI_ERA_SE_COURSE.slug: AI_ERA_SE_COURSE,` の `#` を外す

- [ ] **Step 5: テスト緑を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_course_registry.py -q
```

Expected: `10 passed`（既存 7 + 新規 3）。

- [ ] **Step 6: 全テスト緑**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q
```

Expected: `312 passed`（309 + 新規 3）。

- [ ] **Step 7: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/data/courses/ai_era_se.py backend/app/data/courses/__init__.py backend/tests/test_course_registry.py
git commit -m "feat(sprint-7): ai-era-se Phase 1 (8 tasks + AI usage rules)"
```

---

## Task 4: 既存モデルへ `course_id` を追加（5 テーブル）

**Files:**
- Modify: `backend/app/models/submission.py`
- Modify: `backend/app/models/progress.py`
- Modify: `backend/app/models/chat_history.py`
- Modify: `backend/app/models/embedding.py`
- Modify: `backend/app/models/user_nudge.py`

> **ANTI-HALLUCINATION:** 既存スキーマ事実セクションに書かれた列名・index 名・制約名のみを変更対象とする。例えば `Submission.course_id` を追加する際に `instructor_comments` を書き換えない。

- [ ] **Step 1: `submission.py` に `course_id` 列追加 + 制約再構築**

`backend/app/models/submission.py` の全内容を以下に置き換える:

```python
"""Submission ORM model."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Submission(Base):
    __tablename__ = "submissions"
    # Sprint 7: course_id added, UNIQUE expanded, task_no CHECK removed
    # (ai-era-se has 8 tasks; per-course bounds enforced in service layer).
    __table_args__ = (
        UniqueConstraint(
            "user_id", "course_id", "phase", "task_no",
            name="uq_submissions_user_course_phase_task",
        ),
        CheckConstraint("phase BETWEEN 1 AND 4", name="ck_submissions_phase"),
        CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 100", name="ck_submissions_score"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    phase: Mapped[int] = mapped_column(Integer)
    task_no: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    graded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

`phase BETWEEN 1 AND 4` は temporary: ai-era-se が Phase 1 のみなので現状値域内。Phase 2+ 投入時に follow-up で緩和する。

- [ ] **Step 2: `progress.py` に `course_id` 列追加 + UNIQUE 再構築**

`backend/app/models/progress.py` の全内容を以下に置き換える:

```python
"""Progress ORM model + status enum."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProgressStatus(StrEnum):
    LOCKED = "locked"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    COMPLETED = "completed"


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "course_id", "phase",
            name="uq_progress_user_course_phase",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    phase: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default=ProgressStatus.LOCKED.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 3: `chat_history.py` に `course_id` 列追加 + index 再構築**

`backend/app/models/chat_history.py` の全内容を以下に置き換える:

```python
"""ChatHistory ORM model."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatHistory(Base):
    __tablename__ = "chat_history"
    __table_args__ = (
        Index(
            "ix_chat_history_user_course_phase_created",
            "user_id", "course_id", "phase", "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    phase: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
```

- [ ] **Step 4: `embedding.py` に `course_id` 列追加 + index 再構築**

`backend/app/models/embedding.py` の全内容を以下に置き換える:

```python
"""Embedding ORM model (pgvector-backed)."""

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 output dim
EMBEDDING_DIM = 384


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        Index(
            "ix_embeddings_course_user_phase",
            "course_id", "user_id", "phase",
        ),
        Index(
            "ix_embeddings_vector_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # NULL means "global / curriculum" content shared across users
    # within a course. course_id stays NOT NULL — global-to-the-
    # platform content (none today) would need a separate solution.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(50))
    source_ref: Mapped[str] = mapped_column(String(200))
    phase: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

- [ ] **Step 5: `user_nudge.py` を複合 PK に変更**

`backend/app/models/user_nudge.py` の全内容を以下に置き換える:

```python
"""Sprint 5 nudge cache, Sprint 7 scoped per course.

PK is composite (user_id, course_id) so a learner enrolled in multiple
courses gets one nudge per course instead of one global nudge
contaminated with cross-course state. input_signature still drives
sub-24h invalidation."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserNudge(Base):
    __tablename__ = "user_nudges"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), primary_key=True
    )
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    input_signature: Mapped[str] = mapped_column(String(16), nullable=False)
```

- [ ] **Step 6: テストを走らせて赤を確認（想定内）**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q 2>&1 | tail -20
```

Expected: 大量失敗（`null value in column "course_id"`）。Task 6 で Alembic 作成、Task 16 で conftest 改修まで暫定的にレッド。

- [ ] **Step 7: Commit（赤を抱えたまま中間 commit — Sprint 6 と同じパターン）**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/models/submission.py backend/app/models/progress.py backend/app/models/chat_history.py backend/app/models/embedding.py backend/app/models/user_nudge.py
git commit -m "feat(sprint-7): add course_id FK to 5 existing tables (red commit)"
```

---

## Task 5: schemas 拡張（auth + course + chat + admin）

**Files:**
- Create: `backend/app/schemas/course.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/schemas/chat.py`
- Modify: `backend/app/schemas/admin.py`

- [ ] **Step 1: `schemas/course.py` を新規作成**

`backend/app/schemas/course.py` を新規作成:

```python
"""Sprint 7 course schemas (catalog + enrollment projections)."""

from datetime import datetime

from pydantic import BaseModel, Field


class CourseCatalogItem(BaseModel):
    slug: str
    title: str
    description: str | None
    sort_order: int


class CourseCatalogOut(BaseModel):
    items: list[CourseCatalogItem]


class EnrollmentOut(BaseModel):
    """Returned in admin user detail and as part of /api/courses."""

    course_slug: str
    course_title: str
    status: str = Field(pattern=r"^(active|paused|completed)$")
    enrolled_at: datetime


class MyCourseItem(BaseModel):
    """A course the authenticated learner is enrolled in."""

    slug: str
    title: str
    description: str | None
    status: str = Field(pattern=r"^(active|paused|completed)$")


class MyCoursesOut(BaseModel):
    items: list[MyCourseItem]
```

- [ ] **Step 2: `schemas/auth.py` に `course_slug` 必須化**

`backend/app/schemas/auth.py` の `RegisterRequest` を以下に置き換える:

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    # Sprint 7: course selection is mandatory at registration. The
    # actual slug-existence check happens in the auth route — a
    # Pydantic-level enum would create a circular import.
    course_slug: str = Field(min_length=1, max_length=64)
```

- [ ] **Step 3: `schemas/chat.py` の `phase` 上限を緩和**

該当行を grep:

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
grep -n "le=4" app/schemas/chat.py
```

該当行があれば `le=4` のみ削除（`ge=1` は維持）。上限はサービス層で `PhaseNotFoundError` 経由で弾く。

- [ ] **Step 4: `schemas/admin.py` を確認 + `enrollments` を `AdminUserDetail` に追加**

該当箇所を確認:

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
grep -n "top_weakness_tag\|class Admin" app/schemas/admin.py
```

`AdminUserSummary.top_weakness_tag: str | None = None` の docstring に Sprint 7 仕様を追記:

```python
class AdminUserSummary(BaseModel):
    """One row in the admin users index.

    Sprint 7: top_weakness_tag is computed from submissions in the
    user's primary active enrollment (the course with the lowest
    sort_order among status='active' rows). Older code wrote this
    field assuming a single course.
    """
    id: uuid.UUID
    email: EmailStr
    name: str
    created_at: datetime
    is_admin: bool
    completed_phases: int
    in_progress_phases: int
    top_weakness_tag: str | None = None
```

`AdminUserDetail` の `enrollments` フィールド追加（既存ファイル冒頭の import 群に `from app.schemas.course import EnrollmentOut` を追加）:

```python
class AdminUserDetail(AdminUserSummary):
    """Detailed view used by /api/admin/users/{id}.

    Sprint 7: includes enrollments so the admin UI can render a course
    selector for the dashboard section.
    """
    enrollments: list[EnrollmentOut] = []
```

`AdminUserDetail` がまだ無い場合は `AdminUserSummary` を継承する形で新規追加。`/api/admin/users/{id}` ルートの `response_model` を `AdminUserDetail` に切替えるのは Task 14 で実施。

- [ ] **Step 5: schemas 単体の import エラーが無いことを確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run python -c "from app.schemas import course, auth, chat, admin; print('ok')"
```

Expected: `ok`。

- [ ] **Step 6: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/schemas/course.py backend/app/schemas/auth.py backend/app/schemas/chat.py backend/app/schemas/admin.py
git commit -m "feat(sprint-7): course schemas + course_slug in register + admin enrollments"
```

---

## Task 6: Alembic マイグレーション（テーブル新設 + course_id 追加 + auto-enroll）

**Files:**
- Create: `backend/alembic/versions/20260610_<rev>_sprint7_multi_course.py`
- Create: `backend/tests/test_alembic_sprint7_upgrade.py`

> **ANTI-HALLUCINATION:** マイグレーションでは既存スキーマ事実セクションに列挙した 5 テーブルのみ変更する。`instructor_comments` や `notifications` は触らない。

- [ ] **Step 1: マイグレーション skeleton を生成**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && set -a && . ../.env && set +a && \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  uv run alembic revision -m "sprint7_multi_course"
```

生成ファイル名: `backend/alembic/versions/20260610_<rev>_sprint7_multi_course.py`。`<rev>` は自動填め。

- [ ] **Step 2: マイグレーション本体を手書き**

生成ファイルの `upgrade()` と `downgrade()` を以下に置き換える（`revision` と `down_revision` の自動填め値は保持、`down_revision = '57242832bf0f'` を確認）:

```python
"""sprint7_multi_course

Revision ID: <auto>
Revises: 57242832bf0f
Create Date: <auto>

Sprint 7: introduce courses + enrollments, propagate course_id to
5 dependent tables, auto-enroll all existing users into ai-driven-dev,
and rebuild affected UNIQUE constraints. Down deletes ai-era-se rows
before restoring the single-course schema."""

import uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '<auto>'
down_revision = '57242832bf0f'
branch_labels = None
depends_on = None


AI_DRIVEN_DEV_UUID = uuid.UUID("00000000-0000-4000-8000-000000000001")
AI_ERA_SE_UUID = uuid.UUID("00000000-0000-4000-8000-000000000002")


def upgrade() -> None:
    # 1. courses table
    op.create_table(
        "courses",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 2. seed two courses with fixed UUIDs
    op.execute(
        sa.text(
            "INSERT INTO courses (id, slug, title, description, sort_order) "
            "VALUES (:id1, 'ai-driven-dev', "
            "'AI駆動型開発 補足カリキュラム', "
            "'既存 Java/Python 経験者向けの AI 駆動型開発習得カリキュラム', 0), "
            "(:id2, 'ai-era-se', "
            "'AI時代SE育成カリキュラム', "
            "'12 ヶ月のSE育成カリキュラム。Phase 1 をパイロット投入。', 1)"
        ).bindparams(id1=AI_DRIVEN_DEV_UUID, id2=AI_ERA_SE_UUID)
    )

    # 3. enrollments table
    op.create_table(
        "enrollments",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "user_id", "course_id", name="uq_enrollments_user_course"
        ),
    )
    op.create_index("ix_enrollments_user_id", "enrollments", ["user_id"])
    op.create_index("ix_enrollments_course_id", "enrollments", ["course_id"])

    # 4. add course_id to 5 tables as NULLABLE first
    for table in ("progress", "submissions", "chat_history", "embeddings", "user_nudges"):
        op.add_column(
            table,
            sa.Column(
                "course_id",
                sa.UUID(),
                sa.ForeignKey("courses.id", ondelete="RESTRICT"),
                nullable=True,
            ),
        )

    # 5. backfill existing rows to ai-driven-dev
    for table in ("progress", "submissions", "chat_history", "embeddings", "user_nudges"):
        op.execute(
            sa.text(f"UPDATE {table} SET course_id = :cid WHERE course_id IS NULL")
            .bindparams(cid=AI_DRIVEN_DEV_UUID)
        )

    # 6. auto-enroll all existing users into ai-driven-dev
    op.execute(
        sa.text(
            "INSERT INTO enrollments (id, user_id, course_id, status) "
            "SELECT gen_random_uuid(), id, :cid, 'active' FROM users "
            "ON CONFLICT (user_id, course_id) DO NOTHING"
        ).bindparams(cid=AI_DRIVEN_DEV_UUID)
    )

    # 7. NOT NULL + indexes
    for table in ("progress", "submissions", "chat_history", "embeddings", "user_nudges"):
        op.alter_column(table, "course_id", nullable=False)
        op.create_index(f"ix_{table}_course_id", table, ["course_id"])

    # 8. submissions: drop task_no CHECK, rebuild UNIQUE
    op.drop_constraint("ck_submissions_task_no", "submissions", type_="check")
    op.drop_constraint(
        "uq_submissions_user_phase_task", "submissions", type_="unique"
    )
    op.create_unique_constraint(
        "uq_submissions_user_course_phase_task",
        "submissions",
        ["user_id", "course_id", "phase", "task_no"],
    )

    # 9. progress UNIQUE rebuild
    op.drop_constraint("uq_progress_user_phase", "progress", type_="unique")
    op.create_unique_constraint(
        "uq_progress_user_course_phase",
        "progress",
        ["user_id", "course_id", "phase"],
    )

    # 10. user_nudges PK rebuild (single -> composite)
    op.execute("ALTER TABLE user_nudges DROP CONSTRAINT user_nudges_pkey")
    op.create_primary_key(
        "user_nudges_pkey", "user_nudges", ["user_id", "course_id"]
    )

    # 11. chat_history index rebuild
    op.drop_index("ix_chat_history_user_phase_created", table_name="chat_history")
    op.create_index(
        "ix_chat_history_user_course_phase_created",
        "chat_history",
        ["user_id", "course_id", "phase", "created_at"],
    )

    # 12. embeddings index rebuild (HNSW stays as-is)
    op.drop_index("ix_embeddings_user_phase", table_name="embeddings")
    op.create_index(
        "ix_embeddings_course_user_phase",
        "embeddings",
        ["course_id", "user_id", "phase"],
    )


def downgrade() -> None:
    # Drop ai-era-se rows so the single-course CHECK restoration succeeds.
    # ai-era-se has up to 8 tasks; restoring task_no <= 5 would fail
    # on any task_no > 5 row.
    for table in ("progress", "submissions", "chat_history", "embeddings", "user_nudges"):
        op.execute(
            sa.text(f"DELETE FROM {table} WHERE course_id = :cid")
            .bindparams(cid=AI_ERA_SE_UUID)
        )

    op.drop_index("ix_embeddings_course_user_phase", table_name="embeddings")
    op.create_index("ix_embeddings_user_phase", "embeddings", ["user_id", "phase"])

    op.drop_index("ix_chat_history_user_course_phase_created", table_name="chat_history")
    op.create_index(
        "ix_chat_history_user_phase_created",
        "chat_history",
        ["user_id", "phase", "created_at"],
    )

    op.execute("ALTER TABLE user_nudges DROP CONSTRAINT user_nudges_pkey")
    op.create_primary_key("user_nudges_pkey", "user_nudges", ["user_id"])

    op.drop_constraint("uq_progress_user_course_phase", "progress", type_="unique")
    op.create_unique_constraint(
        "uq_progress_user_phase", "progress", ["user_id", "phase"]
    )

    op.drop_constraint(
        "uq_submissions_user_course_phase_task", "submissions", type_="unique"
    )
    op.create_unique_constraint(
        "uq_submissions_user_phase_task",
        "submissions",
        ["user_id", "phase", "task_no"],
    )
    op.create_check_constraint(
        "ck_submissions_task_no", "submissions", "task_no BETWEEN 1 AND 5"
    )

    for table in ("user_nudges", "embeddings", "chat_history", "submissions", "progress"):
        op.drop_index(f"ix_{table}_course_id", table_name=table)
        op.drop_column(table, "course_id")

    op.drop_index("ix_enrollments_course_id", table_name="enrollments")
    op.drop_index("ix_enrollments_user_id", table_name="enrollments")
    op.drop_table("enrollments")

    op.drop_table("courses")
```

- [ ] **Step 3: 構造テストを追加**

`backend/tests/test_alembic_sprint7_upgrade.py` を新規作成:

```python
"""Sprint 7 — Alembic structural invariants.

We don't run alembic in pytest. This loads the migration module and
asserts fixed UUIDs, down_revision linkage, and presence of upgrade/
downgrade. The actual upgrade is exercised manually against the dev
DB and validated by data probes."""

import importlib.util
import pathlib
import uuid


def _load_migration():
    versions_dir = pathlib.Path(__file__).parent.parent / "alembic" / "versions"
    candidates = list(versions_dir.glob("*sprint7_multi_course*.py"))
    assert len(candidates) == 1, f"expected 1 sprint7 migration, got {candidates}"
    spec = importlib.util.spec_from_file_location(
        "sprint7_migration", candidates[0]
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sprint7_migration_uses_fixed_uuids():
    m = _load_migration()
    assert m.AI_DRIVEN_DEV_UUID == uuid.UUID("00000000-0000-4000-8000-000000000001")
    assert m.AI_ERA_SE_UUID == uuid.UUID("00000000-0000-4000-8000-000000000002")


def test_sprint7_migration_chains_from_sprint6():
    m = _load_migration()
    assert m.down_revision == "57242832bf0f"


def test_sprint7_migration_has_upgrade_and_downgrade():
    m = _load_migration()
    assert callable(m.upgrade)
    assert callable(m.downgrade)
```

- [ ] **Step 4: 構造テスト緑を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_alembic_sprint7_upgrade.py -q
```

Expected: `3 passed`。

- [ ] **Step 5: マイグレーションを開発 DB に適用**

**重要:** pytest を別ターミナルで同時に走らせない（`TRUNCATE` / `DROP TABLE` がデッドロックする — ハンドオフメモで確認済みの落とし穴）。

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && set -a && . ../.env && set +a && \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  uv run alembic upgrade head
```

Expected: `Running upgrade 57242832bf0f -> <rev>, sprint7_multi_course`。

- [ ] **Step 6: 開発 DB でテーブル存在確認**

```bash
docker compose exec postgres psql -U postgres -d ai_tutor -c "\dt courses enrollments"
docker compose exec postgres psql -U postgres -d ai_tutor -c "SELECT slug, sort_order FROM courses ORDER BY sort_order"
docker compose exec postgres psql -U postgres -d ai_tutor -c "SELECT course_id, COUNT(*) FROM progress GROUP BY course_id"
```

Expected: `courses` と `enrollments` が表示、2 コース seeding 済み、progress 全行が ai-driven-dev に紐付く。

- [ ] **Step 7: downgrade も検証**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && set -a && . ../.env && set +a && \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  uv run alembic downgrade -1 && \
  uv run alembic upgrade head
```

Expected: 両方成功。downgrade 後に `\dt courses` で消えること、re-upgrade で戻ること。

- [ ] **Step 8: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/alembic/versions/*sprint7_multi_course.py backend/tests/test_alembic_sprint7_upgrade.py
git commit -m "feat(sprint-7): Alembic migration (courses + enrollments + auto-enroll backfill)"
```

---

## Task 7: `enrollment` サービス + `course_deps` dependency

**Files:**
- Create: `backend/app/services/enrollment.py`
- Create: `backend/app/core/course_deps.py`
- Create: `backend/tests/test_enrollment_service.py`
- Create: `backend/tests/test_course_deps.py`

- [ ] **Step 1: failing test for enrollment service**

`backend/tests/test_enrollment_service.py` を新規作成:

```python
"""Sprint 7 — enrollment service unit tests."""

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User
from app.services.enrollment import (
    AlreadyEnrolledError,
    CourseNotFoundError,
    EnrollmentNotFoundError,
    enroll_user,
    list_my_courses,
    require_active_enrollment,
)


async def _make_user(db, email="u@e.com", is_admin=False):
    user = User(
        email=email, name="U", password_hash=hash_password("p"),
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    await db.commit()
    await db.refresh(user)
    return user


async def _seed_courses(db):
    a = Course(slug="ai-driven-dev", title="AI Dev", sort_order=0)
    b = Course(slug="ai-era-se", title="SE", sort_order=1)
    db.add_all([a, b])
    await db.commit()
    await db.refresh(a)
    await db.refresh(b)
    return a, b


@pytest.mark.asyncio
async def test_enroll_user_creates_active_row(db_session):
    a, _ = await _seed_courses(db_session)
    user = await _make_user(db_session)

    enr = await enroll_user(db_session, user_id=user.id, course_slug=a.slug)
    await db_session.commit()
    assert enr.status == "active"
    assert enr.course_id == a.id


@pytest.mark.asyncio
async def test_enroll_user_raises_on_unknown_slug(db_session):
    user = await _make_user(db_session)
    with pytest.raises(CourseNotFoundError):
        await enroll_user(db_session, user_id=user.id, course_slug="nope")


@pytest.mark.asyncio
async def test_enroll_user_raises_on_duplicate(db_session):
    a, _ = await _seed_courses(db_session)
    user = await _make_user(db_session)

    await enroll_user(db_session, user_id=user.id, course_slug=a.slug)
    await db_session.commit()
    with pytest.raises(AlreadyEnrolledError):
        await enroll_user(db_session, user_id=user.id, course_slug=a.slug)


@pytest.mark.asyncio
async def test_require_active_enrollment_ok(db_session):
    a, _ = await _seed_courses(db_session)
    user = await _make_user(db_session)
    await enroll_user(db_session, user_id=user.id, course_slug=a.slug)
    await db_session.commit()

    found = await require_active_enrollment(
        db_session, user_id=user.id, course_id=a.id
    )
    assert found.status == "active"


@pytest.mark.asyncio
async def test_require_active_enrollment_raises_when_missing(db_session):
    a, _ = await _seed_courses(db_session)
    user = await _make_user(db_session)
    with pytest.raises(EnrollmentNotFoundError):
        await require_active_enrollment(
            db_session, user_id=user.id, course_id=a.id
        )


@pytest.mark.asyncio
async def test_require_active_enrollment_ignores_paused(db_session):
    a, _ = await _seed_courses(db_session)
    user = await _make_user(db_session)
    enr = await enroll_user(db_session, user_id=user.id, course_slug=a.slug)
    enr.status = "paused"
    await db_session.commit()
    with pytest.raises(EnrollmentNotFoundError):
        await require_active_enrollment(
            db_session, user_id=user.id, course_id=a.id
        )


@pytest.mark.asyncio
async def test_list_my_courses_returns_active_sorted(db_session):
    a, b = await _seed_courses(db_session)
    user = await _make_user(db_session)
    await enroll_user(db_session, user_id=user.id, course_slug=b.slug)
    await enroll_user(db_session, user_id=user.id, course_slug=a.slug)
    await db_session.commit()

    items = await list_my_courses(db_session, user_id=user.id)
    # sort_order ascending: ai-driven-dev (0) before ai-era-se (1)
    assert [it.slug for it in items] == ["ai-driven-dev", "ai-era-se"]
```

- [ ] **Step 2: Run — expected to fail (no enrollment service yet)**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_enrollment_service.py -q
```

Expected: ImportError on `app.services.enrollment`。

- [ ] **Step 3: `services/enrollment.py` を作成**

`backend/app/services/enrollment.py` を新規作成:

```python
"""Sprint 7 — enrollment domain service.

Routes interact with enrollments only through these functions so the
course_slug -> course_id mapping is centralised. Admins bypass
require_active_enrollment in `app/core/course_deps.py` (this module
stays unaware of admin-ness)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.courses import COURSE_REGISTRY
from app.models.course import Course
from app.models.enrollment import Enrollment


class CourseNotFoundError(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"course {slug!r} not found")
        self.slug = slug


class EnrollmentNotFoundError(Exception):
    def __init__(self, user_id: uuid.UUID, course_id: uuid.UUID) -> None:
        super().__init__(
            f"active enrollment for user={user_id} course={course_id} not found"
        )
        self.user_id = user_id
        self.course_id = course_id


class AlreadyEnrolledError(Exception):
    def __init__(self, user_id: uuid.UUID, course_slug: str) -> None:
        super().__init__(
            f"user={user_id} already enrolled in {course_slug!r}"
        )


@dataclass(frozen=True)
class MyCourseProjection:
    slug: str
    title: str
    description: str | None
    status: str


async def _get_course_by_slug(db: AsyncSession, slug: str) -> Course:
    if slug not in COURSE_REGISTRY:
        raise CourseNotFoundError(slug)
    result = await db.execute(select(Course).where(Course.slug == slug))
    course = result.scalar_one_or_none()
    if course is None:
        # registry has it but DB row missing — migration issue
        raise CourseNotFoundError(slug)
    return course


async def enroll_user(
    db: AsyncSession, *, user_id: uuid.UUID, course_slug: str
) -> Enrollment:
    course = await _get_course_by_slug(db, course_slug)
    existing = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == user_id,
            Enrollment.course_id == course.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise AlreadyEnrolledError(user_id, course_slug)

    enr = Enrollment(user_id=user_id, course_id=course.id, status="active")
    db.add(enr)
    await db.flush()
    return enr


async def require_active_enrollment(
    db: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> Enrollment:
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == user_id,
            Enrollment.course_id == course_id,
            Enrollment.status == "active",
        )
    )
    enr = result.scalar_one_or_none()
    if enr is None:
        raise EnrollmentNotFoundError(user_id, course_id)
    return enr


async def list_my_courses(
    db: AsyncSession, *, user_id: uuid.UUID
) -> list[MyCourseProjection]:
    result = await db.execute(
        select(Enrollment, Course)
        .join(Course, Enrollment.course_id == Course.id)
        .where(Enrollment.user_id == user_id)
        .order_by(Course.sort_order, Course.title)
    )
    out: list[MyCourseProjection] = []
    for enr, course in result.all():
        out.append(
            MyCourseProjection(
                slug=course.slug,
                title=course.title,
                description=course.description,
                status=enr.status,
            )
        )
    return out
```

- [ ] **Step 4: Run enrollment tests — should pass**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_enrollment_service.py -q
```

Expected: `7 passed`。 conftest 改修前なので courses テーブルへの seed は各テスト内で手動実行（test 自身が `_seed_courses` を呼ぶ）。

- [ ] **Step 5: failing test for course_deps**

`backend/tests/test_course_deps.py` を新規作成:

```python
"""Sprint 7 — course_deps dependency unit tests.

Tests exercise the dependency directly (no FastAPI request) so they
don't depend on conftest's not-yet-updated fixtures."""

import pytest
from fastapi import HTTPException

from app.core.course_deps import get_course_context
from app.core.security import hash_password
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User


async def _seed_user_and_course(db, *, is_admin=False, enrolled=True):
    user = User(
        email="u@e.com", name="U", password_hash=hash_password("p"),
        is_admin=is_admin,
    )
    course = Course(slug="ai-driven-dev", title="A", sort_order=0)
    db.add_all([user, course])
    await db.flush()
    if enrolled:
        db.add(Enrollment(user_id=user.id, course_id=course.id))
    await db.commit()
    await db.refresh(user)
    await db.refresh(course)
    return user, course


@pytest.mark.asyncio
async def test_default_slug_resolves_when_unspecified(db_session):
    user, _ = await _seed_user_and_course(db_session)
    ctx = await get_course_context(course=None, user=user, db=db_session)
    assert ctx.course.slug == "ai-driven-dev"


@pytest.mark.asyncio
async def test_explicit_slug_resolves(db_session):
    user, _ = await _seed_user_and_course(db_session)
    ctx = await get_course_context(course="ai-driven-dev", user=user, db=db_session)
    assert ctx.course.slug == "ai-driven-dev"


@pytest.mark.asyncio
async def test_unknown_slug_returns_404(db_session):
    user, _ = await _seed_user_and_course(db_session)
    with pytest.raises(HTTPException) as ei:
        await get_course_context(course="nope", user=user, db=db_session)
    assert ei.value.status_code == 404


@pytest.mark.asyncio
async def test_non_admin_without_enrollment_gets_403(db_session):
    user, _ = await _seed_user_and_course(db_session, enrolled=False)
    with pytest.raises(HTTPException) as ei:
        await get_course_context(course="ai-driven-dev", user=user, db=db_session)
    assert ei.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_without_enrollment_passes(db_session):
    user, _ = await _seed_user_and_course(db_session, is_admin=True, enrolled=False)
    ctx = await get_course_context(course="ai-driven-dev", user=user, db=db_session)
    assert ctx.course.slug == "ai-driven-dev"
    assert ctx.enrollment is None
```

- [ ] **Step 6: Run — expected to fail (no course_deps yet)**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_course_deps.py -q
```

Expected: ImportError on `app.core.course_deps`。

- [ ] **Step 7: `core/course_deps.py` を作成**

`backend/app/core/course_deps.py` を新規作成:

```python
"""Sprint 7 — FastAPI dependency that resolves ?course= to a CourseContext.

Behavior:
- ?course= missing -> DEFAULT_COURSE_SLUG ('ai-driven-dev')
- Unknown slug -> 404
- Non-admin without active enrollment -> 403
- Admin without enrollment -> allowed (enrollment=None) for support views

Note: this dependency is intentionally separate from the
`enrollment` service so route code can introspect both course
(CourseData) and enrollment (DB row) without re-fetching."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.data.courses import (
    DEFAULT_COURSE_SLUG,
    CourseData,
    CourseNotFoundError as RegistryCourseNotFoundError,
    get_course as get_course_from_registry,
)
from app.db.session import get_db
from app.models.enrollment import Enrollment
from app.models.user import User
from app.services.enrollment import (
    EnrollmentNotFoundError,
    _get_course_by_slug,
    require_active_enrollment,
)


@dataclass(frozen=True)
class CourseContext:
    course: CourseData
    enrollment: Enrollment | None


async def get_course_context(
    course: str | None = Query(None, alias="course"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CourseContext:
    slug = course or DEFAULT_COURSE_SLUG
    try:
        course_data = get_course_from_registry(slug)
    except RegistryCourseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"course {e.slug!r} not found",
        ) from e

    db_course = await _get_course_by_slug(db, slug)

    if user.is_admin:
        return CourseContext(course=course_data, enrollment=None)

    try:
        enr = await require_active_enrollment(
            db, user_id=user.id, course_id=db_course.id
        )
    except EnrollmentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not enrolled in this course",
        ) from e

    return CourseContext(course=course_data, enrollment=enr)
```

- [ ] **Step 8: Run course_deps tests — should pass**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_course_deps.py tests/test_enrollment_service.py -q
```

Expected: `12 passed`。

- [ ] **Step 9: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/services/enrollment.py backend/app/core/course_deps.py backend/tests/test_enrollment_service.py backend/tests/test_course_deps.py
git commit -m "feat(sprint-7): enrollment service + course_deps FastAPI dependency"
```

---

## Task 8: `/api/courses` ルータ（catalog + my courses）

**Files:**
- Create: `backend/app/api/courses.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_courses_api.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_courses_api.py` を新規作成:

```python
"""Sprint 7 — /api/courses (catalog + my courses) integration tests."""

import pytest

from app.core.security import hash_password
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User


async def _seed_courses(db):
    a = Course(slug="ai-driven-dev", title="AI Dev", description="d1", sort_order=0)
    b = Course(slug="ai-era-se", title="SE", description="d2", sort_order=1)
    db.add_all([a, b])
    await db.commit()
    return a, b


@pytest.mark.asyncio
async def test_catalog_is_public(client, db_session):
    await _seed_courses(db_session)
    res = client.get("/api/courses/catalog")
    assert res.status_code == 200
    body = res.json()
    slugs = [i["slug"] for i in body["items"]]
    assert "ai-driven-dev" in slugs
    assert "ai-era-se" in slugs


@pytest.mark.asyncio
async def test_catalog_sorted_by_sort_order(client, db_session):
    await _seed_courses(db_session)
    res = client.get("/api/courses/catalog")
    items = res.json()["items"]
    assert items[0]["slug"] == "ai-driven-dev"
    assert items[1]["slug"] == "ai-era-se"


@pytest.mark.asyncio
async def test_my_courses_requires_auth(client):
    res = client.get("/api/courses")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_my_courses_returns_enrolled_only(
    client, auth_user, auth_token, db_session
):
    a, b = await _seed_courses(db_session)
    db_session.add(
        Enrollment(user_id=auth_user.id, course_id=a.id, status="active")
    )
    await db_session.commit()

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/courses")
    assert res.status_code == 200
    slugs = [i["slug"] for i in res.json()["items"]]
    assert slugs == ["ai-driven-dev"]


@pytest.mark.asyncio
async def test_my_courses_includes_status(
    client, auth_user, auth_token, db_session
):
    a, _ = await _seed_courses(db_session)
    db_session.add(
        Enrollment(user_id=auth_user.id, course_id=a.id, status="paused")
    )
    await db_session.commit()

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/courses")
    assert res.json()["items"][0]["status"] == "paused"
```

- [ ] **Step 2: Run — expected to fail (no /api/courses yet)**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_courses_api.py -q
```

Expected: 5 failing (404 / 401 mismatches)。

- [ ] **Step 3: `api/courses.py` を作成**

`backend/app/api/courses.py` を新規作成:

```python
"""Sprint 7 — public catalog + authenticated my-courses listing."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.course import Course
from app.models.user import User
from app.schemas.course import (
    CourseCatalogItem,
    CourseCatalogOut,
    MyCourseItem,
    MyCoursesOut,
)
from app.services.enrollment import list_my_courses

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("/catalog", response_model=CourseCatalogOut)
async def get_catalog(db: AsyncSession = Depends(get_db)) -> CourseCatalogOut:
    """Public list of available courses (used by the registration form)."""
    result = await db.execute(
        select(Course).order_by(Course.sort_order, Course.title)
    )
    items = [
        CourseCatalogItem(
            slug=c.slug,
            title=c.title,
            description=c.description,
            sort_order=c.sort_order,
        )
        for c in result.scalars().all()
    ]
    return CourseCatalogOut(items=items)


@router.get("", response_model=MyCoursesOut)
async def get_my_courses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MyCoursesOut:
    """Authenticated learner's enrolled courses."""
    items = await list_my_courses(db, user_id=user.id)
    return MyCoursesOut(
        items=[
            MyCourseItem(
                slug=it.slug, title=it.title,
                description=it.description, status=it.status,
            )
            for it in items
        ]
    )
```

- [ ] **Step 4: `main.py` で router を登録**

`backend/app/main.py` の `app.include_router(...)` ブロックに以下を追加（既存 `health.router` の直後を推奨、`/api/courses/catalog` を public ルートとして早めに評価）:

```python
from app.api import courses as courses_router
...
app.include_router(courses_router.router)
```

具体的には `app.include_router(health.router)` の直後に `app.include_router(courses_router.router)`。

- [ ] **Step 5: Run tests — should pass**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_courses_api.py -q
```

Expected: `5 passed`。

- [ ] **Step 6: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/api/courses.py backend/app/main.py backend/tests/test_courses_api.py
git commit -m "feat(sprint-7): GET /api/courses/catalog + GET /api/courses"
```

---

## Task 9: `/api/auth/register` に `course_slug` 必須化

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/services/progress.py`（`initialize_progress_for_course` を追加、`initialize_progress` は legacy shim 化）
- Create: `backend/tests/test_auth_api_course.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_auth_api_course.py` を新規作成:

```python
"""Sprint 7 — auth.register must require course_slug."""

import pytest
from sqlalchemy import select

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.progress import Progress
from app.models.user import User


async def _seed_courses(db):
    a = Course(slug="ai-driven-dev", title="AI Dev", sort_order=0)
    b = Course(slug="ai-era-se", title="SE", sort_order=1)
    db.add_all([a, b])
    await db.commit()
    return a, b


@pytest.mark.asyncio
async def test_register_requires_course_slug(client, db_session):
    await _seed_courses(db_session)
    res = client.post(
        "/api/auth/register",
        json={
            "email": "x@e.com", "name": "X",
            "password": "password123",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_unknown_slug(client, db_session):
    await _seed_courses(db_session)
    res = client.post(
        "/api/auth/register",
        json={
            "email": "x@e.com", "name": "X",
            "password": "password123",
            "course_slug": "nope",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_creates_enrollment(client, db_session):
    a, _ = await _seed_courses(db_session)
    res = client.post(
        "/api/auth/register",
        json={
            "email": "x@e.com", "name": "X",
            "password": "password123",
            "course_slug": "ai-era-se",
        },
    )
    assert res.status_code == 201
    user_id = res.json()["id"]

    enr = (
        await db_session.execute(
            select(Enrollment).where(Enrollment.user_id == user_id)
        )
    ).scalar_one()
    assert enr.status == "active"


@pytest.mark.asyncio
async def test_register_seeds_progress_for_chosen_course(client, db_session):
    a, b = await _seed_courses(db_session)
    res = client.post(
        "/api/auth/register",
        json={
            "email": "x@e.com", "name": "X",
            "password": "password123",
            "course_slug": "ai-era-se",
        },
    )
    user_id = res.json()["id"]
    rows = (
        await db_session.execute(
            select(Progress).where(Progress.user_id == user_id)
        )
    ).scalars().all()
    # ai-era-se has 1 phase (Phase 1 pilot)
    assert {r.phase for r in rows} == {1}
    assert all(r.course_id == b.id for r in rows)
```

- [ ] **Step 2: Run — expected to fail (422 on missing course_slug but no enrollment / progress seeding)**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_auth_api_course.py -q
```

Expected: 失敗。

- [ ] **Step 3: `services/progress.py` に `initialize_progress_for_course` 追加 + legacy shim**

`backend/app/services/progress.py` の `initialize_progress` を以下のように書き換える:

```python
async def initialize_progress_for_course(
    db: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    phase_numbers: list[int],
) -> None:
    """Seed progress rows for (user, course). The first phase in
    ``phase_numbers`` is unlocked; the rest start LOCKED."""
    now = datetime.now(UTC)
    sorted_phases = sorted(phase_numbers)
    for i, phase_no in enumerate(sorted_phases):
        is_first = i == 0
        db.add(
            Progress(
                user_id=user_id,
                course_id=course_id,
                phase=phase_no,
                status=(
                    ProgressStatus.IN_PROGRESS.value
                    if is_first
                    else ProgressStatus.LOCKED.value
                ),
                started_at=now if is_first else None,
            )
        )
    await db.flush()


async def initialize_progress(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Legacy single-course shim — seeds against DEFAULT_COURSE_SLUG.

    Kept for code paths that still call the old signature. New callers
    should use ``initialize_progress_for_course``."""
    from app.data.courses import DEFAULT_COURSE_SLUG, get_course
    from app.services.enrollment import _get_course_by_slug

    course_data = get_course(DEFAULT_COURSE_SLUG)
    db_course = await _get_course_by_slug(db, DEFAULT_COURSE_SLUG)
    phase_numbers = [p.phase for p in course_data.phases]
    await initialize_progress_for_course(
        db, user_id, db_course.id, phase_numbers
    )
```

`CURRICULUM` import は不要になるので削除。`from app.data.curriculum import CURRICULUM` 行を削除。

- [ ] **Step 4: `api/auth.py` を書き換え**

`backend/app/api/auth.py` の `register` を以下に置き換える:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.data.courses import COURSE_REGISTRY, get_course
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.enrollment import (
    AlreadyEnrolledError,
    CourseNotFoundError,
    _get_course_by_slug,
    enroll_user,
)
from app.services.progress import initialize_progress_for_course

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> UserOut:
    if payload.course_slug not in COURSE_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown course_slug: {payload.course_slug!r}",
        )

    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()

    try:
        await enroll_user(db, user_id=user.id, course_slug=payload.course_slug)
    except (CourseNotFoundError, AlreadyEnrolledError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e

    course_data = get_course(payload.course_slug)
    db_course = await _get_course_by_slug(db, payload.course_slug)
    await initialize_progress_for_course(
        db,
        user.id,
        db_course.id,
        [p.phase for p in course_data.phases],
    )

    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)
```

`login` と `me` は変更不要。

- [ ] **Step 5: Run tests — should pass**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_auth_api_course.py -q
```

Expected: `4 passed`。

- [ ] **Step 6: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/api/auth.py backend/app/services/progress.py backend/tests/test_auth_api_course.py
git commit -m "feat(sprint-7): require course_slug at register + per-course progress init"
```

---

## Task 10: `chat_store` と `submission` サービスを course 対応

**Files:**
- Modify: `backend/app/memory/chat_store.py`
- Modify: `backend/app/services/submission.py`

> **ANTI-HALLUCINATION:** `Submission` の `course_id` は Task 4 で追加済み。本 Task では service / chat_store のシグネチャだけ拡張する。`instructor_comments` 関連には触らない。

- [ ] **Step 1: `chat_store.py` を書き換え**

`backend/app/memory/chat_store.py` の全内容を以下に置き換える:

```python
"""SQL-backed chat history store (Sprint 1, Sprint 7 course-aware)."""

import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.chat_history import ChatHistory


class SqlChatStore:
    """Async chat history store backed by `chat_history` table.

    All getters / setters take ``course_id`` to keep chats from
    different courses isolated even when phase numbers collide."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @property
    def db(self) -> AsyncSession:
        return self._db

    async def get_history(
        self,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        phase: int,
    ) -> list[dict[str, str]]:
        result = await self._db.execute(
            select(ChatHistory)
            .where(
                ChatHistory.user_id == user_id,
                ChatHistory.course_id == course_id,
                ChatHistory.phase == phase,
            )
            .order_by(ChatHistory.created_at)
        )
        return [
            {"role": m.role, "content": m.content}
            for m in result.scalars().all()
        ]

    async def append(
        self,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        phase: int,
        role: str,
        content: str,
    ) -> None:
        self._db.add(
            ChatHistory(
                user_id=user_id,
                course_id=course_id,
                phase=phase,
                role=role,
                content=content,
            )
        )
        await self._db.flush()


async def get_chat_store(db: AsyncSession = Depends(get_db)) -> SqlChatStore:
    return SqlChatStore(db)
```

- [ ] **Step 2: `submission.py` の course_id 必須化**

`backend/app/services/submission.py` を読み、`create_submission` 系関数のシグネチャに `course_id: uuid.UUID` を追加し、INSERT 時に渡す。`task_no` 上限チェックは:

```python
from app.data.courses import get_course

course = get_course(course_slug)
phase_def = next((p for p in course.phases if p.phase == phase), None)
if phase_def is None:
    raise PhaseNotFoundError(phase)
if task_no < 1 or task_no > len(phase_def.tasks):
    raise TaskNotFoundError(phase, task_no)
```

具体的な差分箇所:

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
grep -n "task_no\|create_submission\|^async def" app/services/submission.py
```

該当関数を見つけ、すべての書き込みパスに `course_id` を必須引数として追加。

- [ ] **Step 3: 一旦テスト未実装で commit （コンパイル可能だがテストは未対応で赤を持続）**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/memory/chat_store.py backend/app/services/submission.py
git commit -m "feat(sprint-7): chat_store + submission service require course_id"
```

---

## Task 11: weakness / recommendation / nudge / progress_summary を course 対応

**Files:**
- Modify: `backend/app/services/weakness.py`
- Modify: `backend/app/services/recommendation.py`
- Modify: `backend/app/services/nudge.py`
- Modify: `backend/app/services/progress_summary.py`
- Modify: `backend/app/services/dashboard.py`

> **ANTI-HALLUCINATION:** これらは Sprint 5 で追加されたサービス。各関数は `user_id` を必須としていた。本 Task では同位置に `course_id` を必須引数追加する。`compose_dashboard_for_admin` (Sprint 6) も同様。

- [ ] **Step 1: `weakness.py` を course 対応**

`backend/app/services/weakness.py` のクエリ群に `Submission.course_id == course_id` を追加。`compute_weakness` と `compute_top_weakness_tags_bulk` の両方の引数に `course_id: uuid.UUID` を追加する。

具体的な差分例:

```python
async def compute_weakness(
    db: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
) -> WeaknessResult:
    result = await db.execute(
        select(Submission)
        .where(
            Submission.user_id == user_id,
            Submission.course_id == course_id,
            Submission.score.is_not(None),
        )
        .order_by(Submission.submitted_at.desc())
    )
    ...
```

`compute_top_weakness_tags_bulk(db, user_ids: list[uuid.UUID])` は `user_ids: list[tuple[uuid.UUID, uuid.UUID]]` (user_id, course_id) ペアに変更。返り値は `dict[uuid.UUID, str | None]` のまま (user_id → top tag) — admin users 一覧は user ごとに primary course の弱点を返す。

- [ ] **Step 2: `recommendation.py` を course 対応**

`compute_recommendations(db, embedding_client, *, user_id, top_weakness_tags)` のシグネチャに `course_id: uuid.UUID` を追加し、`Submission` / `Embedding` クエリすべてに `course_id` フィルタを追加。

- [ ] **Step 3: `nudge.py` を course 対応**

`get_or_generate(db, *, claude, user_id, ...)` に `course_id: uuid.UUID` を追加。`UserNudge` の PK が `(user_id, course_id)` になったので、`select(UserNudge).where(...)` の条件にも追加。`input_signature` の計算式にも `course_id` を含めるとコース切替時の cache miss が確実に。

具体的なシグネチャ例:

```python
async def get_or_generate(
    db: AsyncSession,
    *,
    claude,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    progress_summary: ProgressSummary,
    top_weakness_tags: list[str],
    top_recommendation_key: str | None,
) -> NudgeResult: ...
```

- [ ] **Step 4: `progress_summary.py` を course 対応**

`compute_progress_summary(db, user_id)` に `course_id` を追加。`Progress` と `Submission` のクエリに `.where(... .course_id == course_id)` を追加。`total_tasks` の計算は `get_course(slug).phases` から行うため、`compute_progress_summary` も `course_slug` 引数を持つ:

```python
async def compute_progress_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    course_slug: str,
) -> ProgressSummary: ...
```

`total_tasks = sum(len(p.tasks) for p in get_course(course_slug).phases)`。

- [ ] **Step 5: `dashboard.py` の `compose_dashboard` / `compose_dashboard_for_admin` を course 対応**

両関数のシグネチャに `course_id: uuid.UUID, course_slug: str` を追加。Sprint 5 / 6 の既存 try/except 構造はそのまま保持し、各サブサービス呼び出しに `course_id` / `course_slug` を渡す。

```python
async def compose_dashboard(
    db: AsyncSession,
    *,
    claude,
    embedding_client,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    course_slug: str,
) -> DashboardData: ...


async def compose_dashboard_for_admin(
    db: AsyncSession,
    *,
    embedding_client,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    course_slug: str,
) -> AdminDashboardData: ...
```

- [ ] **Step 6: Build check — まだテストはレッドだが import チェックは通ること**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run python -c "from app.services import weakness, recommendation, nudge, progress_summary, dashboard; print('ok')"
```

Expected: `ok`。

- [ ] **Step 7: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/services/weakness.py backend/app/services/recommendation.py backend/app/services/nudge.py backend/app/services/progress_summary.py backend/app/services/dashboard.py
git commit -m "feat(sprint-7): dashboard subservices require course_id + course_slug"
```

---

## Task 12: 既存 API へ `?course=` 適用（curriculum / progress / chat / submissions）

**Files:**
- Modify: `backend/app/api/curriculum.py`
- Modify: `backend/app/api/progress.py`
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/api/submissions.py`

> **ANTI-HALLUCINATION:** `?course=` を `Depends(get_course_context)` で解決する。各ルートで個別に `course` クエリ引数を取り直さない（重複定義防止）。

- [ ] **Step 1: `api/curriculum.py` を書き換え**

`backend/app/api/curriculum.py` の既存ルート群を `CourseContext` 依存に書き換える:

```python
from fastapi import APIRouter, Depends, HTTPException

from app.core.course_deps import CourseContext, get_course_context
from app.data.courses import PhaseNotFoundError, get_phase

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


@router.get("/phases")
async def list_phases(ctx: CourseContext = Depends(get_course_context)):
    return [
        {
            "phase": p.phase,
            "title": p.title,
            "goal": p.goal,
            "tasks": [
                {"task_no": t.task_no, "title": t.title}
                for t in p.tasks
            ],
        }
        for p in ctx.course.phases
    ]


@router.get("/phases/{phase}")
async def get_phase_detail(
    phase: int,
    ctx: CourseContext = Depends(get_course_context),
):
    try:
        p = get_phase(ctx.course.slug, phase)
    except PhaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"phase {phase} not found")
    return {
        "phase": p.phase,
        "title": p.title,
        "goal": p.goal,
        "tasks": [
            {
                "task_no": t.task_no,
                "title": t.title,
                "description": t.description,
            }
            for t in p.tasks
        ],
    }
```

- [ ] **Step 2: `api/progress.py` を書き換え**

既存の `list_progress`/`complete_phase` を `CourseContext` 依存に書き換え、`Progress` クエリで `course_id` フィルタを追加。

- [ ] **Step 3: `api/chat.py` を書き換え**

`POST /api/chat` を `CourseContext` 依存に書き換え、`chat_store.get_history` / `chat_store.append` / system_prompt 解決を course 別に。`get_phase(ctx.course.slug, phase)` で system_prompt を取得。

- [ ] **Step 4: `api/submissions.py` を書き換え**

`POST /api/submissions` を `CourseContext` 依存に書き換え、`create_submission` 呼び出しに `course_id=ctx.course.id, course_slug=ctx.course.slug` を渡す。`task_no` 上限はサービス層で検証される。

- [ ] **Step 5: import 構造の整合性確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run python -c "from app.api import curriculum, progress, chat, submissions; print('ok')"
```

Expected: `ok`。

- [ ] **Step 6: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/api/curriculum.py backend/app/api/progress.py backend/app/api/chat.py backend/app/api/submissions.py
git commit -m "feat(sprint-7): scope existing routes via CourseContext (?course=)"
```

---

## Task 13: `/api/me/dashboard` と `/api/admin/users/{id}/dashboard` を course スコープ化

**Files:**
- Modify: `backend/app/api/me_dashboard.py`
- Modify: `backend/app/api/admin/user_dashboard.py`
- Create: `backend/tests/test_dashboard_api_multi_course.py`
- Create: `backend/tests/test_admin_user_dashboard_multi_course.py`

> **ANTI-HALLUCINATION:** Sprint 5 で導入した `/api/me/dashboard` と Sprint 6 で導入した `/api/admin/users/{id}/dashboard` の **両方** を `CourseContext` 依存に切り替える。新規ルートは追加しない。

- [ ] **Step 1: failing test for /api/me/dashboard course scoping**

`backend/tests/test_dashboard_api_multi_course.py` を新規作成:

```python
"""Sprint 7 — /api/me/dashboard must scope by course."""

import pytest

from app.core.security import hash_password
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.user import User


async def _enroll(db, user_id, course_id):
    db.add(Enrollment(user_id=user_id, course_id=course_id, status="active"))
    await db.commit()


@pytest.mark.asyncio
async def test_dashboard_requires_active_enrollment(
    client, auth_user, auth_token, db_session
):
    # No enrollment for ai-era-se -> 403
    db_session.add(Course(slug="ai-era-se", title="SE", sort_order=1))
    await db_session.commit()
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/me/dashboard?course=ai-era-se")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_returns_default_course_when_param_missing(
    client, auth_user, auth_token, db_session
):
    # auth_user fixture enrolls in ai-driven-dev automatically (Task 16)
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/me/dashboard")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_unknown_course_returns_404(
    client, auth_user, auth_token
):
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/me/dashboard?course=nope")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_data_isolated_per_course(
    client, auth_user, auth_token, db_session
):
    """Submissions in course A must not contribute to dashboard for course B."""
    # auth_user already enrolled in ai-driven-dev by fixture
    se = Course(slug="ai-era-se", title="SE", sort_order=1)
    db_session.add(se)
    await db_session.commit()
    await db_session.refresh(se)
    await _enroll(db_session, auth_user.id, se.id)

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    # Submit something to ai-driven-dev
    client.post(
        "/api/submissions?course=ai-driven-dev",
        json={"phase": 1, "task_no": 1, "content": "essay"},
    )
    # Dashboard for ai-era-se must show zero submissions
    res = client.get("/api/me/dashboard?course=ai-era-se")
    assert res.status_code == 200
    body = res.json()
    assert body["progress_summary"]["submission_count"] == 0
```

- [ ] **Step 2: failing test for admin user dashboard**

`backend/tests/test_admin_user_dashboard_multi_course.py` を新規作成:

```python
"""Sprint 7 — /api/admin/users/{id}/dashboard course scoping."""

import pytest

from app.models.course import Course
from app.models.enrollment import Enrollment


async def _seed(db, learner_id):
    se = Course(slug="ai-era-se", title="SE", sort_order=1)
    db.add(se)
    await db.commit()
    await db.refresh(se)
    db.add(Enrollment(user_id=learner_id, course_id=se.id, status="active"))
    await db.commit()
    return se


@pytest.mark.asyncio
async def test_admin_can_view_any_course_dashboard_without_enrollment(
    client, auth_user, admin_token, db_session
):
    """admin is_admin=True bypasses require_active_enrollment in CourseContext."""
    se = await _seed(db_session, auth_user.id)

    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get(
        f"/api/admin/users/{auth_user.id}/dashboard?course=ai-era-se"
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_admin_dashboard_unknown_course_returns_404(
    client, auth_user, admin_token
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get(
        f"/api/admin/users/{auth_user.id}/dashboard?course=nope"
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_admin_dashboard_default_course_when_param_missing(
    client, auth_user, admin_token
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get(f"/api/admin/users/{auth_user.id}/dashboard")
    assert res.status_code == 200
```

- [ ] **Step 3: `api/me_dashboard.py` を書き換え**

`backend/app/api/me_dashboard.py` の `GET /api/me/dashboard` を `CourseContext` 依存に切替:

```python
from fastapi import APIRouter, Depends

from app.core.course_deps import CourseContext, get_course_context
from app.core.deps import get_anthropic_client, get_current_user, get_embedding_client
from app.db.session import get_db
from app.models.user import User
from app.services.dashboard import compose_dashboard

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/dashboard")
async def get_my_dashboard(
    ctx: CourseContext = Depends(get_course_context),
    user: User = Depends(get_current_user),
    db = Depends(get_db),
    claude = Depends(get_anthropic_client),
    embedding_client = Depends(get_embedding_client),
):
    return await compose_dashboard(
        db,
        claude=claude,
        embedding_client=embedding_client,
        user_id=user.id,
        course_id=ctx.course.id,
        course_slug=ctx.course.slug,
    )
```

レスポンス schema は既存 (Sprint 5) のまま。

- [ ] **Step 4: `api/admin/user_dashboard.py` を書き換え**

同様に `GET /api/admin/users/{user_id}/dashboard` も `CourseContext` 依存に切替。Sprint 6 で `compose_dashboard_for_admin` を使用しているので、それを Task 11 で更新したシグネチャに合わせる:

```python
@router.get("/users/{user_id}/dashboard")
async def get_admin_user_dashboard(
    user_id: uuid.UUID,
    ctx: CourseContext = Depends(get_course_context),
    admin: User = Depends(require_admin),
    db = Depends(get_db),
    embedding_client = Depends(get_embedding_client),
):
    target_user = (await db.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return await compose_dashboard_for_admin(
        db,
        embedding_client=embedding_client,
        user_id=user_id,
        course_id=ctx.course.id,
        course_slug=ctx.course.slug,
    )
```

- [ ] **Step 5: テストが緑になることを確認（conftest 改修後）**

Task 16 で conftest を改修するまで、本タスク内では 7 件のテストすべてが赤になる。順序上 Task 13 → Task 16 → 再テストの流れ。本タスクでは「コードのみ commit」が許容ライン。

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_dashboard_api_multi_course.py tests/test_admin_user_dashboard_multi_course.py -q
```

Expected: 失敗（Task 16 まで pending）。

- [ ] **Step 6: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/api/me_dashboard.py backend/app/api/admin/user_dashboard.py backend/tests/test_dashboard_api_multi_course.py backend/tests/test_admin_user_dashboard_multi_course.py
git commit -m "feat(sprint-7): dashboard APIs scoped via CourseContext (red until conftest)"
```

---

## Task 14: admin users 一覧 + admin user 詳細を `enrollments` に対応

**Files:**
- Modify: `backend/app/api/admin/users.py`
- Modify: `backend/app/services/admin_query.py`

> **ANTI-HALLUCINATION:** `top_weakness_tag` は Sprint 6 で導入済み。本 Task では「コース別の primary enrollment 基準で集計する」よう既存ロジックを書き換える。

- [ ] **Step 1: `admin_query.list_users_with_progress` を course 対応**

`backend/app/services/admin_query.py` の該当関数を読む:

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
grep -n "def list_users\|top_weakness\|primary\|enrollment" app/services/admin_query.py
```

各 user について `primary_course_id`（sort_order 最小の status=active の enrollment）を解決し、`top_weakness_tag` 集計はその course でフィルタするよう書き換える。

具体イメージ:

```python
# 1) SELECT user_id, MIN(courses.sort_order) で primary course を解決
primary_courses_rows = (await db.execute(
    select(Enrollment.user_id, Course.id, Course.slug, Course.sort_order)
    .join(Course, Enrollment.course_id == Course.id)
    .where(Enrollment.status == "active")
    .order_by(Enrollment.user_id, Course.sort_order)
)).all()

primary_for: dict[uuid.UUID, uuid.UUID] = {}
for row in primary_courses_rows:
    primary_for.setdefault(row.user_id, row[1])  # course_id

# 2) compute_top_weakness_tags_bulk に (user_id, course_id) ペアで渡す
pairs = [(uid, primary_for[uid]) for uid in user_ids if uid in primary_for]
tag_map = await compute_top_weakness_tags_bulk(db, pairs)
```

`completed_phases` / `in_progress_phases` も同様に primary course でフィルタする。

- [ ] **Step 2: `api/admin/users.py` の `GET /api/admin/users/{user_id}` レスポンスに enrollments を追加**

```python
from app.schemas.course import EnrollmentOut

@router.get("/{user_id}", response_model=AdminUserDetail)
async def get_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserDetail:
    user = (await db.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    enrollments_rows = (await db.execute(
        select(Enrollment, Course)
        .join(Course, Enrollment.course_id == Course.id)
        .where(Enrollment.user_id == user_id)
        .order_by(Course.sort_order)
    )).all()
    enrollments = [
        EnrollmentOut(
            course_slug=c.slug,
            course_title=c.title,
            status=e.status,
            enrolled_at=e.enrolled_at,
        )
        for e, c in enrollments_rows
    ]

    summary = await build_user_summary(db, user)
    return AdminUserDetail(**summary.model_dump(), enrollments=enrollments)
```

`AdminUserDetail` への切替は Task 5 で schemas 側を整えた前提。

- [ ] **Step 3: import エラーが無いことを確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run python -c "from app.api.admin import users; print('ok')"
```

Expected: `ok`。

- [ ] **Step 4: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/api/admin/users.py backend/app/services/admin_query.py
git commit -m "feat(sprint-7): admin users/detail returns enrollments + per-course weakness"
```

---

## Task 15: ai-era-se 8 課題に対応した submission テスト

**Files:**
- Create: `backend/tests/test_submission_se_8tasks.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_submission_se_8tasks.py` を新規作成:

```python
"""Sprint 7 — submissions: task_no upper bound is per-course."""

import pytest

from app.models.course import Course
from app.models.enrollment import Enrollment


async def _enroll_se(db, user_id):
    se = (await db.execute(
        select(Course).where(Course.slug == "ai-era-se")
    )).scalar_one()
    db.add(Enrollment(user_id=user_id, course_id=se.id, status="active"))
    await db.commit()
    return se


@pytest.mark.asyncio
async def test_ai_era_se_accepts_task_no_8(
    client, auth_user, auth_token, db_session
):
    from sqlalchemy import select  # local to avoid conftest import order
    se = (await db_session.execute(
        select(Course).where(Course.slug == "ai-era-se")
    )).scalar_one()
    db_session.add(
        Enrollment(user_id=auth_user.id, course_id=se.id, status="active")
    )
    await db_session.commit()

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.post(
        "/api/submissions?course=ai-era-se",
        json={"phase": 1, "task_no": 8, "content": "essay"},
    )
    assert res.status_code in (200, 201)


@pytest.mark.asyncio
async def test_ai_era_se_rejects_task_no_9(
    client, auth_user, auth_token, db_session
):
    from sqlalchemy import select
    se = (await db_session.execute(
        select(Course).where(Course.slug == "ai-era-se")
    )).scalar_one()
    db_session.add(
        Enrollment(user_id=auth_user.id, course_id=se.id, status="active")
    )
    await db_session.commit()

    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.post(
        "/api/submissions?course=ai-era-se",
        json={"phase": 1, "task_no": 9, "content": "essay"},
    )
    assert res.status_code == 422
```

Note: `from sqlalchemy import select` は module-top に上げる方が綺麗だが、subagent が conftest を読まずに module-top import を変更してハルシネートしないよう、明示的に local import で書いている（実装時は移動可）。

- [ ] **Step 2: Commit（Task 16 まで赤を許容）**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/tests/test_submission_se_8tasks.py
git commit -m "test(sprint-7): submissions accept task_no=8 for ai-era-se, reject 9"
```

---

## Task 16: `conftest.py` を全面改修（courses seed + default_course_id + 既存 fixture を course 対応）

**Files:**
- Modify: `backend/tests/conftest.py`

> **ANTI-HALLUCINATION:** 既存 fixture (`auth_user` / `admin_user` / `db_session` 等) の **名前と意味は維持**。`initialize_progress` の呼び出しを `initialize_progress_for_course` に置き換え、`enroll_user` を呼ぶ。新規 fixture は `default_course_id` のみ追加。

- [ ] **Step 1: conftest を読む**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && wc -l tests/conftest.py
```

ファイル全体を確認してから改修。

- [ ] **Step 2: courses seed + default_course_id fixture 追加**

`backend/tests/conftest.py` の `_setup_db` の直後に、各テスト前の `db_session` truncate より **前** に courses seed を入れる fixture を追加。最も簡単な方法は `db_session` fixture 内で truncate 後に seed する:

```python
@pytest_asyncio.fixture
async def db_session(_setup_db):
    """Truncate all tables before each test, then yield an AsyncSession.

    Sprint 7: courses table is re-seeded after every truncate so
    enrollments / progress / submissions can FK into it."""
    from app.db.base import Base
    from app.db.session import SessionLocal, engine
    from app.data.courses import COURSE_REGISTRY

    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(
                text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
            )

    async with SessionLocal() as session:
        # Re-seed courses (fixed UUIDs match the Alembic migration).
        from app.models.course import Course
        for slug, c in COURSE_REGISTRY.items():
            session.add(
                Course(
                    id=c.id, slug=c.slug, title=c.title,
                    description=c.description, sort_order=c.sort_order,
                )
            )
        await session.commit()
        yield session


@pytest_asyncio.fixture
async def default_course_id(db_session):
    """Sprint 7 — the ai-driven-dev course's fixed UUID."""
    import uuid
    return uuid.UUID("00000000-0000-4000-8000-000000000001")
```

- [ ] **Step 3: `auth_user` / `admin_user` を course 対応に書き換え**

```python
@pytest_asyncio.fixture
async def auth_user(db_session, default_course_id):
    from app.core.security import hash_password
    from app.models.user import User
    from app.services.enrollment import enroll_user
    from app.services.progress import initialize_progress_for_course
    from app.data.courses import DEFAULT_COURSE_SLUG, get_course

    user = User(
        email="alice@example.com",
        name="アリス",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.flush()
    await enroll_user(
        db_session, user_id=user.id, course_slug=DEFAULT_COURSE_SLUG
    )
    course_data = get_course(DEFAULT_COURSE_SLUG)
    await initialize_progress_for_course(
        db_session, user.id, default_course_id,
        [p.phase for p in course_data.phases],
    )
    await db_session.commit()
    await db_session.refresh(user)
    return user
```

`admin_user` も同パターンで `is_admin=True` を維持しつつ、enroll + initialize_progress_for_course を呼ぶ。

- [ ] **Step 4: 既存テストの一部が壊れる箇所を直接修正**

ハンドオフメモが特定した既知の修正対象:

- `tests/test_comment_thread_service.py` の `sub_b` 直接生成箇所に `course_id=default_course_id` を **必ず**付与（プロトタイプで遭遇済みのパターン）

その他ファイルは grep で網羅的に洗い出す:

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
grep -rln "Submission(\|ChatHistory(\|Progress(\|UserNudge(\|Embedding(" tests/
```

各ファイルでコンストラクタ呼び出しに `course_id=default_course_id` を追加（fixture 引数も追加）。多数あるので 1 ファイルずつ修正。同時に `chat_store.get_history(user_id, phase)` / `chat_store.append(user_id, phase, ...)` 呼び出しは `chat_store.get_history(user_id, course_id, phase)` / `chat_store.append(user_id, course_id, phase, ...)` に書き換える。

具体例 (`tests/test_admin_users_api.py` を仮定):

```python
async def test_some_thing(auth_user, default_course_id, db_session):
    s = Submission(
        user_id=auth_user.id,
        course_id=default_course_id,   # Sprint 7
        phase=1, task_no=1, content="essay",
    )
    ...
```

`chat_store.get_history(user_id, phase)` 呼び出しがあるテストは `chat_store.get_history(user_id, course_id, phase)` に修正。

- [ ] **Step 5: 全テスト緑を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q 2>&1 | tail -20
```

Expected: `338 passed`（298 + 新規 ≈40）。失敗が残る場合は個別に修正してから再実行。

- [ ] **Step 6: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/tests/
git commit -m "test(sprint-7): conftest re-seeds courses + auth/admin fixtures enroll + per-course progress"
```

---

## Task 17: フロント — `types/course.ts` + `stores/course.ts` + `lib/api.ts` 拡張

**Files:**
- Create: `frontend/src/types/course.ts`
- Create: `frontend/src/stores/course.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/__tests__/course.store.spec.ts`

> **ANTI-HALLUCINATION:** Sprint 6 で既に `stores/dashboard.ts`, `stores/admin.ts` が存在する。本 Task ではそれらを拡張しない（Task 18 / 19 で扱う）。

- [ ] **Step 1: `types/course.ts` を作成**

`frontend/src/types/course.ts` を新規作成:

```ts
export interface CourseCatalogItem {
  slug: string;
  title: string;
  description: string | null;
  sort_order: number;
}

export interface CourseCatalogResponse {
  items: CourseCatalogItem[];
}

export interface MyCourseItem {
  slug: string;
  title: string;
  description: string | null;
  status: 'active' | 'paused' | 'completed';
}

export interface MyCoursesResponse {
  items: MyCourseItem[];
}
```

- [ ] **Step 2: `lib/api.ts` に course 系の helper を追加**

`frontend/src/lib/api.ts` の export 群に追加:

```ts
import type {
  CourseCatalogResponse,
  MyCoursesResponse,
} from '@/types/course';

export function withCourse(slug: string, extra: Record<string, string> = {}): string {
  const params = new URLSearchParams({ course: slug, ...extra });
  return `?${params.toString()}`;
}

export const api = {
  ...existingApi,
  listCourseCatalog: (): Promise<CourseCatalogResponse> =>
    rawRequest<CourseCatalogResponse>('/api/courses/catalog', { method: 'GET' }),
  listMyCourses: (): Promise<MyCoursesResponse> =>
    rawRequest<MyCoursesResponse>('/api/courses', { method: 'GET' }),
};
```

既存 API（`getMyDashboard`, `getCurriculumPhases`, `postChat`, `createSubmission`, `getAdminUserDashboard` 等）の URL 文字列に `withCourse(courseSlug)` を差し込み、シグネチャに `courseSlug: string` を必須引数として追加。例:

```ts
// Before
getMyDashboard: (): Promise<DashboardResponse> =>
  rawRequest('/api/me/dashboard', { method: 'GET' }),

// After
getMyDashboard: (courseSlug: string): Promise<DashboardResponse> =>
  rawRequest(`/api/me/dashboard${withCourse(courseSlug)}`, { method: 'GET' }),
```

- [ ] **Step 3: `stores/course.ts` を作成**

`frontend/src/stores/course.ts` を新規作成:

```ts
import { defineStore } from 'pinia';
import { api } from '@/lib/api';
import type {
  CourseCatalogItem,
  MyCourseItem,
} from '@/types/course';

interface State {
  activeSlug: string | null;
  myCourses: MyCourseItem[];
  catalog: CourseCatalogItem[];
  loaded: boolean;
}

const STORAGE_KEY = 'ai-tutor.activeCourse';

export const useCourseStore = defineStore('course', {
  state: (): State => ({
    activeSlug: null,
    myCourses: [],
    catalog: [],
    loaded: false,
  }),
  actions: {
    setActiveCourse(slug: string): void {
      this.activeSlug = slug;
      try {
        window.localStorage.setItem(STORAGE_KEY, slug);
      } catch {
        // localStorage may be unavailable (private mode); silent fall-through
      }
    },
    hydrateActiveFromStorage(): void {
      try {
        const stored = window.localStorage.getItem(STORAGE_KEY);
        if (stored !== null) this.activeSlug = stored;
      } catch {
        // ignore
      }
    },
    async fetchMyCourses(): Promise<void> {
      const res = await api.listMyCourses();
      this.myCourses = res.items;
      this.loaded = true;
      if (this.activeSlug === null && res.items.length > 0) {
        this.setActiveCourse(res.items[0].slug);
      }
    },
    async fetchCatalog(): Promise<void> {
      const res = await api.listCourseCatalog();
      this.catalog = res.items;
    },
  },
});
```

- [ ] **Step 4: failing test for course store**

`frontend/src/__tests__/course.store.spec.ts` を新規作成:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      listCourseCatalog: vi.fn(),
      listMyCourses: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import { useCourseStore } from '@/stores/course';

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

describe('course store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it('setActiveCourse persists to localStorage', () => {
    const store = useCourseStore();
    store.setActiveCourse('ai-era-se');
    expect(store.activeSlug).toBe('ai-era-se');
    expect(window.localStorage.getItem('ai-tutor.activeCourse')).toBe('ai-era-se');
  });

  it('hydrateActiveFromStorage restores activeSlug', () => {
    window.localStorage.setItem('ai-tutor.activeCourse', 'ai-driven-dev');
    const store = useCourseStore();
    store.hydrateActiveFromStorage();
    expect(store.activeSlug).toBe('ai-driven-dev');
  });

  it('fetchMyCourses sets first course as active when none chosen', async () => {
    mocked.listMyCourses.mockResolvedValue({
      items: [
        { slug: 'ai-driven-dev', title: 'A', description: null, status: 'active' },
      ],
    });
    const store = useCourseStore();
    await store.fetchMyCourses();
    expect(store.activeSlug).toBe('ai-driven-dev');
    expect(store.myCourses).toHaveLength(1);
    expect(store.loaded).toBe(true);
  });

  it('fetchCatalog populates catalog state', async () => {
    mocked.listCourseCatalog.mockResolvedValue({
      items: [
        { slug: 'ai-driven-dev', title: 'A', description: null, sort_order: 0 },
        { slug: 'ai-era-se', title: 'SE', description: 'd', sort_order: 1 },
      ],
    });
    const store = useCourseStore();
    await store.fetchCatalog();
    expect(store.catalog.map((c) => c.slug)).toEqual([
      'ai-driven-dev', 'ai-era-se',
    ]);
  });
});
```

- [ ] **Step 5: Run — should pass**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run src/__tests__/course.store.spec.ts
```

Expected: `4 passed`。

- [ ] **Step 6: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/types/course.ts frontend/src/stores/course.ts frontend/src/lib/api.ts frontend/src/__tests__/course.store.spec.ts
git commit -m "feat(sprint-7): frontend course types + store + lib/api helpers"
```

---

## Task 18: `LoginView` にコース選択 + `auth.register` に courseSlug

**Files:**
- Modify: `frontend/src/stores/auth.ts`
- Modify: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/__tests__/LoginView.spec.ts`

- [ ] **Step 1: `stores/auth.ts` を courseSlug 対応**

`frontend/src/stores/auth.ts` の `register` を以下に置き換える:

```ts
async register(email: string, name: string, password: string, courseSlug: string) {
  await rawRequest<UserOut>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      email, name, password, course_slug: courseSlug,
    }),
  });
},
```

- [ ] **Step 2: failing test for LoginView**

`frontend/src/__tests__/LoginView.spec.ts` を新規作成:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { mount, flushPromises } from '@vue/test-utils';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      listCourseCatalog: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import LoginView from '@/views/LoginView.vue';

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

const router = {
  push: vi.fn(),
};

vi.mock('vue-router', () => ({
  useRouter: () => router,
}));

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    mocked.listCourseCatalog.mockResolvedValue({
      items: [
        { slug: 'ai-driven-dev', title: 'AI Dev', description: null, sort_order: 0 },
        { slug: 'ai-era-se', title: 'SE', description: null, sort_order: 1 },
      ],
    });
  });

  it('fetches catalog on mount', async () => {
    mount(LoginView);
    await flushPromises();
    expect(mocked.listCourseCatalog).toHaveBeenCalledOnce();
  });

  it('shows course select only in register mode', async () => {
    const w = mount(LoginView);
    await flushPromises();
    // default mode is login -> no select
    expect(w.find('select[data-test="course-select"]').exists()).toBe(false);
    // switch to register
    await w.findAll('button[role="tab"]').at(1)!.trigger('click');
    expect(w.find('select[data-test="course-select"]').exists()).toBe(true);
  });

  it('disables submit when course unselected in register mode', async () => {
    const w = mount(LoginView);
    await flushPromises();
    await w.findAll('button[role="tab"]').at(1)!.trigger('click');
    await w.find('input[type="email"]').setValue('x@e.com');
    await w.find('input[type="text"]').setValue('X');
    await w.find('input[type="password"]').setValue('password123');
    const submit = w.find('button[type="submit"]');
    expect(submit.attributes('disabled')).toBeDefined();
  });

  it('enables submit when all fields including course are set', async () => {
    const w = mount(LoginView);
    await flushPromises();
    await w.findAll('button[role="tab"]').at(1)!.trigger('click');
    await w.find('input[type="email"]').setValue('x@e.com');
    await w.find('input[type="text"]').setValue('X');
    await w.find('input[type="password"]').setValue('password123');
    await w.find('select[data-test="course-select"]').setValue('ai-era-se');
    const submit = w.find('button[type="submit"]');
    expect(submit.attributes('disabled')).toBeUndefined();
  });
});
```

- [ ] **Step 3: `LoginView.vue` を書き換え**

`frontend/src/views/LoginView.vue` の `<script setup>` ブロック全体を以下に置き換える:

```vue
<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useCourseStore } from '@/stores/course';
import { api } from '@/lib/api';
import type { CourseCatalogItem } from '@/types/course';

const mode = ref<'login' | 'register'>('login');
const email = ref('');
const password = ref('');
const name = ref('');
const courseSlug = ref('');
const catalog = ref<CourseCatalogItem[]>([]);
const error = ref<string | null>(null);
const notice = ref<string | null>(null);
const submitting = ref(false);

const auth = useAuthStore();
const course = useCourseStore();
const router = useRouter();

const canSubmit = computed(() => {
  if (submitting.value) return false;
  if (!email.value || !password.value) return false;
  if (mode.value === 'register') {
    if (!name.value || !courseSlug.value) return false;
  }
  return true;
});

onMounted(async () => {
  try {
    const res = await api.listCourseCatalog();
    catalog.value = res.items;
  } catch {
    // network failure: register form still shows but with empty options
  }
});

const submit = async () => {
  error.value = null;
  notice.value = null;
  submitting.value = true;
  try {
    if (mode.value === 'login') {
      await auth.login(email.value, password.value);
      await course.fetchMyCourses();
      if (course.myCourses.length === 1) {
        await router.push(`/courses/${course.myCourses[0].slug}`);
      } else {
        await router.push('/courses');
      }
    } else {
      await auth.register(email.value, name.value, password.value, courseSlug.value);
      course.setActiveCourse(courseSlug.value);
      mode.value = 'login';
      notice.value = '登録できました。続けてログインしてください。';
      password.value = '';
    }
  } catch (e) {
    if (e instanceof Error && e.message.includes('409')) {
      error.value = 'このメールアドレスは既に登録されています';
    } else if (e instanceof Error && e.message.includes('401')) {
      error.value = 'メールアドレスまたはパスワードが正しくありません';
    } else if (e instanceof Error && e.message.includes('422')) {
      error.value = '入力内容を確認してください';
    } else {
      error.value = '通信に失敗しました。時間をおいて再試行してください';
    }
  } finally {
    submitting.value = false;
  }
};
</script>
```

`<template>` 内、`<label>パスワード...</label>` の前に course select を挿入:

```vue
<label v-if="mode === 'register'">
  受講コース
  <select
    v-model="courseSlug"
    data-test="course-select"
    required
  >
    <option value="" disabled>選択してください</option>
    <option v-for="c in catalog" :key="c.slug" :value="c.slug">
      {{ c.title }}
    </option>
  </select>
</label>
```

そして `<button type="submit" :disabled="submitting">` を `:disabled="!canSubmit"` に変更。

- [ ] **Step 4: Run — should pass**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run src/__tests__/LoginView.spec.ts
```

Expected: `4 passed`。

- [ ] **Step 5: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/stores/auth.ts frontend/src/views/LoginView.vue frontend/src/__tests__/LoginView.spec.ts
git commit -m "feat(sprint-7): LoginView course select + auth.register accepts courseSlug"
```

---

## Task 19: `CourseListView` + router 再構成 + 旧 `/phases/:phase` redirect

**Files:**
- Create: `frontend/src/views/CourseListView.vue`
- Modify: `frontend/src/router/index.ts`
- Create: `frontend/src/__tests__/CourseListView.spec.ts`

- [ ] **Step 1: failing test を追加**

`frontend/src/__tests__/CourseListView.spec.ts` を新規作成:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { mount, flushPromises } from '@vue/test-utils';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      listCourseCatalog: vi.fn(),
      listMyCourses: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import CourseListView from '@/views/CourseListView.vue';

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
}));

describe('CourseListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('renders enrolled courses', async () => {
    mocked.listMyCourses.mockResolvedValue({
      items: [
        { slug: 'ai-driven-dev', title: 'AI Dev', description: 'd1', status: 'active' },
      ],
    });
    mocked.listCourseCatalog.mockResolvedValue({ items: [] });
    const w = mount(CourseListView);
    await flushPromises();
    expect(w.text()).toContain('AI Dev');
  });

  it('renders "request admin" hint for un-enrolled courses', async () => {
    mocked.listMyCourses.mockResolvedValue({ items: [] });
    mocked.listCourseCatalog.mockResolvedValue({
      items: [
        { slug: 'ai-era-se', title: 'SE', description: 'd', sort_order: 1 },
      ],
    });
    const w = mount(CourseListView);
    await flushPromises();
    expect(w.text()).toContain('SE');
    expect(w.text()).toContain('管理者へ依頼');
  });

  it('shows empty placeholder when no enrolled courses', async () => {
    mocked.listMyCourses.mockResolvedValue({ items: [] });
    mocked.listCourseCatalog.mockResolvedValue({ items: [] });
    const w = mount(CourseListView);
    await flushPromises();
    expect(w.text()).toContain('受講中のコースはありません');
  });
});
```

- [ ] **Step 2: `CourseListView.vue` を作成**

`frontend/src/views/CourseListView.vue` を新規作成:

```vue
<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { RouterLink } from 'vue-router';
import { useCourseStore } from '@/stores/course';

const course = useCourseStore();

onMounted(async () => {
  await Promise.all([course.fetchMyCourses(), course.fetchCatalog()]);
});

const unEnrolled = computed(() => {
  const enrolledSlugs = new Set(course.myCourses.map((c) => c.slug));
  return course.catalog.filter((c) => !enrolledSlugs.has(c.slug));
});
</script>

<template>
  <section class="course-list">
    <h1>受講コース</h1>

    <div v-if="course.myCourses.length === 0" class="empty">
      受講中のコースはありません
    </div>

    <ul v-else class="my-courses">
      <li v-for="c in course.myCourses" :key="c.slug">
        <RouterLink :to="`/courses/${c.slug}`">
          <span class="title">{{ c.title }}</span>
          <span v-if="c.description" class="desc">{{ c.description }}</span>
          <span class="status">{{ c.status }}</span>
        </RouterLink>
      </li>
    </ul>

    <div v-if="unEnrolled.length > 0" class="catalog">
      <h2>その他のコース</h2>
      <ul>
        <li v-for="c in unEnrolled" :key="c.slug">
          <span class="title">{{ c.title }}</span>
          <span v-if="c.description" class="desc">{{ c.description }}</span>
          <span class="note">追加受講は管理者へ依頼してください</span>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.course-list { max-width: 720px; margin: 2rem auto; }
.my-courses, .catalog ul { list-style: none; padding: 0; }
.my-courses li { margin: 0.75rem 0; }
.my-courses a {
  display: flex; flex-direction: column;
  padding: 1rem; border: 1px solid #e5e7eb; border-radius: 12px;
  text-decoration: none; color: inherit;
}
.title { font-weight: 600; }
.desc { color: #6b7280; font-size: 0.9rem; }
.status { color: #2563eb; font-size: 0.8rem; }
.note { color: #b91c1c; font-size: 0.8rem; }
.empty { color: #6b7280; padding: 2rem; text-align: center; }
</style>
```

- [ ] **Step 3: `router/index.ts` を書き換え**

`frontend/src/router/index.ts` の `routes` 配列を以下に変更:

```ts
import CourseListView from '@/views/CourseListView.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', redirect: '/courses' },
    { path: '/courses', name: 'courses', component: CourseListView },
    {
      path: '/courses/:courseSlug',
      name: 'course-home',
      component: HomeView,
      props: (route) => ({ courseSlug: route.params.courseSlug as string }),
    },
    {
      path: '/courses/:courseSlug/phases/:phase',
      name: 'course-phase',
      component: PhaseChatView,
      props: (route) => ({
        courseSlug: route.params.courseSlug as string,
        phase: Number(route.params.phase),
      }),
    },
    {
      path: '/phases/:phase',
      redirect: (to) => `/courses/ai-driven-dev/phases/${to.params.phase}`,
    },
    ...adminRoutes,
  ],
});
```

- [ ] **Step 4: `router/index.ts` の guard に course hydrate を追加**

`attachGuards` の `beforeEach` ハンドラに、`useCourseStore` をインポートして hydrate を追加:

```ts
import { useCourseStore } from '@/stores/course';
...
router.beforeEach(async (to) => {
  const auth = useAuthStore();
  const course = useCourseStore();
  if (auth.token && !auth.user) {
    try { await auth.fetchMe(); } catch { auth.logout(); }
  }
  if (auth.isAuthenticated) {
    course.hydrateActiveFromStorage();
    if (!course.loaded) {
      try { await course.fetchMyCourses(); } catch { /* ignore */ }
    }
  }
  if (to.meta.public !== true && !auth.isAuthenticated) {
    return { name: 'login' };
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'courses' };
  }
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: 'courses' };
  }
  return true;
});
```

- [ ] **Step 5: Run tests — should pass**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run src/__tests__/CourseListView.spec.ts
```

Expected: `3 passed`。

- [ ] **Step 6: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/views/CourseListView.vue frontend/src/router/index.ts frontend/src/__tests__/CourseListView.spec.ts
git commit -m "feat(sprint-7): CourseListView + routes + /phases/:n redirect to ai-driven-dev"
```

---

## Task 20: `HomeView` / `PhaseChatView` / `PhaseCard` / admin dashboard を courseSlug 対応

**Files:**
- Modify: `frontend/src/views/HomeView.vue`
- Modify: `frontend/src/views/PhaseChatView.vue`
- Modify: `frontend/src/components/PhaseCard.vue`
- Modify: `frontend/src/views/AdminUserDetailView.vue`
- Modify: `frontend/src/stores/admin.ts`
- Modify: `frontend/src/stores/dashboard.ts`
- Modify: `frontend/src/stores/curriculum.ts`
- Modify: `frontend/src/stores/chat.ts`
- Modify: `frontend/src/__tests__/HomeView.spec.ts`
- Modify: `frontend/src/__tests__/AdminUserDetailView.spec.ts`

> **ANTI-HALLUCINATION:** ストアごとに 1 メソッドずつ courseSlug 引数を必須化する。既存メソッド名は変更しない（admin の `fetchUserDashboard` 等）。Sprint 6 で追加されたメソッドは Task 14 のレスポンス schema 拡張に従う。

- [ ] **Step 1: `stores/dashboard.ts` を courseSlug 必須化**

`frontend/src/stores/dashboard.ts` を読んで、`fetchDashboard()` を以下に書き換える:

```ts
async fetchDashboard(courseSlug: string): Promise<void> {
  this.loading = true;
  try {
    this.data = await api.getMyDashboard(courseSlug);
    this.error = null;
  } catch (e) {
    this.error = e instanceof Error ? e.message : String(e);
  } finally {
    this.loading = false;
  }
},
```

- [ ] **Step 2: `stores/curriculum.ts` を courseSlug 必須化**

`fetchPhases()` / `fetchPhaseDetail()` 等のメソッドに `courseSlug: string` を引数追加し、`api.getCurriculumPhases(courseSlug)` 系を呼ぶ。

- [ ] **Step 3: `stores/chat.ts` を courseSlug 必須化**

`sendMessage` / `loadHistory` 系のメソッドに `courseSlug: string` を追加。

- [ ] **Step 4: `stores/admin.ts` の `fetchUserDashboard` を courseSlug 対応**

```ts
async fetchUserDashboard(userId: string, courseSlug: string): Promise<AdminDashboardResponse | null> {
  try {
    const data = await api.getAdminUserDashboard(userId, courseSlug);
    this.dashboardError = null;
    return data;
  } catch (e) {
    this.dashboardError = e instanceof Error ? e.message : String(e);
    return null;
  }
},
```

- [ ] **Step 5: `HomeView.vue` を書き換え**

`frontend/src/views/HomeView.vue` の `<script setup>` を以下のように改修:

```vue
<script setup lang="ts">
import { onMounted, watch } from 'vue';
import { useDashboardStore } from '@/stores/dashboard';
import { useCurriculumStore } from '@/stores/curriculum';
import { useCourseStore } from '@/stores/course';
import WeaknessCard from '@/components/WeaknessCard.vue';
import RecommendationsCard from '@/components/RecommendationsCard.vue';
import NudgeBanner from '@/components/NudgeBanner.vue';
import ProgressSummaryCard from '@/components/ProgressSummaryCard.vue';
import PhaseCard from '@/components/PhaseCard.vue';

const props = defineProps<{ courseSlug: string }>();
const course = useCourseStore();
const dashboard = useDashboardStore();
const curriculum = useCurriculumStore();

async function loadAll() {
  course.setActiveCourse(props.courseSlug);
  await Promise.all([
    dashboard.fetchDashboard(props.courseSlug),
    curriculum.fetchPhases(props.courseSlug),
  ]);
}

onMounted(loadAll);
watch(() => props.courseSlug, loadAll);
</script>
```

template 内の `<PhaseCard :phase="...">` 等に `:course-slug="courseSlug"` を渡す。

- [ ] **Step 6: `PhaseChatView.vue` を書き換え**

props に `courseSlug: string` を追加、`useChatStore().sendMessage(...)` に渡す。コース名をヘッダーに表示するため `useCourseStore().myCourses.find((c) => c.slug === courseSlug)?.title` を使用。

- [ ] **Step 7: `PhaseCard.vue` のリンク先変更**

`<RouterLink :to="\`/phases/${phase}\`">` を以下に変更:

```vue
<RouterLink :to="`/courses/${courseSlug}/phases/${phase}`">
```

`PhaseCard` の props に `courseSlug: string` を追加（required）。

- [ ] **Step 8: `AdminUserDetailView.vue` にコース切替セレクタを追加**

`<script setup>` の冒頭に:

```ts
import { ref, computed, watch } from 'vue';

const selectedCourseSlug = ref('');
const activeEnrollments = computed(() =>
  (admin.selectedUser?.enrollments ?? []).filter((e) => e.status === 'active'),
);

// 初期値: sort_order 最小の active enrollment
watch(activeEnrollments, (rows) => {
  if (rows.length > 0 && !selectedCourseSlug.value) {
    selectedCourseSlug.value = rows[0].course_slug;
  }
}, { immediate: true });

async function loadDashboardForSelectedCourse() {
  if (selectedCourseSlug.value && admin.selectedUser) {
    dashboardData.value = await admin.fetchUserDashboard(
      admin.selectedUser.id, selectedCourseSlug.value,
    );
  }
}
watch(selectedCourseSlug, loadDashboardForSelectedCourse);
```

template 側の dashboard セクション直前に:

```vue
<label v-if="activeEnrollments.length > 0" data-test="course-selector">
  コース
  <select v-model="selectedCourseSlug">
    <option v-for="e in activeEnrollments" :key="e.course_slug" :value="e.course_slug">
      {{ e.course_title }}
    </option>
  </select>
</label>
```

- [ ] **Step 9: 既存テストを修正 / 追加**

`frontend/src/__tests__/HomeView.spec.ts` の既存テストで `courseSlug` props を追加し、`useCourseStore` をモック:

```ts
const w = mount(HomeView, {
  props: { courseSlug: 'ai-driven-dev' },
});
```

`AdminUserDetailView.spec.ts` に course セレクタのテストを 2 件追加:

```ts
it('renders course selector when user has multiple enrollments', async () => {
  // selectedUser に enrollments: [{course_slug: 'a', course_title: 'A', status: 'active'}, ...]
  // を入れて mount → select 要素が表示されること
});

it('reloads dashboard when course selector changes', async () => {
  // mocked.getAdminUserDashboard を vi.fn() で監視
  // select 値を変えて trigger('change') → mocked が引数違いで再呼出されること
});
```

- [ ] **Step 10: Run frontend tests**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run
```

Expected: `79 passed`（既存 64 + Task 17 で +4 + Task 18 で +4 + Task 19 で +3 + 本 Task で +4 = 79）。

- [ ] **Step 11: Build check**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm run build
```

Expected: 成功。

- [ ] **Step 12: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/views/HomeView.vue frontend/src/views/PhaseChatView.vue frontend/src/components/PhaseCard.vue frontend/src/views/AdminUserDetailView.vue frontend/src/stores/admin.ts frontend/src/stores/dashboard.ts frontend/src/stores/curriculum.ts frontend/src/stores/chat.ts frontend/src/__tests__/HomeView.spec.ts frontend/src/__tests__/AdminUserDetailView.spec.ts
git commit -m "feat(sprint-7): courseSlug-aware views + admin dashboard course selector"
```

---

## Task 21: code-reviewer + security-reviewer + 全件テスト最終確認

**Files:**
- 各 reviewer が指摘した HIGH のみ修正（ファイル不定）

- [ ] **Step 1: バックエンド全件テスト**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q
```

Expected: `338 passed`。

- [ ] **Step 2: フロント全件テスト + ビルド**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run && npm run build
```

Expected: `79 passed`、ビルド成功。

- [ ] **Step 3: MCP playwright で手動 E2E 確認**

dev サーバを起動:

```bash
cd /Volumes/Seagate3TB/projects/edu && make dev
```

別ターミナルで:

1. http://localhost:5173/login → 新規登録モード → 「AI時代SE育成カリキュラム」選択 → 登録
2. ログイン → `/courses` → SE コース選択 → Phase 1 task 1 でチャット送信 → 提出
3. admin (`instructor@example.com`) でログイン → /admin/users/{learner_id} → コース切替セレクタで両コースの dashboard を確認
4. 既存ユーザログイン → `/courses/ai-driven-dev` の dashboard が空欄でないこと

問題があれば該当 Task に戻って修正、本 Task はリプレイ。

- [ ] **Step 4: code-reviewer agent を実行**

`Agent({ subagent_type: "code-reviewer", description: "Sprint 7 final review", prompt: "..." })` で `feature/sprint-7` ブランチ全体をレビュー依頼。プロンプト例:

```
feature/sprint-7 ブランチで Sprint 7 マルチコース化を完了した。spec は
docs/superpowers/specs/2026-06-10-sprint-7-multi-course-architecture-design.md、
plan は docs/superpowers/plans/2026-06-10-ai-tutor-curriculum-sprint-7.md。
重点チェック:
- 5 テーブルの course_id NOT NULL 化が漏れていないか
- /api/me/dashboard と /api/admin/users/{id}/dashboard が他コースのデータ漏洩を起こさないか
- auto-enroll マイグレーションの ON CONFLICT が冪等か
- frontend で activeSlug が null のままで fetch が走らないか
出力: HIGH / MEDIUM / LOW の指摘リスト。HIGH は本 Sprint で修正、MEDIUM/LOW は follow-up doc 候補。
```

- [ ] **Step 5: security-reviewer agent を実行**

同様に `subagent_type: "security-reviewer"` で:

```
feature/sprint-7 を OWASP Top 10 + Sprint 4 セキュリティ系項目で監査。
重点:
- /api/auth/register の course_slug が enum 経由でなく文字列受付 → 安全か
- /api/me/dashboard が他コースのデータを返さないか (CourseContext の検証)
- /api/admin/users/{id}/dashboard で admin 権限が課程横断で適切に効くか
- enroll_user が race condition で重複 enrollment を作らないか
- course_slug を URL に直接埋め込む箇所での injection 可能性
```

- [ ] **Step 6: HIGH 指摘を本 Sprint 内で修正**

各 reviewer が HIGH を出した箇所を個別 commit で修正:

```bash
git commit -m "fix(sprint-7): address HIGH-N from code/security review"
```

MEDIUM/LOW は `docs/superpowers/specs/2026-06-1X-sprint-7-followups.md` に記載（Task 22 で作成）。

- [ ] **Step 7: 再度全件テスト**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run
```

Expected: 両方緑。

---

## Task 22: README 更新 + follow-up doc 作成 + ハンドオフメモ削除 + main マージ

**Files:**
- Modify: `README.md`
- Create: `docs/superpowers/specs/2026-06-1X-sprint-7-followups.md`（実際の日付は実装日）
- Delete: `docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md`

- [ ] **Step 1: `README.md` を更新**

README の Sprint 完了マーク表に Sprint 7 行を追加し、マルチコース運用手順セクションを追記:

```markdown
## Sprint 完了状態

| Sprint | 内容 | 完了日 |
|---|---|---|
| ... 既存行 ... | | |
| Sprint 7 | マルチコース化 (ai-driven-dev + ai-era-se Phase 1) | 2026-06-1X |

## マルチコース運用

- 2 コース運用中: `ai-driven-dev` (既存、4 フェーズ) と `ai-era-se` (Phase 1 パイロット、8 課題)
- 新規登録時にコース選択必須 (`/login` → 新規登録 → コース select)
- API: `?course={slug}` クエリでスコープ。未指定時は `ai-driven-dev` に解決
- DB マイグレーション: `make migrate` で適用 (既存ユーザは ai-driven-dev に自動 enroll)
- 追加 enroll: 現状 admin 経由 API なし → 直接 SQL で `INSERT INTO enrollments` (follow-up で API 化予定)
```

- [ ] **Step 2: follow-up doc を作成**

`docs/superpowers/specs/2026-06-1X-sprint-7-followups.md` を新規作成（X は実装日）。code/security reviewer が出した MEDIUM/LOW 指摘 + 元 spec の out-of-scope 項目を整理:

```markdown
# Sprint 7 follow-up tickets

> 起点: docs/superpowers/specs/2026-06-10-sprint-7-multi-course-architecture-design.md
> 完了 sprint: Sprint 7 (commit <hash>)
> ベースライン: backend 338 / frontend 79 (Sprint 7 完了時)

## MEDIUM

### MED-1: `POST /api/admin/users/{id}/enrollments`
admin が既存ユーザに追加コースを enroll できる API。現状は直接 SQL のみ。
- 影響: ユーザ追加 enroll のオペレーション工数
- 対応: 新規 router 1 本 + service helper の `enroll_user` 再利用

### MED-2: `scripts/seed_embeddings.py` の `source_ref` をコース付きに
現状全 embedding が ai-driven-dev に紐付くが、`source_ref` 形式は単一コース時のままで RAG が将来曖昧になる。
- 対応: `source_ref = f"course:{slug}:phase:{n}:task:{m}"` 形式に変更 + 既存行も migration で書き換え

## LOW

### LOW-1: ai-era-se Phase 2-4 の投入
パイロット成功後、シラバスの Phase 2-4 をコード化。

### LOW-2: broadcast 通知のコーススコープ化
broadcast 機能本体実装と合わせて。

### LOW-3: Sprint 6 follow-up からのキャリーオーバー
MED-2 / MED-6 (判断保留)、LOW-4 (vitest CVE)、LOW-5 (Playwright headless)。

### LOW-N: (code/security review からの追加項目)
```

- [ ] **Step 3: Cursor ハンドオフメモを削除**

```bash
cd /Volumes/Seagate3TB/projects/edu
rm docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md
```

- [ ] **Step 4: 最終 commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add README.md docs/superpowers/specs/2026-06-1X-sprint-7-followups.md
git rm docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md
git commit -m "docs(sprint-7): README + follow-ups + remove handoff memo"
```

- [ ] **Step 5: main へ fast-forward マージ**

```bash
cd /Volumes/Seagate3TB/projects/edu
git checkout main
git pull --ff-only || true
git merge --ff-only feature/sprint-7
git push origin main
```

- [ ] **Step 6: feature ブランチを削除**

```bash
git branch -d feature/sprint-7
git push origin --delete feature/sprint-7 2>/dev/null || true
```

- [ ] **Step 7: 完了確認**

```bash
git log --oneline main | head -25
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q | tail -3
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run 2>&1 | tail -5
```

Expected: 最新 main HEAD が Sprint 7 完了 commit、backend `338 passed`、frontend `79 passed`。

---

## Plan 完了確認

- [ ] backend 338 passed
- [ ] frontend 79 passed
- [ ] Alembic upgrade / downgrade 両方成功
- [ ] 既存ユーザが `ai-driven-dev` で従来通り動く
- [ ] 新規登録時 `ai-era-se` を選んで Phase 1 task 1〜8 すべて提出可能
- [ ] admin がコース切替セレクタで両コースの dashboard を確認できる
- [ ] Cursor ハンドオフメモ削除済み
- [ ] follow-up doc 作成済み
- [ ] main HEAD = Sprint 7 完了 commit
