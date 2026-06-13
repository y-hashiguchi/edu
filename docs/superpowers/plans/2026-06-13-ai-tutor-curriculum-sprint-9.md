# AIチューターカリキュラム Sprint 9 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** admin が GUI から curriculum (Phase の title/goal/system_prompt + Task の title/description/skill_tags/deliverable/week_label) を編集できる admin UI を追加する。DB を curriculum の唯一の真実とし、Python レジストリは初期 seeder に格下げ。draft → publish 二段階で公開し、誤公開を防ぐ。

**Architecture:** `curriculum_phases` + `curriculum_tasks` の 2 テーブルを新設し、各行に published + draft の両状態を保持する。Alembic migration が初回 seed として `app/data/courses/{ai_driven_dev,ai_era_se}.py` の値を dict literal で書き写す (registry import に依存せず将来も再現可能)。ランタイムは `app/data/courses/runtime.py` の process-local in-memory cache で公開値を返却し、API の `get_course()` 同期シグネチャは温存。publish 時に当該 course の cache を再構築。

**Tech Stack:**
- Backend: 既存 (FastAPI / async SQLAlchemy / asyncpg / Alembic / Anthropic SDK / pgvector / fastembed / slowapi / arq + Redis)。新規依存ゼロ。
- Frontend: 既存 (Vue 3 / Pinia / TypeScript / Vue Router) のみ。
- 新規 SQL: 標準 PostgreSQL + `JSONB` (skill_tags)、新規 extension 不要。

---

## 設計書

実装中は以下の設計書を参照すること:

- 上位設計: `docs/superpowers/specs/2026-06-13-sprint-9-curriculum-editing-design.md`（本計画書の根拠、コミット `f389bd0`）
- Sprint 7 マルチコース化 spec: `docs/superpowers/specs/2026-06-10-sprint-7-multi-course-architecture-design.md`
- Sprint 7 follow-up doc: `docs/superpowers/specs/2026-06-11-sprint-7-followups.md`

---

## 主要意思決定（Sprint 9 計画時点）

| # | 判断項目 | 選択 | 理由 |
|---|---|---|---|
| 1 | 永続化 | DB 永続化、Python レジストリは seeder | デプロイなしで curriculum 更新可能 |
| 2 | 編集スコープ | 既存フィールド編集のみ (add/delete/reorder 除外) | YAGNI、`progress.total_tasks` 等の整合性を維持 |
| 3 | 公開戦略 | draft → publish 二段階、course 単位 publish | 誤公開防止 + 編集を関連変更とまとめて反映 |
| 4 | draft 表現 | 同一行 `draft_*` 列 + 空文字 sentinel | 別テーブル分離より join なしで読める |
| 5 | `skill_tags` 列型 | JSONB | pydantic ↔ JSON が自然、現状タグ検索なし |
| 6 | タグ意味論 | 常に現在のタグで再計算 (snapshot しない) | weakness/recommendation サービスを変更不要 |
| 7 | RBAC | Sprint 4 の `is_admin` をそのまま使用 | 小規模チーム前提 |
| 8 | seed の依存 | dict literal をコピペ、registry import なし | 将来 registry 削除しても過去 migration が動く |
| 9 | runtime API | `get_course()` 同期シグネチャ温存、内部 cache 化 | 全 service の呼び出し側を変更しないで済む |
| 10 | cache スコープ | process-local、multi-worker 対応は follow-up | dev/docker は単一プロセス前提 |
| 11 | publish 粒度 | course 単位 | 関連編集を一括公開、idempotent |
| 12 | PUT セマンティクス | exclude_unset (省略=変更なし、None=draft クリア、値=draft 設定) | inline edit との相性が良い |
| 13 | debounce 自動保存 | 500ms debounce で PUT 自動発火 | UX を滑らかに、明示「保存」ボタン不要 |
| 14 | rate limit | curriculum_write=120/min、publish=10/min を新設 | debounce 連発を許容、publish はキャッシュ再構築のため絞る |
| 15 | テスト戦略 | TDD 厳格 + 既存 conftest 改修 + 新規 ≈36 件 | Sprint 7 と同水準 |
| 16 | subagent 防御 | 各 Task で CRITICAL ANTI-HALLUCINATION GUARDS 明記 | Sprint 6 Task 4 の前科 |
| 17 | seed 内容のフリーズ | migration 作成時点の dict literal を凍結 | docstring で「以後の registry 変更は反映されない」を明示 |
| 18 | 既存 service 変更 | しない (Sprint 7 で `get_course()` 経由に集約済) | Sprint 7 設計の恩恵を最大化 |
| 19 | 起動時 0 行検出 | エラーで起動失敗 (silent fallback ではなく) | Alembic migration 未実行を明示 |
| 20 | E2E 追加 | 1 件 (admin が編集 → publish → 受講者画面に反映) | golden path カバー |

---

## スコープ境界

**含む（Sprint 9）：**

- DB:
  - `curriculum_phases` テーブル新規 (id, course_id, phase_no, title, goal, system_prompt, draft_*, updated_at)
  - `curriculum_tasks` テーブル新規 (id, phase_id, task_no, title, description, skill_tags JSONB, deliverable, week_label, draft_*, updated_at)
  - Alembic migration 1 リビジョン + 初回 seed (dict literal で COURSE_REGISTRY 内容をコピペ)
- バックエンド:
  - `app/models/curriculum_phase.py` (新規) + `app/models/curriculum_task.py` (新規)
  - `app/data/courses/runtime.py` (新規) — process-local cache + reload_from_db / reload_course / get_cached_course
  - `app/data/courses/__init__.py` (改修) — `get_course()` を cache 経由に rewire、`COURSE_REGISTRY` を cache の dict view として legacy alias 保持
  - `app/main.py` lifespan に `reload_from_db(db)` を組み込み (arq init/close と並走、0 行はエラー)
  - `app/services/curriculum_edit.py` (新規) — `put_phase_draft` / `put_task_draft` / `publish_course` / `discard_drafts`、exclude_unset セマンティクス対応
  - `app/schemas/admin_curriculum.py` (新規) — 6 出力 schema + 2 request schema
  - `app/api/admin/curriculum.py` (新規) — 6 ルート (GET 一覧 / GET 詳細 / PUT phase / PUT task / POST publish / POST draft DELETE)
  - `app/config.py` に `admin_curriculum_write_rate_limit="120/minute"` + `admin_curriculum_publish_rate_limit="10/minute"` を追加
  - `app/main.py` に admin curriculum router 登録
- フロントエンド:
  - `frontend/src/types/admin_curriculum.ts` (新規)
  - `frontend/src/stores/admin_curriculum.ts` (新規) — fetchList / fetchDetail / putPhase (debounced) / putTask (debounced) / publish / discardDrafts
  - `frontend/src/lib/api.ts` に admin curriculum API client を追加
  - `frontend/src/views/admin/AdminCurriculumListView.vue` (新規) — 一覧ビュー + draft 件数バッジ
  - `frontend/src/views/admin/AdminCurriculumEditView.vue` (新規) — 編集ビュー parent
  - `frontend/src/components/admin/CurriculumPhaseEditor.vue` (新規) — Phase 単位の編集 UI
  - `frontend/src/components/admin/CurriculumTaskEditor.vue` (新規) — Task 単位の編集 UI (debounced PUT)
  - `frontend/src/components/admin/SkillTagInput.vue` (新規) — タグ chip + add input
  - `frontend/src/router/admin.ts` にルート 2 件追加 (`admin-curriculum-list`, `admin-curriculum-edit`)
  - `frontend/src/layouts/AdminLayout.vue` の nav に「カリキュラム編集」リンク追加
- テスト: backend 新規 ≈25、frontend 新規 ≈11、E2E +1 件
- `docs/superpowers/specs/2026-06-1X-sprint-9-followups.md` に MED/LOW を切り出し
- README 更新 (Sprint 9 完了マーク + curriculum 編集の運用手順)

**含まない（後続スプリント）：**

- Phase / Task / Course の追加・削除・並び替え
- 編集履歴 / バージョン管理 (`curriculum_versions` テーブル)
- multi-worker 対応のキャッシュ無効化 (Redis pub/sub)
- embeddings の自動再生成 (publish 時の arq バックグラウンド)
- 編集中の楽観ロック (`updated_at` を ETag として活用)
- 専用 RBAC ロール (`is_curriculum_editor` フラグ等)
- システムプロンプト変更が in-flight chat に与える影響を抑える「セッション固定」モード

---

## ファイル構造（差分のみ）

```
edu/
├── README.md                                                              # Modify: Sprint 9 完了マーク + 運用手順
├── backend/
│   ├── app/
│   │   ├── api/admin/curriculum.py                                        # Create: 6 routes
│   │   ├── data/courses/
│   │   │   ├── __init__.py                                                # Modify: get_course を cache 経由に
│   │   │   └── runtime.py                                                 # Create: in-process cache
│   │   ├── models/
│   │   │   ├── curriculum_phase.py                                        # Create
│   │   │   ├── curriculum_task.py                                         # Create
│   │   │   └── __init__.py                                                # Modify: 2 model を登録
│   │   ├── schemas/admin_curriculum.py                                    # Create: 6 + 2 schema
│   │   ├── services/curriculum_edit.py                                    # Create
│   │   ├── config.py                                                      # Modify: rate limit 2 件追加
│   │   └── main.py                                                        # Modify: lifespan + router
│   ├── alembic/versions/
│   │   └── 20260613_<rev>_sprint9_curriculum_editing.py                   # Create
│   └── tests/
│       ├── conftest.py                                                    # Modify: 再 seed + reload + fixture
│       ├── test_models_sprint9.py                                         # Create (4 tests)
│       ├── test_curriculum_seed_migration.py                              # Create (3 tests)
│       ├── test_curriculum_cache.py                                       # Create (5 tests)
│       ├── test_curriculum_edit_service.py                                # Create (6 tests)
│       └── test_admin_curriculum_api.py                                   # Create (7 tests)
└── frontend/
    └── src/
        ├── types/admin_curriculum.ts                                      # Create
        ├── lib/api.ts                                                     # Modify: admin curriculum 6 メソッド
        ├── stores/admin_curriculum.ts                                     # Create
        ├── views/admin/
        │   ├── AdminCurriculumListView.vue                                # Create
        │   └── AdminCurriculumEditView.vue                                # Create
        ├── components/admin/
        │   ├── CurriculumPhaseEditor.vue                                  # Create
        │   ├── CurriculumTaskEditor.vue                                   # Create
        │   └── SkillTagInput.vue                                          # Create
        ├── router/admin.ts                                                # Modify: 2 ルート追加
        ├── layouts/AdminLayout.vue                                        # Modify: nav リンク
        ├── e2e/admin-curriculum.spec.ts                                   # Create
        └── __tests__/
            ├── admin_curriculum.store.spec.ts                             # Create (4 tests)
            ├── AdminCurriculumListView.spec.ts                            # Create (2 tests)
            ├── AdminCurriculumEditView.spec.ts                            # Create (3 tests)
            └── CurriculumTaskEditor.spec.ts                               # Create (2 tests)
```

---

## 共通の前提

- **作業ブランチ:** `feature/sprint-9`（main から派生、現 HEAD = `f389bd0`）
- **環境:** Docker Compose の `postgres` を起動。backend は `uv run uvicorn` でホスト起動可。
- **テスト DB:** `ai_tutor_test`。Sprint 9 マイグレーションは `Base.metadata.create_all` 経由でテストに反映される（Alembic は本番 DB のみ）。
- **既存テスト件数（ベースライン）:** backend 370 / frontend 83 / E2E 4
- **目標テスト件数:** backend **395** / frontend **94** / E2E **5**
- **コミット規約:** Sprint 1〜8 と同じ `feat|fix|test|chore|docs|refactor(scope): ...`。本スプリントの scope は `sprint-9`。
- **コマンド実行ディレクトリ:** 特記なき限り `/Volumes/Seagate3TB/projects/edu`。

### 既存スキーマ事実（subagent 暴走防止用 — そのまま転記）

- **`Course`** (`backend/app/models/course.py`): 列 `id, slug, title, description, sort_order, created_at`。固定 UUID: `ai-driven-dev=00000000-0000-4000-8000-000000000001`、`ai-era-se=00000000-0000-4000-8000-000000000002`
- **`Enrollment`** (`backend/app/models/enrollment.py`): 列 `id, user_id, course_id, status, enrolled_at`、UNIQUE (`user_id`, `course_id`)
- **`COURSE_REGISTRY`** (`backend/app/data/courses/__init__.py`): `dict[str, CourseData]`。`get_course(slug)`, `get_phases(slug)`, `get_phase(slug, phase_no)` をエクスポート
- **`CourseData`** (`backend/app/data/courses/types.py`): frozen dataclass、`id, slug, title, description, sort_order, phases`
- **`PhaseData`**: frozen dataclass、`phase, title, goal, tasks, system_prompt`
- **`TaskItem`**: frozen dataclass、`task_no, title, description, skill_tags, deliverable, week_label`
- **`ai_driven_dev.py`**: 4 phases × 3 tasks。Phase 1 例: title="開発環境の近代化", goal="AIツールを使いこなすための「土台」を固める"。task 1 例: title="Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成", skill_tags=("Git/GitHub",)
- **`ai_era_se.py`**: 4 phases (Phase 1=8 tasks, Phase 2/3/4 は 12+16+12 週)
- **最新 Alembic リビジョン:** `a1b2c3d4e5f6` (`20260611_..._sprint7_followups.py`)
- **既存 admin router 登録順** (`app/main.py:87-100`): health → courses → auth → curriculum → progress → submissions → chat → admin_users → admin_submissions → admin_comments → admin_notifications → admin_user_dashboard → me → me_dashboard

### 既存テスト fixture（`conftest.py`）

- `client`: `TestClient(app)`
- `_setup_db` (session-scoped, autouse): `Base.metadata.create_all` を 1 回実行
- `db_session`: 各テスト前に全テーブル TRUNCATE、COURSE_REGISTRY を `courses` テーブルに seed、`AsyncSession` を yield
- `default_course_id`: `ai-driven-dev` の固定 UUID
- `auth_user` / `admin_user` / `auth_token` / `admin_token` / `auth_client` / `admin_client`
- **Sprint 9 で `curriculum_phases` / `curriculum_tasks` も再 seed する必要あり**
- **Sprint 9 で各 test 前に `reload_from_db()` を呼ぶ必要あり (cache を test DB に合わせる)**

### CRITICAL ANTI-HALLUCINATION GUARDS（subagent 全 Task 共通）

Sprint 6 Task 4 で subagent が仕様外の書き換えを行った前科。各 Task の subagent プロンプトに以下を **必ず** 明記する:

1. **既存スキーマは上記「既存スキーマ事実」セクションを唯一の真実とせよ**。コード中で見えない属性は **存在しないと仮定**
2. **修正ファイル allowlist は本 Task の「Files:」セクションに列挙したもののみ**。それ以外は read のみ可、write は禁止
3. **各 Step 開始前に `git status` を実行**。allowlist 外の差分が出ていたら即停止して報告
4. **Sprint 9 では既存 service (`enrollment`, `submission`, `dashboard`, `recommendation`, `progress_summary`, `progress`) を変更しない**。Sprint 7 で `get_course()` 経由に集約済みなので変更不要
5. **Alembic migration の seed は `COURSE_REGISTRY` を import しない**。dict literal で値をコピペする (将来 registry 削除に備える)

---

## Task 0: ブランチ作成と環境確認

**Files:**
- なし（git のみ）

- [ ] **Step 1: feature ブランチを切る**

```bash
git checkout main
git pull --ff-only || true
git checkout -b feature/sprint-9
```

- [ ] **Step 2: バックエンド全件テストが現状で通ることを確認**

```bash
docker compose up -d postgres
sleep 5
cd backend && uv run pytest -q
```

Expected: `370 passed`。

- [ ] **Step 3: フロントテストとビルドが現状で通ることを確認**

```bash
cd ../frontend && npm run build && npm test -- --run
```

Expected: ビルド成功、`83 passed`。

- [ ] **Step 4: 開発 DB のマイグレーション状況を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && set -a && . ../.env && set +a && \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  uv run alembic current
```

Expected: 最新リビジョン `a1b2c3d4e5f6` (`20260611_..._sprint7_followups`)。

- [ ] **Step 5: E2E が現状通ることを確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  JWT_SECRET_KEY=test-secret ANTHROPIC_API_KEY=test-key \
  GRADING_ASYNC_ENABLED=false CLAUDE_STUB_MODE=true \
  RATE_LIMIT_ENABLED=false BCRYPT_ROUNDS=4 \
  CORS_ALLOW_ORIGINS=http://localhost:5173 \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 &
sleep 6
curl -s http://127.0.0.1:8001/healthz
cd /Volumes/Seagate3TB/projects/edu/frontend && \
  VITE_API_BASE_URL=http://127.0.0.1:8001 npx playwright test
# 終了後
lsof -ti:8001 | xargs -r kill
```

Expected: 4 passed (smoke 2 + dashboard 2)。

---

## Task 1: `CurriculumPhase` / `CurriculumTask` ORM モデル

**Files:**
- Create: `backend/app/models/curriculum_phase.py`
- Create: `backend/app/models/curriculum_task.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/tests/test_models_sprint9.py`

> **ANTI-HALLUCINATION:** 既存の `Course` モデルは触らない。FK は `courses(id)` ON DELETE RESTRICT で参照のみ。`InstructorComment` / `Notification` / その他既存テーブルにも触らない。

- [ ] **Step 1: failing test を追加**

`backend/tests/test_models_sprint9.py` を新規作成:

```python
"""Sprint 9 model tests — CurriculumPhase / CurriculumTask."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask


@pytest.mark.asyncio
async def test_curriculum_phase_unique_course_phase_no(db_session):
    c = Course(slug="x", title="X", sort_order=0)
    db_session.add(c)
    await db_session.flush()

    p = CurriculumPhase(
        course_id=c.id, phase_no=1,
        title="t", goal="g", system_prompt="s",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    assert p.id is not None

    dup = CurriculumPhase(
        course_id=c.id, phase_no=1,
        title="t2", goal="g2", system_prompt="s2",
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_curriculum_task_unique_phase_task_no(db_session):
    c = Course(slug="x", title="X", sort_order=0)
    db_session.add(c)
    await db_session.flush()
    p = CurriculumPhase(
        course_id=c.id, phase_no=1,
        title="t", goal="g", system_prompt="s",
    )
    db_session.add(p)
    await db_session.flush()

    t = CurriculumTask(
        phase_id=p.id, task_no=1,
        title="task", description="d", skill_tags=["A"],
    )
    db_session.add(t)
    await db_session.commit()

    dup = CurriculumTask(
        phase_id=p.id, task_no=1,
        title="task2", description="d2", skill_tags=["B"],
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_phase_delete_cascades_tasks(db_session):
    """ON DELETE CASCADE: phase が消えたら tasks も消える。"""
    c = Course(slug="x", title="X", sort_order=0)
    db_session.add(c)
    await db_session.flush()
    p = CurriculumPhase(
        course_id=c.id, phase_no=1,
        title="t", goal="g", system_prompt="s",
    )
    db_session.add(p)
    await db_session.flush()
    db_session.add(CurriculumTask(
        phase_id=p.id, task_no=1,
        title="task", description="d", skill_tags=[],
    ))
    await db_session.commit()

    await db_session.delete(p)
    await db_session.commit()
    rows = (await db_session.execute(select(CurriculumTask))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_curriculum_task_skill_tags_stores_list(db_session):
    """skill_tags は JSONB で list[str] のラウンドトリップが効くこと。"""
    c = Course(slug="x", title="X", sort_order=0)
    db_session.add(c)
    await db_session.flush()
    p = CurriculumPhase(
        course_id=c.id, phase_no=1,
        title="t", goal="g", system_prompt="s",
    )
    db_session.add(p)
    await db_session.flush()

    t = CurriculumTask(
        phase_id=p.id, task_no=1,
        title="task", description="d",
        skill_tags=["Git/GitHub", "API基礎"],
        deliverable="report.md", week_label="第1週",
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    assert t.skill_tags == ["Git/GitHub", "API基礎"]
    assert t.deliverable == "report.md"
    assert t.week_label == "第1週"
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_models_sprint9.py -q
```

Expected: 失敗 (`CurriculumPhase` / `CurriculumTask` モジュール未存在)。

- [ ] **Step 3: `CurriculumPhase` モデルを作成**

`backend/app/models/curriculum_phase.py` を新規作成:

```python
"""Sprint 9 — editable per-phase curriculum row (published + draft)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CurriculumPhase(Base):
    """Curriculum の Phase 1 行。published 列と draft_* 列の二段保持。

    Sprint 9: ai-driven-dev / ai-era-se の Python レジストリは初回 seed として
    Alembic migration 内で写し込まれる。以後の編集はこのテーブル経由のみ。
    `draft_*` 列は NULL = 未編集、非 NULL = 次 publish 候補。
    """

    __tablename__ = "curriculum_phases"
    __table_args__ = (
        UniqueConstraint(
            "course_id", "phase_no", name="uq_curriculum_phases_course_phase_no"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    phase_no: Mapped[int] = mapped_column(Integer, nullable=False)

    # Published values (runtime cache が読む値)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Draft overlay (NULL = 未編集)
    draft_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
```

- [ ] **Step 4: `CurriculumTask` モデルを作成**

`backend/app/models/curriculum_task.py` を新規作成:

```python
"""Sprint 9 — editable per-task curriculum row (published + draft)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CurriculumTask(Base):
    """Curriculum の Task 1 行。published 列と draft_* 列の二段保持。

    Sprint 9: `skill_tags` は JSONB の `list[str]` で永続化。`deliverable`
    と `week_label` は NULL 可。`draft_deliverable=""` / `draft_week_label=""`
    は「明示的に空にしたい」を表すための sentinel として運用 (NULL は
    "未編集" の意味で予約)。
    """

    __tablename__ = "curriculum_tasks"
    __table_args__ = (
        UniqueConstraint(
            "phase_id", "task_no", name="uq_curriculum_tasks_phase_task_no"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    phase_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_phases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_no: Mapped[int] = mapped_column(Integer, nullable=False)

    # Published values
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    skill_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    deliverable: Mapped[str | None] = mapped_column(Text, nullable=True)
    week_label: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Draft overlay
    draft_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_skill_tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    draft_deliverable: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_week_label: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
```

- [ ] **Step 5: `models/__init__.py` で両モデルを登録**

`backend/app/models/__init__.py` を読んで、既存の import 行と並べてアルファベット順に追加:

```python
from app.models.curriculum_phase import CurriculumPhase  # noqa: F401
from app.models.curriculum_task import CurriculumTask  # noqa: F401
```

- [ ] **Step 6: テスト緑を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_models_sprint9.py -q
```

Expected: `4 passed`。

- [ ] **Step 7: 全テスト緑（既存 conftest はまだ curriculum_phases を seed しないので、これらモデル単体テストのみ通る前提。既存テストは Task 10 まで影響しない）**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q 2>&1 | tail -5
```

Expected: `374 passed`（370 + 4 新規）。

- [ ] **Step 8: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/models/curriculum_phase.py backend/app/models/curriculum_task.py backend/app/models/__init__.py backend/tests/test_models_sprint9.py
git commit -m "feat(sprint-9): add CurriculumPhase + CurriculumTask ORM models"
```

---

## Task 2: Alembic マイグレーション + 初回 seed (dict literal)

**Files:**
- Create: `backend/alembic/versions/20260613_<rev>_sprint9_curriculum_editing.py`
- Create: `backend/tests/test_curriculum_seed_migration.py`

> **ANTI-HALLUCINATION:** seed 値は `COURSE_REGISTRY` を import せず、dict literal でコピペする。値は migration 作成時点でフリーズし、将来 `app/data/courses/*.py` を変更しても migration の挙動は不変。docstring に明記。

- [ ] **Step 1: マイグレーション skeleton を生成**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && set -a && . ../.env && set +a && \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  uv run alembic revision -m "sprint9_curriculum_editing"
```

生成ファイル: `backend/alembic/versions/20260613_<rev>_sprint9_curriculum_editing.py`。

- [ ] **Step 2: マイグレーション本体を手書き**

生成ファイルの `upgrade()` と `downgrade()` を以下に置き換える (`revision` 自動填め値は保持、`down_revision = 'a1b2c3d4e5f6'` を確認):

```python
"""sprint9_curriculum_editing

Revision ID: <auto>
Revises: a1b2c3d4e5f6
Create Date: <auto>

Sprint 9: introduce curriculum_phases + curriculum_tasks tables for
admin-editable curriculum content. Each row holds both the published
column and a `draft_*` overlay (NULL = unedited).

Initial seed is written by **literal dict copy** of the
`app/data/courses/{ai_driven_dev,ai_era_se}.py` state at migration
authoring time. Doing the copy here (instead of importing
COURSE_REGISTRY) freezes the seed so future Python registry edits do
NOT retroactively change this migration's behaviour — important for
`alembic downgrade -1 && upgrade head` reproducibility on production.
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = '<auto>'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


AI_DRIVEN_DEV_UUID = uuid.UUID("00000000-0000-4000-8000-000000000001")
AI_ERA_SE_UUID = uuid.UUID("00000000-0000-4000-8000-000000000002")


# ---------------------------------------------------------------------------
# Seed payload — frozen dict literal copy of app/data/courses/*.py state at
# migration authoring time. DO NOT re-import COURSE_REGISTRY here. See the
# module docstring above.
# ---------------------------------------------------------------------------

_AI_DRIVEN_DEV_PHASES = [
    {
        "phase_no": 1,
        "title": "開発環境の近代化",
        "goal": "AIツールを使いこなすための「土台」を固める",
        "system_prompt": (
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
        "tasks": [
            {
                "task_no": 1,
                "title": "Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成",
                "description": "Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成",
                "skill_tags": ["Git/GitHub"],
                "deliverable": None,
                "week_label": None,
            },
            {
                "task_no": 2,
                "title": "VSCode拡張（GitLens・REST Client・GitHub Copilot）の導入と動作確認",
                "description": "VSCode拡張（GitLens・REST Client・GitHub Copilot）の導入と動作確認",
                "skill_tags": ["開発環境"],
                "deliverable": None,
                "week_label": None,
            },
            {
                "task_no": 3,
                "title": "curlでREST APIを叩き、JSONレスポンス構造をまとめる",
                "description": "curlでREST APIを叩き、JSONレスポンス構造をまとめる",
                "skill_tags": ["API基礎"],
                "deliverable": None,
                "week_label": None,
            },
        ],
    },
    # NOTE: Phase 2-4 を ai_driven_dev.py からコピペする。タスク数は各 3。
    # 本 plan では Phase 2-4 の literal を完全に書き出すと migration が
    # 数百行になるため、実装時に下記コメントの指示に従って `ai_driven_dev.py`
    # の現値をそのまま埋める。
    # FILL: Phase 2, 3, 4 を ai_driven_dev.py から dict literal でコピペ
]

_AI_ERA_SE_PHASES = [
    # FILL: Phase 1-4 を ai_era_se.py から dict literal でコピペ
    # Phase 1 = 8 tasks (Git 等)、Phase 2 = 12 weeks、Phase 3 = 16 weeks、Phase 4 = 12 weeks
]


_SEED_PAYLOAD = [
    (AI_DRIVEN_DEV_UUID, _AI_DRIVEN_DEV_PHASES),
    (AI_ERA_SE_UUID, _AI_ERA_SE_PHASES),
]


def upgrade() -> None:
    # 1. curriculum_phases
    op.create_table(
        "curriculum_phases",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("phase_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("draft_title", sa.Text(), nullable=True),
        sa.Column("draft_goal", sa.Text(), nullable=True),
        sa.Column("draft_system_prompt", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "course_id", "phase_no", name="uq_curriculum_phases_course_phase_no"
        ),
    )
    op.create_index(
        "ix_curriculum_phases_course_id", "curriculum_phases", ["course_id"]
    )

    # 2. curriculum_tasks
    op.create_table(
        "curriculum_tasks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "phase_id",
            sa.UUID(),
            sa.ForeignKey("curriculum_phases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("skill_tags", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("deliverable", sa.Text(), nullable=True),
        sa.Column("week_label", sa.Text(), nullable=True),
        sa.Column("draft_title", sa.Text(), nullable=True),
        sa.Column("draft_description", sa.Text(), nullable=True),
        sa.Column(
            "draft_skill_tags", sa.dialects.postgresql.JSONB(), nullable=True
        ),
        sa.Column("draft_deliverable", sa.Text(), nullable=True),
        sa.Column("draft_week_label", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "phase_id", "task_no", name="uq_curriculum_tasks_phase_task_no"
        ),
    )
    op.create_index(
        "ix_curriculum_tasks_phase_id", "curriculum_tasks", ["phase_id"]
    )

    # 3. seed (frozen dict literal copy)
    for course_id, phases in _SEED_PAYLOAD:
        for phase in phases:
            phase_id = uuid.uuid4()
            op.execute(
                sa.text(
                    "INSERT INTO curriculum_phases "
                    "(id, course_id, phase_no, title, goal, system_prompt) "
                    "VALUES (:id, :cid, :pn, :t, :g, :sp)"
                ).bindparams(
                    id=phase_id,
                    cid=course_id,
                    pn=phase["phase_no"],
                    t=phase["title"],
                    g=phase["goal"],
                    sp=phase["system_prompt"],
                )
            )
            for task in phase["tasks"]:
                op.execute(
                    sa.text(
                        "INSERT INTO curriculum_tasks "
                        "(id, phase_id, task_no, title, description, "
                        " skill_tags, deliverable, week_label) "
                        "VALUES (:id, :pid, :tn, :t, :d, "
                        "        CAST(:st AS JSONB), :del, :wl)"
                    ).bindparams(
                        id=uuid.uuid4(),
                        pid=phase_id,
                        tn=task["task_no"],
                        t=task["title"],
                        d=task["description"],
                        st=__import__("json").dumps(
                            task["skill_tags"], ensure_ascii=False
                        ),
                        del_=task["deliverable"],
                        wl=task["week_label"],
                    ).bindparams(sa.bindparam("del", task["deliverable"]))
                )


def downgrade() -> None:
    op.drop_index("ix_curriculum_tasks_phase_id", table_name="curriculum_tasks")
    op.drop_table("curriculum_tasks")
    op.drop_index("ix_curriculum_phases_course_id", table_name="curriculum_phases")
    op.drop_table("curriculum_phases")
```

**実装時の注意:**
- `_AI_DRIVEN_DEV_PHASES` の Phase 2/3/4 と `_AI_ERA_SE_PHASES` の Phase 1-4 は **手動で `app/data/courses/{ai_driven_dev,ai_era_se}.py` を開いて値をコピペする**。タスクの `title`, `description`, `skill_tags` (tuple → list 変換)、`deliverable`、`week_label` を漏れなく転記。
- INSERT 時の `del` パラメータ名は Python 予約語と衝突するので `:del_` にリネームする手もあるが、`sa.bindparam` で名前を指定するパターンで回避。実装時は `deliverable_val=...` 等にリネームしてもよい。
- 各 task の `skill_tags` は dict → JSON 文字列に変換し、`CAST(... AS JSONB)` で挿入。

- [ ] **Step 3: 構造テストを追加**

`backend/tests/test_curriculum_seed_migration.py` を新規作成:

```python
"""Sprint 9 — Alembic structural invariants for curriculum seed."""

import importlib.util
import pathlib
import uuid


def _load_migration():
    versions_dir = pathlib.Path(__file__).parent.parent / "alembic" / "versions"
    candidates = list(versions_dir.glob("*sprint9_curriculum_editing*.py"))
    assert len(candidates) == 1, f"expected 1 sprint9 migration, got {candidates}"
    spec = importlib.util.spec_from_file_location(
        "sprint9_migration", candidates[0]
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sprint9_migration_chains_from_sprint7_followup():
    m = _load_migration()
    assert m.down_revision == "a1b2c3d4e5f6"


def test_sprint9_migration_uses_fixed_uuids():
    m = _load_migration()
    assert m.AI_DRIVEN_DEV_UUID == uuid.UUID(
        "00000000-0000-4000-8000-000000000001"
    )
    assert m.AI_ERA_SE_UUID == uuid.UUID("00000000-0000-4000-8000-000000000002")


def test_sprint9_migration_seed_does_not_import_registry():
    """seed payload は COURSE_REGISTRY を import せず、dict literal で
    凍結されている (将来 registry を変更しても migration 挙動不変)。"""
    m = _load_migration()
    import inspect
    source = inspect.getsource(m)
    assert "from app.data.courses" not in source
    assert "COURSE_REGISTRY" not in source
```

- [ ] **Step 4: 構造テスト緑を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_curriculum_seed_migration.py -q
```

Expected: `3 passed`。

- [ ] **Step 5: マイグレーションを開発 DB に適用**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && set -a && . ../.env && set +a && \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  uv run alembic upgrade head
```

Expected: `Running upgrade a1b2c3d4e5f6 -> <rev>, sprint9_curriculum_editing`。

- [ ] **Step 6: 開発 DB で seed 内容を確認**

```bash
docker compose exec postgres psql -U postgres -d ai_tutor -c "\dt curriculum_phases curriculum_tasks"
docker compose exec postgres psql -U postgres -d ai_tutor \
  -c "SELECT course_id, phase_no, title FROM curriculum_phases ORDER BY course_id, phase_no"
docker compose exec postgres psql -U postgres -d ai_tutor \
  -c "SELECT phase_id, task_no, title FROM curriculum_tasks ORDER BY phase_id, task_no LIMIT 10"
```

Expected: 4 (ai-driven-dev) + 4 (ai-era-se) = 8 phases、ai-driven-dev=12 tasks + ai-era-se=8+12+16+12=48 tasks。

- [ ] **Step 7: downgrade を検証**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && set -a && . ../.env && set +a && \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  uv run alembic downgrade -1 && \
  uv run alembic upgrade head
```

Expected: 両方成功、テーブルが drop → 再生成される。

- [ ] **Step 8: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/alembic/versions/*sprint9_curriculum_editing.py backend/tests/test_curriculum_seed_migration.py
git commit -m "feat(sprint-9): Alembic migration with frozen dict-literal seed"
```

---

## Task 3: `app/data/courses/runtime.py` (process-local cache)

**Files:**
- Create: `backend/app/data/courses/runtime.py`
- Create: `backend/tests/test_curriculum_cache.py`

> **ANTI-HALLUCINATION:** 既存の `__init__.py` には触らない (Task 4 で扱う)。`CourseData` / `PhaseData` / `TaskItem` の型定義 (`types.py`) も触らない。

- [ ] **Step 1: failing test を追加**

`backend/tests/test_curriculum_cache.py` を新規作成:

```python
"""Sprint 9 — process-local curriculum cache tests."""

import uuid

import pytest

from app.data.courses import runtime
from app.data.courses.types import CourseData, PhaseData, TaskItem


@pytest.mark.asyncio
async def test_reload_from_db_populates_cache(db_session, seed_curriculum):
    """seed_curriculum fixture (Task 10 で追加) が curriculum_phases /
    curriculum_tasks を埋めた後、reload_from_db で cache が満たされる。"""
    runtime._CACHE.clear()
    await runtime.reload_from_db(db_session)
    course = runtime.get_cached_course("ai-driven-dev")
    assert isinstance(course, CourseData)
    assert course.slug == "ai-driven-dev"
    assert len(course.phases) == 4
    p1 = course.phases[0]
    assert isinstance(p1, PhaseData)
    assert p1.phase == 1
    assert len(p1.tasks) == 3
    t1 = p1.tasks[0]
    assert isinstance(t1, TaskItem)
    assert "Git" in t1.title


@pytest.mark.asyncio
async def test_get_cached_course_raises_on_unknown_slug(
    db_session, seed_curriculum
):
    from app.data.courses import CourseNotFoundError

    runtime._CACHE.clear()
    await runtime.reload_from_db(db_session)
    with pytest.raises(CourseNotFoundError):
        runtime.get_cached_course("nope")


@pytest.mark.asyncio
async def test_reload_course_updates_single_course_only(
    db_session, seed_curriculum
):
    """publish 後の差し替え: 1 course だけ rebuild、他は不変。"""
    from app.models.curriculum_phase import CurriculumPhase
    from sqlalchemy import select, update

    runtime._CACHE.clear()
    await runtime.reload_from_db(db_session)
    before_se = runtime.get_cached_course("ai-era-se")

    # ai-driven-dev の Phase 1 title を直接更新 (publish 相当)
    stmt = update(CurriculumPhase).where(
        CurriculumPhase.phase_no == 1
    ).values(title="X 更新後")
    # course_id で絞り込み (ai-driven-dev のみ更新)
    from app.models.course import Course
    dev_id = (await db_session.execute(
        select(Course.id).where(Course.slug == "ai-driven-dev")
    )).scalar_one()
    stmt = update(CurriculumPhase).where(
        CurriculumPhase.course_id == dev_id, CurriculumPhase.phase_no == 1
    ).values(title="X 更新後")
    await db_session.execute(stmt)
    await db_session.commit()

    await runtime.reload_course(db_session, "ai-driven-dev")
    after_dev = runtime.get_cached_course("ai-driven-dev")
    after_se = runtime.get_cached_course("ai-era-se")
    assert after_dev.phases[0].title == "X 更新後"
    assert after_se is before_se  # same object → unchanged


@pytest.mark.asyncio
async def test_cache_returns_published_not_draft(db_session, seed_curriculum):
    """draft_title が入っていても、cache (= runtime) は published 値を返す。"""
    from app.models.curriculum_phase import CurriculumPhase
    from sqlalchemy import select, update
    from app.models.course import Course

    dev_id = (await db_session.execute(
        select(Course.id).where(Course.slug == "ai-driven-dev")
    )).scalar_one()
    await db_session.execute(
        update(CurriculumPhase).where(
            CurriculumPhase.course_id == dev_id,
            CurriculumPhase.phase_no == 1,
        ).values(draft_title="DRAFT ONLY")
    )
    await db_session.commit()

    runtime._CACHE.clear()
    await runtime.reload_from_db(db_session)
    course = runtime.get_cached_course("ai-driven-dev")
    assert course.phases[0].title != "DRAFT ONLY"


@pytest.mark.asyncio
async def test_reload_from_db_on_empty_table_raises(db_session):
    """0 行検出時はエラー (silent fallback ではなく、明示的に起動失敗)。"""
    from sqlalchemy import delete
    from app.models.curriculum_phase import CurriculumPhase
    from app.models.curriculum_task import CurriculumTask

    await db_session.execute(delete(CurriculumTask))
    await db_session.execute(delete(CurriculumPhase))
    await db_session.commit()

    runtime._CACHE.clear()
    with pytest.raises(RuntimeError, match="curriculum_phases is empty"):
        await runtime.reload_from_db(db_session)
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_curriculum_cache.py -q
```

Expected: ImportError on `app.data.courses.runtime` または `seed_curriculum` fixture 未定義。

- [ ] **Step 3: `runtime.py` を作成**

`backend/app/data/courses/runtime.py` を新規作成:

```python
"""Sprint 9 — process-local in-memory cache of published curriculum.

The cache is populated from the DB at app startup (`lifespan` in
`app/main.py`) and refreshed after `POST /api/admin/curriculum/{slug}/publish`.

This lets the existing synchronous `get_course(slug)` API stay
unchanged while moving the source of truth from the Python registry to
the DB.

Multi-worker note (follow-up): with N uvicorn workers each cache is
process-local, so `publish` triggers an inconsistency window until each
worker observes the next reload. For Sprint 9 the dev / docker setup
runs a single worker; future scaling needs a Redis pub/sub invalidation
broadcast.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.data.courses.types import CourseData, PhaseData, TaskItem
from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask


# process-local cache. Cleared by tests via `_CACHE.clear()`.
_CACHE: dict[str, CourseData] = {}


def _build_task(row: CurriculumTask) -> TaskItem:
    return TaskItem(
        task_no=row.task_no,
        title=row.title,
        description=row.description,
        skill_tags=tuple(row.skill_tags or ()),
        deliverable=row.deliverable,
        week_label=row.week_label,
    )


def _build_phase(
    phase_row: CurriculumPhase, task_rows: list[CurriculumTask]
) -> PhaseData:
    tasks = tuple(
        _build_task(t)
        for t in sorted(task_rows, key=lambda r: r.task_no)
    )
    return PhaseData(
        phase=phase_row.phase_no,
        title=phase_row.title,
        goal=phase_row.goal,
        tasks=tasks,
        system_prompt=phase_row.system_prompt,
    )


def _build_course(course: Course, phase_rows: list[CurriculumPhase]) -> CourseData:
    phases = tuple(
        _build_phase(p, list(p.tasks))  # p.tasks は selectinload で埋まる前提
        for p in sorted(phase_rows, key=lambda r: r.phase_no)
    )
    return CourseData(
        id=course.id,
        slug=course.slug,
        title=course.title,
        description=course.description or "",
        sort_order=course.sort_order,
        phases=phases,
    )


async def _load_course_phases(
    db: AsyncSession, course_id: uuid.UUID
) -> list[CurriculumPhase]:
    stmt = (
        select(CurriculumPhase)
        .where(CurriculumPhase.course_id == course_id)
        .options(selectinload(CurriculumPhase.tasks))
    )
    return list((await db.execute(stmt)).scalars().all())


async def reload_from_db(db: AsyncSession) -> None:
    """全 course の CourseData を再構築して `_CACHE` を置き換える。

    Sprint 9 / 起動時: app.main.lifespan が 1 度呼ぶ。0 行は明示的なエラー。
    """
    courses = list((await db.execute(select(Course))).scalars().all())
    if not courses:
        raise RuntimeError(
            "curriculum cache: courses table is empty — "
            "alembic upgrade head が未実行の可能性"
        )

    new_cache: dict[str, CourseData] = {}
    for course in courses:
        phase_rows = await _load_course_phases(db, course.id)
        if not phase_rows:
            raise RuntimeError(
                f"curriculum_phases is empty for course {course.slug!r} — "
                "alembic seed が未実行の可能性"
            )
        new_cache[course.slug] = _build_course(course, phase_rows)

    _CACHE.clear()
    _CACHE.update(new_cache)


async def reload_course(db: AsyncSession, slug: str) -> None:
    """1 course だけを再構築して cache を差し替える (publish 後に呼ぶ)。"""
    course = (
        await db.execute(select(Course).where(Course.slug == slug))
    ).scalar_one_or_none()
    if course is None:
        from app.data.courses import CourseNotFoundError
        raise CourseNotFoundError(slug)
    phase_rows = await _load_course_phases(db, course.id)
    _CACHE[slug] = _build_course(course, phase_rows)


def get_cached_course(slug: str) -> CourseData:
    """同期 API。`get_course(slug)` から呼ばれる。

    cache miss は CourseNotFoundError。reload 漏れの早期検出を狙う。
    """
    from app.data.courses import CourseNotFoundError

    try:
        return _CACHE[slug]
    except KeyError:
        raise CourseNotFoundError(slug) from None
```

`CurriculumPhase` に `tasks` relationship が必要。一旦 `_load_course_phases` は手動 join で書き直す:

```python
async def _load_course_phases(
    db: AsyncSession, course_id: uuid.UUID
) -> list[tuple[CurriculumPhase, list[CurriculumTask]]]:
    phases = list((await db.execute(
        select(CurriculumPhase).where(CurriculumPhase.course_id == course_id)
    )).scalars().all())
    if not phases:
        return []
    phase_ids = [p.id for p in phases]
    tasks = list((await db.execute(
        select(CurriculumTask).where(CurriculumTask.phase_id.in_(phase_ids))
    )).scalars().all())
    by_phase: dict[uuid.UUID, list[CurriculumTask]] = {pid: [] for pid in phase_ids}
    for t in tasks:
        by_phase[t.phase_id].append(t)
    return [(p, by_phase[p.id]) for p in phases]
```

そして `_build_course` を以下に変更:

```python
def _build_course(
    course: Course, pairs: list[tuple[CurriculumPhase, list[CurriculumTask]]]
) -> CourseData:
    phases = tuple(
        _build_phase(p, t)
        for p, t in sorted(pairs, key=lambda x: x[0].phase_no)
    )
    return CourseData(
        id=course.id,
        slug=course.slug,
        title=course.title,
        description=course.description or "",
        sort_order=course.sort_order,
        phases=phases,
    )
```

`reload_from_db` / `reload_course` 内の `phase_rows` 取得を `_load_course_phases` のペア戻り値に合わせて修正。

- [ ] **Step 4: テストはまだ通らない (conftest の seed_curriculum fixture が未追加)。後続 Task 10 で conftest を改修したあとに再実行する**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_curriculum_cache.py -q 2>&1 | tail -3
```

Expected: failed / fixture not found。これは Task 10 まで放置。

- [ ] **Step 5: Commit (red commit を許容)**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/data/courses/runtime.py backend/tests/test_curriculum_cache.py
git commit -m "feat(sprint-9): process-local curriculum cache (red until Task 10)"
```

---

## Task 4: `app/data/courses/__init__.py` の `get_course` を cache 経由に rewire

**Files:**
- Modify: `backend/app/data/courses/__init__.py`

> **ANTI-HALLUCINATION:** `types.py` / `ai_driven_dev.py` / `ai_era_se.py` は触らない。`get_course()` の同期 API シグネチャを保持。`COURSE_REGISTRY` を legacy alias として cache の dict view に置き換える。

- [ ] **Step 1: 既存ファイルを読む**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && cat app/data/courses/__init__.py
```

`COURSE_REGISTRY`, `DEFAULT_COURSE_SLUG`, `CourseNotFoundError`, `PhaseNotFoundError`, `get_course`, `get_phases`, `get_phase` のエクスポートがあることを確認。

- [ ] **Step 2: `get_course` を cache 経由に rewire**

`backend/app/data/courses/__init__.py` を以下に置き換える:

```python
"""Sprint 7 — course registry. Sprint 9 — runtime cache rewire.

Public API:
  COURSE_REGISTRY: dict[slug, CourseData]   — legacy alias for the cache
  DEFAULT_COURSE_SLUG: 'ai-driven-dev'
  get_course(slug) -> CourseData             — cache 経由
  get_phases(slug) -> tuple[PhaseData, ...]
  get_phase(slug, phase_no) -> PhaseData
  CourseNotFoundError / PhaseNotFoundError

Sprint 9 後の挙動:
- `get_course()` は in-memory cache (`runtime._CACHE`) を読む。
- cache は app 起動時に `runtime.reload_from_db(db)` が満たす。
- 編集 → publish のサイクルは `runtime.reload_course(db, slug)` で 1 course
  分の cache だけを差し替える。
- 既存 `ai_driven_dev.py` / `ai_era_se.py` は Alembic seed のドキュメント
  および test fallback 用に残す。本番 runtime は読まない。
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


# `COURSE_REGISTRY` is a backward-compatible alias kept for tests that
# still iterate over the python-side seed dict. Sprint 9 runtime code
# reads from `runtime._CACHE` via `get_course()`; this dict is NOT a
# source of truth at runtime.
COURSE_REGISTRY: dict[str, CourseData] = {
    AI_DRIVEN_DEV_COURSE.slug: AI_DRIVEN_DEV_COURSE,
    AI_ERA_SE_COURSE.slug: AI_ERA_SE_COURSE,
}


def get_course(slug: str) -> CourseData:
    """Cache-first lookup. Sprint 9 routes/services hit this via the cache.

    Test convenience: if the cache is empty (no `reload_from_db` was
    called — common for pure-unit tests that don't go through lifespan),
    fall back to `COURSE_REGISTRY`. Integration tests that exercise edit
    semantics must call `runtime.reload_from_db(db)` explicitly so they
    see the DB state, not the python literal.
    """
    from app.data.courses import runtime

    if runtime._CACHE:
        return runtime.get_cached_course(slug)
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

- [ ] **Step 3: 既存テストが緑であることを確認 (cache が空のときは registry fallback で動く)**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q 2>&1 | tail -5
```

Expected: `377 passed` (370 + 7 = Task 1 の 4 + Task 2 の 3)。Task 3 の cache test は seed_curriculum fixture 未追加で fail のままだが、それは Task 10 まで pending として許容。

- [ ] **Step 4: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/data/courses/__init__.py
git commit -m "feat(sprint-9): rewire get_course() to runtime cache with registry fallback"
```

---

## Task 5: `app/main.py` lifespan に `reload_from_db` を組み込み

**Files:**
- Modify: `backend/app/main.py`

> **ANTI-HALLUCINATION:** 既存の lifespan は `init_grading_pool` / `close_grading_pool` を含む。これらの呼び出し順序を壊さない。`reload_from_db` は arq init より前または後どちらでも実害なし。本 plan では arq init の直後・yield の前に挟む (起動時点で arq pool / curriculum cache の両方が準備済になる)。

- [ ] **Step 1: 既存 lifespan を確認**

```bash
grep -n "lifespan\|init_grading_pool\|close_grading_pool" backend/app/main.py
```

`@asynccontextmanager async def lifespan(app)` に `await init_grading_pool()` → `yield` → `await close_grading_pool()` の順序があることを確認。

- [ ] **Step 2: lifespan 修正**

`backend/app/main.py` の `lifespan` を以下に置き換える:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_grading_pool()
    # Sprint 9: populate the curriculum cache from DB. 0 行のときは
    # 明示的なエラーで起動を失敗させ、Alembic seed 未実行を可視化。
    from app.data.courses.runtime import reload_from_db
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        await reload_from_db(db)

    yield
    await close_grading_pool()
```

- [ ] **Step 3: app 起動確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  JWT_SECRET_KEY=test-secret ANTHROPIC_API_KEY=test-key \
  GRADING_ASYNC_ENABLED=false RATE_LIMIT_ENABLED=false BCRYPT_ROUNDS=4 \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 &
sleep 6
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8001/healthz
lsof -ti:8001 | xargs -r kill
```

Expected: `200` (lifespan が無事に curriculum を読めた)。

- [ ] **Step 4: 全テスト緑を維持していることを確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q 2>&1 | tail -5
```

Expected: `377 passed` (Task 4 と同じ)。

- [ ] **Step 5: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/main.py
git commit -m "feat(sprint-9): lifespan loads curriculum cache from DB on startup"
```

---

## Task 6: `app/schemas/admin_curriculum.py` (6 output + 2 request)

**Files:**
- Create: `backend/app/schemas/admin_curriculum.py`

> **ANTI-HALLUCINATION:** バリデーション値は spec の固定値: title=200/description=2000/system_prompt=8000/goal=500、skill_tags 配列長 ≤ 10、各要素長 ≤ 50、deliverable/week_label は 0〜200 文字 (空文字 OK)。

- [ ] **Step 1: schemas を作成**

`backend/app/schemas/admin_curriculum.py` を新規作成:

```python
"""Sprint 9 — admin curriculum editing DTOs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Output DTOs
# ---------------------------------------------------------------------------


class AdminCurriculumCourseSummary(BaseModel):
    """`/api/admin/curriculum/` (一覧) の 1 row。"""

    slug: str
    title: str
    pending_draft_count: int


class AdminCurriculumCourseList(BaseModel):
    items: list[AdminCurriculumCourseSummary]


class AdminTaskEditOut(BaseModel):
    """1 task 分の published + draft 両状態。"""

    task_no: int
    title: str
    description: str
    skill_tags: list[str]
    deliverable: str | None
    week_label: str | None
    draft_title: str | None
    draft_description: str | None
    draft_skill_tags: list[str] | None
    draft_deliverable: str | None
    draft_week_label: str | None
    updated_at: datetime


class AdminPhaseEditOut(BaseModel):
    """1 phase 分の published + draft 両状態 + tasks."""

    phase_no: int
    title: str
    goal: str
    system_prompt: str
    draft_title: str | None
    draft_goal: str | None
    draft_system_prompt: str | None
    tasks: list[AdminTaskEditOut]
    updated_at: datetime


class AdminCurriculumCourseDetail(BaseModel):
    """`GET /api/admin/curriculum/{slug}` のレスポンス。"""

    slug: str
    title: str
    phases: list[AdminPhaseEditOut]


class AdminCurriculumPublishOut(BaseModel):
    slug: str
    published_phase_count: int
    published_task_count: int
    published_at: datetime


# ---------------------------------------------------------------------------
# Request DTOs — exclude_unset セマンティクス用に全フィールド Optional
# ---------------------------------------------------------------------------


class AdminPhaseUpdateRequest(BaseModel):
    """PUT body — フィールド省略 = 変更なし、明示 None = draft クリア、
    明示値 = draft 設定。route 側で `model_dump(exclude_unset=True)` を取る。
    """

    title: str | None = Field(default=None, max_length=200)
    goal: str | None = Field(default=None, max_length=500)
    system_prompt: str | None = Field(default=None, max_length=8000)


class AdminTaskUpdateRequest(BaseModel):
    """PUT body for task draft."""

    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    skill_tags: list[str] | None = Field(default=None, max_length=10)
    deliverable: str | None = Field(default=None, max_length=200)
    week_label: str | None = Field(default=None, max_length=200)

    def normalized_skill_tags(self) -> list[str] | None:
        """順序維持の dedup + 各要素長 50 チェック。

        route が `model_dump(exclude_unset=True)` の後にこれを呼ぶ運用 (タグ
        フィールド省略時は None、明示空 list は []、値ありは dedup 後)。
        """
        if self.skill_tags is None:
            return None
        seen: set[str] = set()
        out: list[str] = []
        for raw in self.skill_tags:
            t = raw.strip()
            if not t or len(t) > 50:
                continue
            if t in seen:
                continue
            seen.add(t)
            out.append(t)
        return out
```

- [ ] **Step 2: import 確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run python -c "from app.schemas import admin_curriculum; print('ok')"
```

Expected: `ok`。

- [ ] **Step 3: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/schemas/admin_curriculum.py
git commit -m "feat(sprint-9): admin_curriculum schemas (6 output + 2 request)"
```

---

## Task 7: `app/services/curriculum_edit.py` (draft 編集 + publish + discard)

**Files:**
- Create: `backend/app/services/curriculum_edit.py`
- Create: `backend/tests/test_curriculum_edit_service.py`

> **ANTI-HALLUCINATION:** Sprint 9 では既存 service ファイルを一切触らない。`curriculum_edit.py` 単体で publish 完了時の `runtime.reload_course(db, slug)` 呼び出しまで担当する。`exclude_unset` セマンティクスは「dict 内に key があるかどうか」で判定 (Pydantic `model_dump(exclude_unset=True)` の結果を受け取る前提)。

- [ ] **Step 1: failing test を追加**

`backend/tests/test_curriculum_edit_service.py` を新規作成:

```python
"""Sprint 9 — curriculum_edit service unit tests."""

import pytest
from sqlalchemy import select

from app.data.courses import runtime
from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask
from app.services.curriculum_edit import (
    PhaseNotFoundError,
    TaskNotFoundError,
    discard_drafts,
    publish_course,
    put_phase_draft,
    put_task_draft,
)


@pytest.mark.asyncio
async def test_put_phase_draft_sets_specified_fields_only(
    db_session, seed_curriculum
):
    """field 省略 (key not in payload) = 変更なし、明示値 = draft 設定。"""
    await put_phase_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        payload={"title": "新しい Phase 1 タイトル"},
    )
    await db_session.commit()

    dev_id = (await db_session.execute(
        select(Course.id).where(Course.slug == "ai-driven-dev")
    )).scalar_one()
    row = (await db_session.execute(
        select(CurriculumPhase).where(
            CurriculumPhase.course_id == dev_id,
            CurriculumPhase.phase_no == 1,
        )
    )).scalar_one()
    assert row.draft_title == "新しい Phase 1 タイトル"
    assert row.draft_goal is None  # 省略 → 変更なし


@pytest.mark.asyncio
async def test_put_phase_draft_none_clears_draft(db_session, seed_curriculum):
    """payload に明示 None を入れると draft をクリア。"""
    await put_phase_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        payload={"title": "draft"},
    )
    await db_session.commit()
    await put_phase_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        payload={"title": None},
    )
    await db_session.commit()

    dev_id = (await db_session.execute(
        select(Course.id).where(Course.slug == "ai-driven-dev")
    )).scalar_one()
    row = (await db_session.execute(
        select(CurriculumPhase).where(
            CurriculumPhase.course_id == dev_id,
            CurriculumPhase.phase_no == 1,
        )
    )).scalar_one()
    assert row.draft_title is None


@pytest.mark.asyncio
async def test_put_phase_draft_404_on_unknown_phase(
    db_session, seed_curriculum
):
    with pytest.raises(PhaseNotFoundError):
        await put_phase_draft(
            db_session,
            course_slug="ai-driven-dev",
            phase_no=99,
            payload={"title": "x"},
        )


@pytest.mark.asyncio
async def test_put_task_draft_handles_skill_tags(db_session, seed_curriculum):
    await put_task_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        task_no=1,
        payload={"skill_tags": ["NEW_TAG"]},
    )
    await db_session.commit()

    row = (await db_session.execute(
        select(CurriculumTask)
        .join(CurriculumPhase, CurriculumTask.phase_id == CurriculumPhase.id)
        .join(Course, CurriculumPhase.course_id == Course.id)
        .where(
            Course.slug == "ai-driven-dev",
            CurriculumPhase.phase_no == 1,
            CurriculumTask.task_no == 1,
        )
    )).scalar_one()
    assert row.draft_skill_tags == ["NEW_TAG"]


@pytest.mark.asyncio
async def test_publish_course_promotes_drafts_and_reloads_cache(
    db_session, seed_curriculum
):
    await put_phase_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        payload={"title": "公開対象タイトル"},
    )
    await put_task_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        task_no=1,
        payload={"title": "新 task 1 title"},
    )
    await db_session.commit()

    result = await publish_course(db_session, course_slug="ai-driven-dev")
    await db_session.commit()
    assert result.published_phase_count == 1
    assert result.published_task_count == 1

    # cache が新値を返す
    course = runtime.get_cached_course("ai-driven-dev")
    assert course.phases[0].title == "公開対象タイトル"
    assert course.phases[0].tasks[0].title == "新 task 1 title"

    # draft 列はクリアされている
    dev_id = (await db_session.execute(
        select(Course.id).where(Course.slug == "ai-driven-dev")
    )).scalar_one()
    p = (await db_session.execute(
        select(CurriculumPhase).where(
            CurriculumPhase.course_id == dev_id,
            CurriculumPhase.phase_no == 1,
        )
    )).scalar_one()
    assert p.draft_title is None
    assert p.title == "公開対象タイトル"


@pytest.mark.asyncio
async def test_discard_drafts_clears_all_drafts_for_course(
    db_session, seed_curriculum
):
    await put_phase_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        payload={"title": "discard me"},
    )
    await put_task_draft(
        db_session,
        course_slug="ai-driven-dev",
        phase_no=1,
        task_no=1,
        payload={"description": "discard me too"},
    )
    await db_session.commit()

    await discard_drafts(db_session, course_slug="ai-driven-dev")
    await db_session.commit()

    dev_id = (await db_session.execute(
        select(Course.id).where(Course.slug == "ai-driven-dev")
    )).scalar_one()
    p_rows = (await db_session.execute(
        select(CurriculumPhase).where(CurriculumPhase.course_id == dev_id)
    )).scalars().all()
    assert all(p.draft_title is None for p in p_rows)
    t_rows = (await db_session.execute(
        select(CurriculumTask)
        .join(CurriculumPhase, CurriculumTask.phase_id == CurriculumPhase.id)
        .where(CurriculumPhase.course_id == dev_id)
    )).scalars().all()
    assert all(t.draft_description is None for t in t_rows)
```

- [ ] **Step 2: service を作成**

`backend/app/services/curriculum_edit.py` を新規作成:

```python
"""Sprint 9 — curriculum edit service.

Routes never touch the ORM directly. They call these helpers and the
service is responsible for:
  - exclude_unset セマンティクス (key in dict / not in dict の判別)
  - publish 時の cache 差し替え
  - エラーハンドリング (PhaseNotFoundError / TaskNotFoundError /
    CourseNotFoundError)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.courses import CourseNotFoundError, runtime
from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask


class PhaseNotFoundError(Exception):
    def __init__(self, slug: str, phase_no: int) -> None:
        super().__init__(f"phase {phase_no} not found in course {slug!r}")
        self.slug = slug
        self.phase_no = phase_no


class TaskNotFoundError(Exception):
    def __init__(self, slug: str, phase_no: int, task_no: int) -> None:
        super().__init__(
            f"task {task_no} not found in phase {phase_no} of course {slug!r}"
        )
        self.slug = slug
        self.phase_no = phase_no
        self.task_no = task_no


@dataclass(frozen=True)
class PublishResult:
    slug: str
    published_phase_count: int
    published_task_count: int
    published_at: datetime


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


async def _get_course_by_slug(db: AsyncSession, slug: str) -> Course:
    course = (
        await db.execute(select(Course).where(Course.slug == slug))
    ).scalar_one_or_none()
    if course is None:
        raise CourseNotFoundError(slug)
    return course


async def _get_phase(
    db: AsyncSession, course_id, phase_no: int
) -> CurriculumPhase:
    row = (
        await db.execute(
            select(CurriculumPhase).where(
                CurriculumPhase.course_id == course_id,
                CurriculumPhase.phase_no == phase_no,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        # slug は呼び出し側が知っているのでここでは数値だけ持つ
        raise PhaseNotFoundError(slug="?", phase_no=phase_no)
    return row


async def _get_task(
    db: AsyncSession, phase_id, task_no: int
) -> CurriculumTask:
    row = (
        await db.execute(
            select(CurriculumTask).where(
                CurriculumTask.phase_id == phase_id,
                CurriculumTask.task_no == task_no,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise TaskNotFoundError(slug="?", phase_no=-1, task_no=task_no)
    return row


# ---------------------------------------------------------------------------
# Draft write
# ---------------------------------------------------------------------------


_PHASE_DRAFT_FIELDS = ("title", "goal", "system_prompt")
_TASK_DRAFT_FIELDS = (
    "title",
    "description",
    "skill_tags",
    "deliverable",
    "week_label",
)


async def put_phase_draft(
    db: AsyncSession,
    *,
    course_slug: str,
    phase_no: int,
    payload: Mapping[str, Any],
) -> CurriculumPhase:
    """payload に key があるフィールドだけ draft_* を更新する。

    None 値は「draft をクリア」、明示値は「draft を設定」。key の不在は
    「変更なし」。route は `model_dump(exclude_unset=True)` を渡す。
    """
    course = await _get_course_by_slug(db, course_slug)
    try:
        row = await _get_phase(db, course.id, phase_no)
    except PhaseNotFoundError as e:
        raise PhaseNotFoundError(course_slug, phase_no) from e

    for field in _PHASE_DRAFT_FIELDS:
        if field in payload:
            setattr(row, f"draft_{field}", payload[field])
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return row


async def put_task_draft(
    db: AsyncSession,
    *,
    course_slug: str,
    phase_no: int,
    task_no: int,
    payload: Mapping[str, Any],
) -> CurriculumTask:
    course = await _get_course_by_slug(db, course_slug)
    try:
        phase = await _get_phase(db, course.id, phase_no)
    except PhaseNotFoundError as e:
        raise PhaseNotFoundError(course_slug, phase_no) from e
    try:
        row = await _get_task(db, phase.id, task_no)
    except TaskNotFoundError as e:
        raise TaskNotFoundError(course_slug, phase_no, task_no) from e

    for field in _TASK_DRAFT_FIELDS:
        if field in payload:
            setattr(row, f"draft_{field}", payload[field])
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return row


# ---------------------------------------------------------------------------
# Publish / discard
# ---------------------------------------------------------------------------


async def publish_course(
    db: AsyncSession, *, course_slug: str
) -> PublishResult:
    """全 draft_* を対応する published 列に COPY、draft_* を NULL に。

    Returns: 影響行数。0 件も idempotent (200 OK)。
    publish 完了後、runtime cache を当該 course の rebuild で差し替える。
    """
    course = await _get_course_by_slug(db, course_slug)

    # Phase: draft が 1 つでも非 NULL の行を対象に title = COALESCE(draft, title)
    # で UPSERT (簡潔のためサービス層では行ごとにループする)
    phases = (await db.execute(
        select(CurriculumPhase).where(CurriculumPhase.course_id == course.id)
    )).scalars().all()

    published_phase = 0
    for p in phases:
        dirty = False
        if p.draft_title is not None:
            p.title = p.draft_title
            p.draft_title = None
            dirty = True
        if p.draft_goal is not None:
            p.goal = p.draft_goal
            p.draft_goal = None
            dirty = True
        if p.draft_system_prompt is not None:
            p.system_prompt = p.draft_system_prompt
            p.draft_system_prompt = None
            dirty = True
        if dirty:
            published_phase += 1
            p.updated_at = datetime.now(UTC)

    # Task は phase_id で絞って取得 (course 内の全 task)
    phase_ids = [p.id for p in phases]
    tasks = (await db.execute(
        select(CurriculumTask).where(CurriculumTask.phase_id.in_(phase_ids))
    )).scalars().all() if phase_ids else []

    published_task = 0
    for t in tasks:
        dirty = False
        if t.draft_title is not None:
            t.title = t.draft_title
            t.draft_title = None
            dirty = True
        if t.draft_description is not None:
            t.description = t.draft_description
            t.draft_description = None
            dirty = True
        if t.draft_skill_tags is not None:
            t.skill_tags = t.draft_skill_tags
            t.draft_skill_tags = None
            dirty = True
        if t.draft_deliverable is not None:
            # 空文字 = "明示的に空にしたい"。NULL ではなく empty string を保存。
            t.deliverable = t.draft_deliverable or None  # "" → None でも可
            t.draft_deliverable = None
            dirty = True
        if t.draft_week_label is not None:
            t.week_label = t.draft_week_label or None
            t.draft_week_label = None
            dirty = True
        if dirty:
            published_task += 1
            t.updated_at = datetime.now(UTC)

    await db.flush()

    # cache を差し替え
    await runtime.reload_course(db, course_slug)

    return PublishResult(
        slug=course_slug,
        published_phase_count=published_phase,
        published_task_count=published_task,
        published_at=datetime.now(UTC),
    )


async def discard_drafts(db: AsyncSession, *, course_slug: str) -> None:
    """当該 course 配下の全 draft_* 列を NULL にする。published は変更なし。"""
    course = await _get_course_by_slug(db, course_slug)
    phase_ids = [
        row[0] for row in (await db.execute(
            select(CurriculumPhase.id).where(
                CurriculumPhase.course_id == course.id
            )
        )).all()
    ]

    await db.execute(
        update(CurriculumPhase)
        .where(CurriculumPhase.course_id == course.id)
        .values(
            draft_title=None,
            draft_goal=None,
            draft_system_prompt=None,
        )
    )
    if phase_ids:
        await db.execute(
            update(CurriculumTask)
            .where(CurriculumTask.phase_id.in_(phase_ids))
            .values(
                draft_title=None,
                draft_description=None,
                draft_skill_tags=None,
                draft_deliverable=None,
                draft_week_label=None,
            )
        )
    await db.flush()


# ---------------------------------------------------------------------------
# Count drafts (admin 一覧バッジ用)
# ---------------------------------------------------------------------------


async def count_pending_drafts(db: AsyncSession, *, course_slug: str) -> int:
    """draft_* に非 NULL がある field の総数を返す (Phase + Task)。"""
    course = await _get_course_by_slug(db, course_slug)
    phases = (await db.execute(
        select(CurriculumPhase).where(CurriculumPhase.course_id == course.id)
    )).scalars().all()
    n = 0
    for p in phases:
        n += sum(
            1
            for f in ("draft_title", "draft_goal", "draft_system_prompt")
            if getattr(p, f) is not None
        )
    phase_ids = [p.id for p in phases]
    if phase_ids:
        tasks = (await db.execute(
            select(CurriculumTask).where(CurriculumTask.phase_id.in_(phase_ids))
        )).scalars().all()
        for t in tasks:
            n += sum(
                1
                for f in (
                    "draft_title",
                    "draft_description",
                    "draft_skill_tags",
                    "draft_deliverable",
                    "draft_week_label",
                )
                if getattr(t, f) is not None
            )
    return n
```

- [ ] **Step 3: テスト実行 (まだ seed_curriculum fixture が無いので fail でも OK、Task 10 で緑化)**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest tests/test_curriculum_edit_service.py -q 2>&1 | tail -5
```

Expected: fixture not found / errors (Task 10 まで放置)。

- [ ] **Step 4: Commit (red commit を許容)**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/services/curriculum_edit.py backend/tests/test_curriculum_edit_service.py
git commit -m "feat(sprint-9): curriculum_edit service (red until Task 10)"
```

---

## Task 8: rate limit settings 追加

**Files:**
- Modify: `backend/app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: `config.py` に rate limit 2 件追加**

`backend/app/config.py` の Settings クラス内に追記 (既存 admin_write_rate_limit の近く):

```python
    # Sprint 9 — curriculum 編集 (admin GUI)
    # debounce 自動保存で連続 PUT が来るので writes は余裕を持って高めに。
    # publish は cache 全リビルドを伴うので絞る。
    admin_curriculum_write_rate_limit: str = "120/minute"
    admin_curriculum_publish_rate_limit: str = "10/minute"
```

- [ ] **Step 2: `.env.example` に対応する env を追加**

`.env.example` の末尾に追記:

```
# Sprint 9 — curriculum 編集 (admin GUI)
ADMIN_CURRICULUM_WRITE_RATE_LIMIT=120/minute
ADMIN_CURRICULUM_PUBLISH_RATE_LIMIT=10/minute
```

- [ ] **Step 3: import 確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run python -c "from app.config import settings; print(settings.admin_curriculum_write_rate_limit, settings.admin_curriculum_publish_rate_limit)"
```

Expected: `120/minute 10/minute`。

- [ ] **Step 4: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/config.py .env.example
git commit -m "feat(sprint-9): admin_curriculum rate limit settings (write 120 / publish 10)"
```

---

## Task 9: `app/api/admin/curriculum.py` (6 ルート) + main.py 登録

**Files:**
- Create: `backend/app/api/admin/curriculum.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_admin_curriculum_api.py`

> **ANTI-HALLUCINATION:** 既存の admin route ファイル (users / submissions / comments / notifications / user_dashboard) には触らない。`get_current_admin` dependency を流用する。route 内の cache reload は service 層で完結 (publish の中で reload_course を呼んでいる)。

- [ ] **Step 1: failing test を追加**

`backend/tests/test_admin_curriculum_api.py` を新規作成:

```python
"""Sprint 9 — admin curriculum HTTP API tests."""

import pytest


@pytest.mark.asyncio
async def test_list_requires_admin(client, auth_user, auth_token, seed_curriculum):
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    res = client.get("/api/admin/curriculum/")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_list_returns_courses_with_zero_drafts(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get("/api/admin/curriculum/")
    assert res.status_code == 200
    items = res.json()["items"]
    slugs = [it["slug"] for it in items]
    assert "ai-driven-dev" in slugs
    assert all(it["pending_draft_count"] == 0 for it in items)


@pytest.mark.asyncio
async def test_detail_returns_phases_and_tasks(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.get("/api/admin/curriculum/ai-driven-dev")
    assert res.status_code == 200
    body = res.json()
    assert body["slug"] == "ai-driven-dev"
    assert len(body["phases"]) == 4
    p1 = body["phases"][0]
    assert p1["phase_no"] == 1
    assert len(p1["tasks"]) == 3
    assert p1["draft_title"] is None  # 初期は draft なし


@pytest.mark.asyncio
async def test_put_phase_records_draft(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.put(
        "/api/admin/curriculum/ai-driven-dev/phases/1",
        json={"title": "新しい Phase 1"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["draft_title"] == "新しい Phase 1"
    assert body["title"] != "新しい Phase 1"  # published はまだ未更新


@pytest.mark.asyncio
async def test_put_task_records_draft_skill_tags(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    res = client.put(
        "/api/admin/curriculum/ai-driven-dev/phases/1/tasks/1",
        json={"skill_tags": ["NEW_TAG", "NEW_TAG", "ANOTHER"]},
    )
    assert res.status_code == 200
    body = res.json()
    # dedup されている
    assert body["draft_skill_tags"] == ["NEW_TAG", "ANOTHER"]


@pytest.mark.asyncio
async def test_publish_promotes_drafts_idempotent(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    client.put(
        "/api/admin/curriculum/ai-driven-dev/phases/1",
        json={"title": "publish me"},
    )
    res = client.post("/api/admin/curriculum/ai-driven-dev/publish")
    assert res.status_code == 200
    body = res.json()
    assert body["published_phase_count"] == 1

    # 2 度目の publish は 0 件 (idempotent)
    res2 = client.post("/api/admin/curriculum/ai-driven-dev/publish")
    assert res2.status_code == 200
    assert res2.json()["published_phase_count"] == 0


@pytest.mark.asyncio
async def test_discard_drafts_returns_204(
    client, admin_user, admin_token, seed_curriculum
):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    client.put(
        "/api/admin/curriculum/ai-driven-dev/phases/1",
        json={"title": "discard"},
    )
    res = client.post("/api/admin/curriculum/ai-driven-dev/draft")
    assert res.status_code == 204
```

- [ ] **Step 2: route を作成**

`backend/app/api/admin/curriculum.py` を新規作成:

```python
"""Sprint 9 — admin curriculum editing API (`/api/admin/curriculum/...`)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_admin
from app.core.limiter import limiter
from app.data.courses import CourseNotFoundError
from app.db.session import get_db
from app.models.course import Course
from app.models.curriculum_phase import CurriculumPhase
from app.models.curriculum_task import CurriculumTask
from app.models.user import User
from app.schemas.admin_curriculum import (
    AdminCurriculumCourseDetail,
    AdminCurriculumCourseList,
    AdminCurriculumCourseSummary,
    AdminCurriculumPublishOut,
    AdminPhaseEditOut,
    AdminPhaseUpdateRequest,
    AdminTaskEditOut,
    AdminTaskUpdateRequest,
)
from app.services.curriculum_edit import (
    PhaseNotFoundError,
    TaskNotFoundError,
    count_pending_drafts,
    discard_drafts,
    publish_course,
    put_phase_draft,
    put_task_draft,
)

router = APIRouter(prefix="/api/admin/curriculum", tags=["admin"])


def _task_to_dto(t: CurriculumTask) -> AdminTaskEditOut:
    return AdminTaskEditOut(
        task_no=t.task_no,
        title=t.title,
        description=t.description,
        skill_tags=list(t.skill_tags or []),
        deliverable=t.deliverable,
        week_label=t.week_label,
        draft_title=t.draft_title,
        draft_description=t.draft_description,
        draft_skill_tags=t.draft_skill_tags,
        draft_deliverable=t.draft_deliverable,
        draft_week_label=t.draft_week_label,
        updated_at=t.updated_at,
    )


def _phase_to_dto(
    p: CurriculumPhase, tasks: list[CurriculumTask]
) -> AdminPhaseEditOut:
    return AdminPhaseEditOut(
        phase_no=p.phase_no,
        title=p.title,
        goal=p.goal,
        system_prompt=p.system_prompt,
        draft_title=p.draft_title,
        draft_goal=p.draft_goal,
        draft_system_prompt=p.draft_system_prompt,
        tasks=[
            _task_to_dto(t)
            for t in sorted(tasks, key=lambda r: r.task_no)
        ],
        updated_at=p.updated_at,
    )


@router.get("/", response_model=AdminCurriculumCourseList)
async def list_courses(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCurriculumCourseList:
    rows = (
        await db.execute(select(Course).order_by(Course.sort_order))
    ).scalars().all()
    items: list[AdminCurriculumCourseSummary] = []
    for c in rows:
        n = await count_pending_drafts(db, course_slug=c.slug)
        items.append(
            AdminCurriculumCourseSummary(
                slug=c.slug, title=c.title, pending_draft_count=n
            )
        )
    return AdminCurriculumCourseList(items=items)


@router.get("/{course_slug}", response_model=AdminCurriculumCourseDetail)
async def get_detail(
    course_slug: str = Path(...),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCurriculumCourseDetail:
    course = (
        await db.execute(select(Course).where(Course.slug == course_slug))
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")

    phases = (await db.execute(
        select(CurriculumPhase)
        .where(CurriculumPhase.course_id == course.id)
        .order_by(CurriculumPhase.phase_no)
    )).scalars().all()
    phase_ids = [p.id for p in phases]
    tasks = (await db.execute(
        select(CurriculumTask).where(CurriculumTask.phase_id.in_(phase_ids))
    )).scalars().all() if phase_ids else []
    by_phase: dict = {pid: [] for pid in phase_ids}
    for t in tasks:
        by_phase[t.phase_id].append(t)

    return AdminCurriculumCourseDetail(
        slug=course.slug,
        title=course.title,
        phases=[_phase_to_dto(p, by_phase.get(p.id, [])) for p in phases],
    )


@router.put(
    "/{course_slug}/phases/{phase_no}",
    response_model=AdminPhaseEditOut,
)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def put_phase(
    request: Request,
    payload: AdminPhaseUpdateRequest,
    course_slug: str = Path(...),
    phase_no: int = Path(ge=1),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminPhaseEditOut:
    try:
        row = await put_phase_draft(
            db,
            course_slug=course_slug,
            phase_no=phase_no,
            payload=payload.model_dump(exclude_unset=True),
        )
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    except PhaseNotFoundError:
        raise HTTPException(status_code=404, detail="phase not found")
    await db.commit()
    await db.refresh(row)

    tasks = (await db.execute(
        select(CurriculumTask).where(CurriculumTask.phase_id == row.id)
    )).scalars().all()
    return _phase_to_dto(row, list(tasks))


@router.put(
    "/{course_slug}/phases/{phase_no}/tasks/{task_no}",
    response_model=AdminTaskEditOut,
)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def put_task(
    request: Request,
    payload: AdminTaskUpdateRequest,
    course_slug: str = Path(...),
    phase_no: int = Path(ge=1),
    task_no: int = Path(ge=1),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTaskEditOut:
    # skill_tags dedup を request 段階で適用 (空でない指定があれば dedup)
    body = payload.model_dump(exclude_unset=True)
    if "skill_tags" in body and body["skill_tags"] is not None:
        body["skill_tags"] = payload.normalized_skill_tags()
    try:
        row = await put_task_draft(
            db,
            course_slug=course_slug,
            phase_no=phase_no,
            task_no=task_no,
            payload=body,
        )
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    except PhaseNotFoundError:
        raise HTTPException(status_code=404, detail="phase not found")
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail="task not found")
    await db.commit()
    await db.refresh(row)
    return _task_to_dto(row)


@router.post(
    "/{course_slug}/publish",
    response_model=AdminCurriculumPublishOut,
)
@limiter.limit(lambda: settings.admin_curriculum_publish_rate_limit)
async def publish(
    request: Request,
    course_slug: str = Path(...),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCurriculumPublishOut:
    try:
        result = await publish_course(db, course_slug=course_slug)
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    await db.commit()
    return AdminCurriculumPublishOut(
        slug=result.slug,
        published_phase_count=result.published_phase_count,
        published_task_count=result.published_task_count,
        published_at=result.published_at,
    )


@router.post(
    "/{course_slug}/draft",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit(lambda: settings.admin_curriculum_write_rate_limit)
async def discard(
    request: Request,
    course_slug: str = Path(...),
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await discard_drafts(db, course_slug=course_slug)
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="course not found")
    await db.commit()
    return None
```

- [ ] **Step 3: `app/main.py` に router を登録**

`backend/app/main.py` の import 行に追加:

```python
from app.api.admin import curriculum as admin_curriculum
```

`include_router` の admin 系の末尾に追加:

```python
app.include_router(admin_curriculum.router)
```

- [ ] **Step 4: import 確認 (起動はしない)**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run python -c "from app.api.admin import curriculum as c; print(c.router.prefix)"
```

Expected: `/api/admin/curriculum`。

- [ ] **Step 5: Commit (red commit を許容)**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/api/admin/curriculum.py backend/app/main.py backend/tests/test_admin_curriculum_api.py
git commit -m "feat(sprint-9): admin curriculum API (6 routes) + main.py router (red until Task 10)"
```

---

## Task 10: `conftest.py` 改修 (curriculum 再 seed + reload_from_db + fixture)

**Files:**
- Modify: `backend/tests/conftest.py`

> **ANTI-HALLUCINATION:** 既存 fixture (`auth_user`, `admin_user`, `db_session`, `default_course_id`) の名前と意味は維持。新規 `seed_curriculum` fixture を追加し、`db_session` の各テスト前に curriculum_phases / curriculum_tasks も再 seed する。

- [ ] **Step 1: 既存 conftest を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && grep -n "db_session\|COURSE_REGISTRY\|seed_curriculum\|reload_from_db" tests/conftest.py
```

`db_session` fixture が `courses` テーブルを seed していることを確認。

- [ ] **Step 2: conftest を改修**

`backend/tests/conftest.py` の `db_session` fixture 内、courses seed の直後に curriculum_phases / curriculum_tasks の seed を追加。Code 例 (既存の courses seed 後に挿入):

```python
        # Sprint 9: curriculum_phases / curriculum_tasks も毎テスト再 seed
        from app.models.curriculum_phase import CurriculumPhase
        from app.models.curriculum_task import CurriculumTask
        for slug, c in COURSE_REGISTRY.items():
            for phase in c.phases:
                phase_row = CurriculumPhase(
                    course_id=c.id,
                    phase_no=phase.phase,
                    title=phase.title,
                    goal=phase.goal,
                    system_prompt=phase.system_prompt,
                )
                session.add(phase_row)
                await session.flush()
                for t in phase.tasks:
                    session.add(CurriculumTask(
                        phase_id=phase_row.id,
                        task_no=t.task_no,
                        title=t.title,
                        description=t.description,
                        skill_tags=list(t.skill_tags),
                        deliverable=t.deliverable,
                        week_label=t.week_label,
                    ))
        await session.commit()

        # cache を test DB の内容で初期化
        from app.data.courses import runtime
        await runtime.reload_from_db(session)
        yield session
```

そして `seed_curriculum` fixture を追加 (no-op で db_session への依存だけ):

```python
@pytest_asyncio.fixture
async def seed_curriculum(db_session):
    """Sprint 9 — Task 1-9 のテストが curriculum_phases / curriculum_tasks を
    必要とすることを明示するためのマーカー。実際の seed は db_session で済む。"""
    return db_session
```

- [ ] **Step 3: 全テスト緑を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q 2>&1 | tail -10
```

Expected: `395 passed` (370 + 4 (Task 1) + 3 (Task 2) + 5 (Task 3) + 6 (Task 7) + 7 (Task 9) = 395)。

- [ ] **Step 4: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/tests/conftest.py
git commit -m "test(sprint-9): conftest re-seeds curriculum + reload cache + seed_curriculum fixture"
```

---

## Task 11: フロント — `types/admin_curriculum.ts` + `lib/api.ts` 拡張

**Files:**
- Create: `frontend/src/types/admin_curriculum.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: types を作成**

`frontend/src/types/admin_curriculum.ts` を新規作成:

```typescript
// Sprint 9 — admin curriculum editing DTOs (mirror backend schemas).

export interface AdminCurriculumCourseSummary {
  slug: string;
  title: string;
  pending_draft_count: number;
}

export interface AdminCurriculumCourseList {
  items: AdminCurriculumCourseSummary[];
}

export interface AdminTaskEditOut {
  task_no: number;
  title: string;
  description: string;
  skill_tags: string[];
  deliverable: string | null;
  week_label: string | null;
  draft_title: string | null;
  draft_description: string | null;
  draft_skill_tags: string[] | null;
  draft_deliverable: string | null;
  draft_week_label: string | null;
  updated_at: string;
}

export interface AdminPhaseEditOut {
  phase_no: number;
  title: string;
  goal: string;
  system_prompt: string;
  draft_title: string | null;
  draft_goal: string | null;
  draft_system_prompt: string | null;
  tasks: AdminTaskEditOut[];
  updated_at: string;
}

export interface AdminCurriculumCourseDetail {
  slug: string;
  title: string;
  phases: AdminPhaseEditOut[];
}

export interface AdminCurriculumPublishOut {
  slug: string;
  published_phase_count: number;
  published_task_count: number;
  published_at: string;
}

// Request bodies — exclude_unset semantics. クライアント側は変更したい field
// だけを payload に含める (省略 = 変更なし、明示 null = draft クリア、値 = draft 設定)。
export interface AdminPhasePatch {
  title?: string | null;
  goal?: string | null;
  system_prompt?: string | null;
}

export interface AdminTaskPatch {
  title?: string | null;
  description?: string | null;
  skill_tags?: string[] | null;
  deliverable?: string | null;
  week_label?: string | null;
}
```

- [ ] **Step 2: `lib/api.ts` に admin curriculum 6 メソッドを追加**

`frontend/src/lib/api.ts` の `import type` 群に追加:

```typescript
import type {
  AdminCurriculumCourseDetail,
  AdminCurriculumCourseList,
  AdminCurriculumPublishOut,
  AdminPhaseEditOut,
  AdminPhasePatch,
  AdminTaskEditOut,
  AdminTaskPatch,
} from '@/types/admin_curriculum';
```

`api` オブジェクト内に追加:

```typescript
  // Sprint 9 — admin curriculum editing.
  adminCurriculumList: (): Promise<AdminCurriculumCourseList> =>
    rawRequest<AdminCurriculumCourseList>('/api/admin/curriculum/', {
      method: 'GET',
    }),
  adminCurriculumDetail: (slug: string): Promise<AdminCurriculumCourseDetail> =>
    rawRequest<AdminCurriculumCourseDetail>(
      `/api/admin/curriculum/${encodeURIComponent(slug)}`,
      { method: 'GET' },
    ),
  adminPutCurriculumPhase: (
    slug: string,
    phaseNo: number,
    body: AdminPhasePatch,
  ): Promise<AdminPhaseEditOut> =>
    rawRequest<AdminPhaseEditOut>(
      `/api/admin/curriculum/${encodeURIComponent(slug)}/phases/${phaseNo}`,
      { method: 'PUT', body: JSON.stringify(body) },
    ),
  adminPutCurriculumTask: (
    slug: string,
    phaseNo: number,
    taskNo: number,
    body: AdminTaskPatch,
  ): Promise<AdminTaskEditOut> =>
    rawRequest<AdminTaskEditOut>(
      `/api/admin/curriculum/${encodeURIComponent(slug)}/phases/${phaseNo}/tasks/${taskNo}`,
      { method: 'PUT', body: JSON.stringify(body) },
    ),
  adminPublishCurriculum: (slug: string): Promise<AdminCurriculumPublishOut> =>
    rawRequest<AdminCurriculumPublishOut>(
      `/api/admin/curriculum/${encodeURIComponent(slug)}/publish`,
      { method: 'POST' },
    ),
  adminDiscardCurriculumDrafts: (slug: string): Promise<void> =>
    rawRequest<void>(
      `/api/admin/curriculum/${encodeURIComponent(slug)}/draft`,
      { method: 'POST' },
    ),
```

- [ ] **Step 3: build を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm run build 2>&1 | tail -3
```

Expected: 成功。

- [ ] **Step 4: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/types/admin_curriculum.ts frontend/src/lib/api.ts
git commit -m "feat(sprint-9): frontend types + api client for admin curriculum editing"
```

---

## Task 12: フロント — `stores/admin_curriculum.ts` (debounced PUT)

**Files:**
- Create: `frontend/src/stores/admin_curriculum.ts`
- Create: `frontend/src/__tests__/admin_curriculum.store.spec.ts`

- [ ] **Step 1: failing test を追加**

`frontend/src/__tests__/admin_curriculum.store.spec.ts` を新規作成:

```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      adminCurriculumList: vi.fn(),
      adminCurriculumDetail: vi.fn(),
      adminPutCurriculumPhase: vi.fn(),
      adminPutCurriculumTask: vi.fn(),
      adminPublishCurriculum: vi.fn(),
      adminDiscardCurriculumDrafts: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import { useAdminCurriculumStore } from '@/stores/admin_curriculum';

describe('admin_curriculum store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('fetchList populates state', async () => {
    (api.adminCurriculumList as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({ items: [{ slug: 'a', title: 'A', pending_draft_count: 2 }] });
    const store = useAdminCurriculumStore();
    await store.fetchList();
    expect(store.list).toHaveLength(1);
    expect(store.list[0].pending_draft_count).toBe(2);
  });

  it('putTask debounce sends only the last value within window', async () => {
    (api.adminPutCurriculumTask as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({} as never);
    const store = useAdminCurriculumStore();
    vi.useFakeTimers();
    try {
      store.putTask('ai-driven-dev', 1, 1, { title: 'a' });
      store.putTask('ai-driven-dev', 1, 1, { title: 'ab' });
      store.putTask('ai-driven-dev', 1, 1, { title: 'abc' });
      await vi.advanceTimersByTimeAsync(600);
      expect(api.adminPutCurriculumTask).toHaveBeenCalledTimes(1);
      expect(api.adminPutCurriculumTask).toHaveBeenCalledWith(
        'ai-driven-dev', 1, 1, { title: 'abc' },
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it('publish then refetches detail', async () => {
    (api.adminPublishCurriculum as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({
        slug: 'a', published_phase_count: 1, published_task_count: 2,
        published_at: '2026-06-13T00:00:00Z',
      });
    (api.adminCurriculumDetail as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({ slug: 'a', title: 'A', phases: [] });
    const store = useAdminCurriculumStore();
    await store.publish('a');
    expect(api.adminCurriculumDetail).toHaveBeenCalledWith('a');
    expect(store.detail?.slug).toBe('a');
  });

  it('discardDrafts then refetches detail', async () => {
    (api.adminDiscardCurriculumDrafts as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue(undefined as never);
    (api.adminCurriculumDetail as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({ slug: 'a', title: 'A', phases: [] });
    const store = useAdminCurriculumStore();
    await store.discardDrafts('a');
    expect(api.adminDiscardCurriculumDrafts).toHaveBeenCalledWith('a');
    expect(api.adminCurriculumDetail).toHaveBeenCalledWith('a');
  });
});
```

- [ ] **Step 2: store を作成**

`frontend/src/stores/admin_curriculum.ts` を新規作成:

```typescript
import { defineStore } from 'pinia';
import { api } from '@/lib/api';
import type {
  AdminCurriculumCourseDetail,
  AdminCurriculumCourseSummary,
  AdminPhasePatch,
  AdminTaskPatch,
} from '@/types/admin_curriculum';

interface PendingTimer {
  timer: ReturnType<typeof setTimeout>;
  lastPayload: AdminPhasePatch | AdminTaskPatch;
}

const DEBOUNCE_MS = 500;

interface State {
  list: AdminCurriculumCourseSummary[];
  detail: AdminCurriculumCourseDetail | null;
  saveError: string | null;
  pending: Record<string, PendingTimer>;
}

function phaseKey(slug: string, phaseNo: number): string {
  return `phase:${slug}:${phaseNo}`;
}
function taskKey(slug: string, phaseNo: number, taskNo: number): string {
  return `task:${slug}:${phaseNo}:${taskNo}`;
}

export const useAdminCurriculumStore = defineStore('admin_curriculum', {
  state: (): State => ({
    list: [],
    detail: null,
    saveError: null,
    pending: {},
  }),
  actions: {
    async fetchList() {
      const res = await api.adminCurriculumList();
      this.list = res.items;
    },

    async fetchDetail(slug: string) {
      this.detail = await api.adminCurriculumDetail(slug);
    },

    putPhase(slug: string, phaseNo: number, payload: AdminPhasePatch) {
      const key = phaseKey(slug, phaseNo);
      this._scheduleDebounced(key, payload, async (latest) => {
        try {
          await api.adminPutCurriculumPhase(slug, phaseNo, latest as AdminPhasePatch);
          this.saveError = null;
          // ローカルの detail を最新値で書き換える (確実な再描画のため)
          await this.fetchDetail(slug);
        } catch (e) {
          this.saveError = e instanceof Error ? e.message : String(e);
        }
      });
    },

    putTask(
      slug: string,
      phaseNo: number,
      taskNo: number,
      payload: AdminTaskPatch,
    ) {
      const key = taskKey(slug, phaseNo, taskNo);
      this._scheduleDebounced(key, payload, async (latest) => {
        try {
          await api.adminPutCurriculumTask(
            slug, phaseNo, taskNo, latest as AdminTaskPatch,
          );
          this.saveError = null;
          await this.fetchDetail(slug);
        } catch (e) {
          this.saveError = e instanceof Error ? e.message : String(e);
        }
      });
    },

    async publish(slug: string) {
      await api.adminPublishCurriculum(slug);
      await this.fetchDetail(slug);
    },

    async discardDrafts(slug: string) {
      await api.adminDiscardCurriculumDrafts(slug);
      await this.fetchDetail(slug);
    },

    // ----- internal -----
    _scheduleDebounced(
      key: string,
      payload: AdminPhasePatch | AdminTaskPatch,
      fire: (latest: AdminPhasePatch | AdminTaskPatch) => Promise<void>,
    ) {
      const existing = this.pending[key];
      const merged = { ...(existing?.lastPayload ?? {}), ...payload };
      if (existing) {
        clearTimeout(existing.timer);
      }
      const timer = setTimeout(() => {
        delete this.pending[key];
        void fire(merged);
      }, DEBOUNCE_MS);
      this.pending[key] = { timer, lastPayload: merged };
    },
  },
});
```

- [ ] **Step 3: テスト緑を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run src/__tests__/admin_curriculum.store.spec.ts 2>&1 | tail -3
```

Expected: `4 passed`。

- [ ] **Step 4: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/stores/admin_curriculum.ts frontend/src/__tests__/admin_curriculum.store.spec.ts
git commit -m "feat(sprint-9): admin_curriculum store with 500ms debounced PUT"
```

---

## Task 13: フロント — `AdminCurriculumListView.vue` (一覧 + draft バッジ)

**Files:**
- Create: `frontend/src/views/admin/AdminCurriculumListView.vue`
- Create: `frontend/src/__tests__/AdminCurriculumListView.spec.ts`

- [ ] **Step 1: failing test を追加**

`frontend/src/__tests__/AdminCurriculumListView.spec.ts` を新規作成:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { mount, flushPromises } from '@vue/test-utils';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      adminCurriculumList: vi.fn(),
    },
  };
});

vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
}));

import { api } from '@/lib/api';
import AdminCurriculumListView from '@/views/admin/AdminCurriculumListView.vue';

describe('AdminCurriculumListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('renders course summary cards', async () => {
    (api.adminCurriculumList as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({
        items: [
          { slug: 'ai-driven-dev', title: 'AI Dev', pending_draft_count: 0 },
          { slug: 'ai-era-se', title: 'SE', pending_draft_count: 3 },
        ],
      });
    const w = mount(AdminCurriculumListView);
    await flushPromises();
    expect(w.text()).toContain('AI Dev');
    expect(w.text()).toContain('SE');
  });

  it('shows draft badge only when pending_draft_count > 0', async () => {
    (api.adminCurriculumList as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({
        items: [
          { slug: 'a', title: 'A', pending_draft_count: 0 },
          { slug: 'b', title: 'B', pending_draft_count: 5 },
        ],
      });
    const w = mount(AdminCurriculumListView);
    await flushPromises();
    const badges = w.findAll('[data-test="draft-badge"]');
    expect(badges).toHaveLength(1);
    expect(badges[0].text()).toContain('5');
  });
});
```

- [ ] **Step 2: View を作成**

`frontend/src/views/admin/AdminCurriculumListView.vue` を新規作成:

```vue
<script setup lang="ts">
import { onMounted } from 'vue';
import { RouterLink } from 'vue-router';
import { useAdminCurriculumStore } from '@/stores/admin_curriculum';

const store = useAdminCurriculumStore();

onMounted(() => {
  void store.fetchList();
});
</script>

<template>
  <section class="curriculum-list">
    <h1>カリキュラム編集</h1>
    <p class="hint">
      タスク本文・skill_tags・Phase の system_prompt 等を編集できます。
      公開すると受講者の表示が即座に切り替わります。
    </p>

    <ul class="courses">
      <li v-for="c in store.list" :key="c.slug" class="course">
        <RouterLink
          :to="`/admin/curriculum/${c.slug}`"
          class="course-link"
        >
          <span class="title">{{ c.title }}</span>
          <span
            v-if="c.pending_draft_count > 0"
            class="badge"
            data-test="draft-badge"
          >
            {{ c.pending_draft_count }} 件の draft
          </span>
        </RouterLink>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.curriculum-list { max-width: 720px; margin: 2rem auto; }
.hint { color: #6b7280; font-size: 0.9rem; }
.courses { list-style: none; padding: 0; }
.course { margin: 0.75rem 0; }
.course-link {
  display: flex; align-items: center; justify-content: space-between;
  padding: 1rem; border: 1px solid #e5e7eb; border-radius: 12px;
  text-decoration: none; color: inherit;
}
.title { font-weight: 600; }
.badge {
  background: #fef3c7; color: #92400e;
  padding: 0.2rem 0.6rem; border-radius: 999px;
  font-size: 0.8rem;
}
</style>
```

- [ ] **Step 3: テスト緑を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run src/__tests__/AdminCurriculumListView.spec.ts 2>&1 | tail -3
```

Expected: `2 passed`。

- [ ] **Step 4: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/views/admin/AdminCurriculumListView.vue frontend/src/__tests__/AdminCurriculumListView.spec.ts
git commit -m "feat(sprint-9): AdminCurriculumListView with draft badges"
```

---

## Task 14: フロント — `SkillTagInput.vue` + `CurriculumTaskEditor.vue`

**Files:**
- Create: `frontend/src/components/admin/SkillTagInput.vue`
- Create: `frontend/src/components/admin/CurriculumTaskEditor.vue`
- Create: `frontend/src/__tests__/CurriculumTaskEditor.spec.ts`

- [ ] **Step 1: failing test を追加**

`frontend/src/__tests__/CurriculumTaskEditor.spec.ts` を新規作成:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { mount } from '@vue/test-utils';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      adminPutCurriculumTask: vi.fn(),
      adminCurriculumDetail: vi.fn().mockResolvedValue({
        slug: 'ai-driven-dev', title: 'X', phases: [],
      }),
    },
  };
});

import { api } from '@/lib/api';
import CurriculumTaskEditor from '@/components/admin/CurriculumTaskEditor.vue';
import type { AdminTaskEditOut } from '@/types/admin_curriculum';

function makeTask(overrides: Partial<AdminTaskEditOut> = {}): AdminTaskEditOut {
  return {
    task_no: 1,
    title: 'Original',
    description: 'desc',
    skill_tags: ['Git/GitHub'],
    deliverable: null,
    week_label: null,
    draft_title: null,
    draft_description: null,
    draft_skill_tags: null,
    draft_deliverable: null,
    draft_week_label: null,
    updated_at: '2026-06-13T00:00:00Z',
    ...overrides,
  };
}

describe('CurriculumTaskEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('debounce fires putTask once with the last value', async () => {
    vi.useFakeTimers();
    const w = mount(CurriculumTaskEditor, {
      props: { courseSlug: 'ai-driven-dev', phaseNo: 1, task: makeTask() },
    });
    const input = w.find('[data-test="task-title-input"]');
    await input.setValue('A');
    await input.setValue('AB');
    await input.setValue('ABC');
    await vi.advanceTimersByTimeAsync(600);
    expect(api.adminPutCurriculumTask).toHaveBeenCalledTimes(1);
    expect(api.adminPutCurriculumTask).toHaveBeenCalledWith(
      'ai-driven-dev', 1, 1, expect.objectContaining({ title: 'ABC' }),
    );
    vi.useRealTimers();
  });

  it('shows ✏ indicator when draft_title is set', () => {
    const w = mount(CurriculumTaskEditor, {
      props: {
        courseSlug: 'ai-driven-dev',
        phaseNo: 1,
        task: makeTask({ draft_title: 'Draft' }),
      },
    });
    expect(w.find('[data-test="title-draft-indicator"]').exists()).toBe(true);
  });
});
```

- [ ] **Step 2: `SkillTagInput.vue` を作成**

`frontend/src/components/admin/SkillTagInput.vue` を新規作成:

```vue
<script setup lang="ts">
import { ref } from 'vue';

const props = defineProps<{ tags: string[] }>();
const emit = defineEmits<{ change: [tags: string[]] }>();

const draft = ref('');

function addTag() {
  const t = draft.value.trim();
  if (!t || t.length > 50) return;
  if (props.tags.includes(t)) return;
  emit('change', [...props.tags, t]);
  draft.value = '';
}

function removeTag(t: string) {
  emit('change', props.tags.filter((x) => x !== t));
}
</script>

<template>
  <div class="tags">
    <span v-for="t in tags" :key="t" class="chip">
      {{ t }}
      <button
        type="button"
        class="remove"
        :aria-label="`Remove ${t}`"
        @click="removeTag(t)"
      >×</button>
    </span>
    <input
      v-model="draft"
      type="text"
      placeholder="新しいタグ + Enter"
      maxlength="50"
      data-test="skill-tag-input"
      @keydown.enter.prevent="addTag"
      @blur="addTag"
    />
  </div>
</template>

<style scoped>
.tags { display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; }
.chip {
  background: #e0e7ff; color: #3730a3;
  padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.85rem;
  display: inline-flex; gap: 0.3rem; align-items: center;
}
.remove { background: none; border: 0; color: inherit; cursor: pointer; }
input {
  flex: 1; min-width: 8rem;
  border: 1px solid #d1d5db; border-radius: 6px;
  padding: 0.3rem 0.5rem; font: inherit;
}
</style>
```

- [ ] **Step 3: `CurriculumTaskEditor.vue` を作成**

`frontend/src/components/admin/CurriculumTaskEditor.vue` を新規作成:

```vue
<script setup lang="ts">
import { computed } from 'vue';
import { useAdminCurriculumStore } from '@/stores/admin_curriculum';
import SkillTagInput from './SkillTagInput.vue';
import type { AdminTaskEditOut } from '@/types/admin_curriculum';

const props = defineProps<{
  courseSlug: string;
  phaseNo: number;
  task: AdminTaskEditOut;
}>();

const store = useAdminCurriculumStore();

const t = computed(() => props.task);

// 表示する value: draft が非 NULL ならそれを、NULL なら published を。
const titleValue = computed({
  get: () => t.value.draft_title ?? t.value.title,
  set: (v: string) => store.putTask(props.courseSlug, props.phaseNo, t.value.task_no, { title: v }),
});
const descValue = computed({
  get: () => t.value.draft_description ?? t.value.description,
  set: (v: string) => store.putTask(props.courseSlug, props.phaseNo, t.value.task_no, { description: v }),
});
const deliverableValue = computed({
  get: () => t.value.draft_deliverable ?? t.value.deliverable ?? '',
  set: (v: string) => store.putTask(props.courseSlug, props.phaseNo, t.value.task_no, { deliverable: v }),
});
const weekLabelValue = computed({
  get: () => t.value.draft_week_label ?? t.value.week_label ?? '',
  set: (v: string) => store.putTask(props.courseSlug, props.phaseNo, t.value.task_no, { week_label: v }),
});
const displayedTags = computed(() => t.value.draft_skill_tags ?? t.value.skill_tags);

function onTagsChange(tags: string[]) {
  store.putTask(props.courseSlug, props.phaseNo, t.value.task_no, { skill_tags: tags });
}
</script>

<template>
  <article class="task-edit" :data-test="`task-edit-${t.task_no}`">
    <header>
      <span class="num">Task {{ t.task_no }}</span>
    </header>

    <label>
      <span class="lbl">title <span v-if="t.draft_title !== null" class="ind" data-test="title-draft-indicator">✏</span></span>
      <input
        v-model="titleValue"
        type="text"
        maxlength="200"
        data-test="task-title-input"
      />
    </label>

    <label>
      <span class="lbl">description <span v-if="t.draft_description !== null" class="ind">✏</span></span>
      <textarea v-model="descValue" rows="3" maxlength="2000" />
    </label>

    <label>
      <span class="lbl">skill_tags <span v-if="t.draft_skill_tags !== null" class="ind">✏</span></span>
      <SkillTagInput :tags="displayedTags" @change="onTagsChange" />
    </label>

    <div class="row">
      <label>
        <span class="lbl">deliverable <span v-if="t.draft_deliverable !== null" class="ind">✏</span></span>
        <input v-model="deliverableValue" type="text" maxlength="200" />
      </label>
      <label>
        <span class="lbl">week_label <span v-if="t.draft_week_label !== null" class="ind">✏</span></span>
        <input v-model="weekLabelValue" type="text" maxlength="200" />
      </label>
    </div>
  </article>
</template>

<style scoped>
.task-edit {
  border: 1px solid #e5e7eb; border-radius: 10px;
  padding: 0.8rem 1rem; margin: 0.5rem 0;
  display: flex; flex-direction: column; gap: 0.6rem;
}
header { display: flex; gap: 0.5rem; align-items: baseline; }
.num { font-weight: 700; color: #6b7280; }
.lbl { display: block; font-size: 0.85rem; color: #374151; margin-bottom: 0.25rem; }
.ind { color: #d97706; }
input, textarea {
  width: 100%;
  border: 1px solid #d1d5db; border-radius: 6px;
  padding: 0.4rem 0.6rem; font: inherit;
}
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; }
</style>
```

- [ ] **Step 4: テスト緑を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run src/__tests__/CurriculumTaskEditor.spec.ts 2>&1 | tail -3
```

Expected: `2 passed`。

- [ ] **Step 5: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/components/admin/SkillTagInput.vue frontend/src/components/admin/CurriculumTaskEditor.vue frontend/src/__tests__/CurriculumTaskEditor.spec.ts
git commit -m "feat(sprint-9): SkillTagInput + CurriculumTaskEditor with debounce"
```

---

## Task 15: フロント — `CurriculumPhaseEditor.vue`

**Files:**
- Create: `frontend/src/components/admin/CurriculumPhaseEditor.vue`

> **ANTI-HALLUCINATION:** Phase 単位の field は `title` / `goal` / `system_prompt` の 3 つだけ。tasks 表示は `CurriculumTaskEditor` を子コンポーネントで描画。

- [ ] **Step 1: `CurriculumPhaseEditor.vue` を作成**

`frontend/src/components/admin/CurriculumPhaseEditor.vue` を新規作成:

```vue
<script setup lang="ts">
import { computed, ref } from 'vue';
import { useAdminCurriculumStore } from '@/stores/admin_curriculum';
import CurriculumTaskEditor from './CurriculumTaskEditor.vue';
import type { AdminPhaseEditOut } from '@/types/admin_curriculum';

const props = defineProps<{
  courseSlug: string;
  phase: AdminPhaseEditOut;
}>();

const store = useAdminCurriculumStore();
const collapsed = ref(false);

const titleValue = computed({
  get: () => props.phase.draft_title ?? props.phase.title,
  set: (v: string) => store.putPhase(props.courseSlug, props.phase.phase_no, { title: v }),
});
const goalValue = computed({
  get: () => props.phase.draft_goal ?? props.phase.goal,
  set: (v: string) => store.putPhase(props.courseSlug, props.phase.phase_no, { goal: v }),
});
const systemPromptValue = computed({
  get: () => props.phase.draft_system_prompt ?? props.phase.system_prompt,
  set: (v: string) => store.putPhase(props.courseSlug, props.phase.phase_no, { system_prompt: v }),
});
</script>

<template>
  <section class="phase-edit" :data-test="`phase-edit-${phase.phase_no}`">
    <header @click="collapsed = !collapsed">
      <span class="toggle">{{ collapsed ? '▶' : '▼' }}</span>
      <h2>Phase {{ phase.phase_no }}: {{ phase.title }}</h2>
    </header>

    <div v-if="!collapsed" class="body">
      <label>
        <span class="lbl">title <span v-if="phase.draft_title !== null" class="ind">✏</span></span>
        <input v-model="titleValue" type="text" maxlength="200" />
      </label>
      <label>
        <span class="lbl">goal <span v-if="phase.draft_goal !== null" class="ind">✏</span></span>
        <input v-model="goalValue" type="text" maxlength="500" />
      </label>
      <label>
        <span class="lbl">system_prompt <span v-if="phase.draft_system_prompt !== null" class="ind">✏</span></span>
        <textarea v-model="systemPromptValue" rows="8" maxlength="8000" />
      </label>

      <CurriculumTaskEditor
        v-for="t in phase.tasks"
        :key="t.task_no"
        :course-slug="courseSlug"
        :phase-no="phase.phase_no"
        :task="t"
      />
    </div>
  </section>
</template>

<style scoped>
.phase-edit {
  border: 1px solid #d1d5db; border-radius: 12px;
  padding: 1rem 1.2rem; margin: 1rem 0;
  background: #f9fafb;
}
header {
  display: flex; align-items: baseline; gap: 0.6rem;
  cursor: pointer;
}
header h2 { margin: 0; font-size: 1rem; }
.toggle { color: #6b7280; }
.lbl { display: block; font-size: 0.85rem; color: #374151; margin-top: 0.6rem; }
.ind { color: #d97706; }
input, textarea {
  width: 100%;
  border: 1px solid #d1d5db; border-radius: 6px;
  padding: 0.4rem 0.6rem; font: inherit;
}
.body { display: flex; flex-direction: column; gap: 0.3rem; }
</style>
```

- [ ] **Step 2: build を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm run build 2>&1 | tail -3
```

Expected: 成功。

- [ ] **Step 3: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/components/admin/CurriculumPhaseEditor.vue
git commit -m "feat(sprint-9): CurriculumPhaseEditor with collapsible tasks"
```

---

## Task 16: フロント — `AdminCurriculumEditView.vue` (parent + publish/discard)

**Files:**
- Create: `frontend/src/views/admin/AdminCurriculumEditView.vue`
- Create: `frontend/src/__tests__/AdminCurriculumEditView.spec.ts`

- [ ] **Step 1: failing test を追加**

`frontend/src/__tests__/AdminCurriculumEditView.spec.ts` を新規作成:

```typescript
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { mount, flushPromises } from '@vue/test-utils';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      adminCurriculumDetail: vi.fn(),
      adminPublishCurriculum: vi.fn(),
      adminDiscardCurriculumDrafts: vi.fn(),
    },
  };
});

import { api } from '@/lib/api';
import AdminCurriculumEditView from '@/views/admin/AdminCurriculumEditView.vue';

function fakeDetail(draftCount: number) {
  return {
    slug: 'ai-driven-dev',
    title: 'AI Dev',
    phases: [
      {
        phase_no: 1, title: 'Phase 1', goal: 'g', system_prompt: 'sp',
        draft_title: draftCount > 0 ? 'draft' : null,
        draft_goal: null, draft_system_prompt: null,
        tasks: [{
          task_no: 1, title: 'T1', description: 'd', skill_tags: [],
          deliverable: null, week_label: null,
          draft_title: null, draft_description: null,
          draft_skill_tags: null, draft_deliverable: null, draft_week_label: null,
          updated_at: '2026-06-13T00:00:00Z',
        }],
        updated_at: '2026-06-13T00:00:00Z',
      },
    ],
  };
}

describe('AdminCurriculumEditView', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('fetches detail on mount', async () => {
    (api.adminCurriculumDetail as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue(fakeDetail(0));
    mount(AdminCurriculumEditView, {
      props: { courseSlug: 'ai-driven-dev' },
    });
    await flushPromises();
    expect(api.adminCurriculumDetail).toHaveBeenCalledWith('ai-driven-dev');
  });

  it('publish button triggers confirm modal then publish', async () => {
    (api.adminCurriculumDetail as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue(fakeDetail(1));
    (api.adminPublishCurriculum as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue({
        slug: 'ai-driven-dev', published_phase_count: 1,
        published_task_count: 0, published_at: '2026-06-13T00:00:00Z',
      });
    const w = mount(AdminCurriculumEditView, {
      props: { courseSlug: 'ai-driven-dev' },
    });
    await flushPromises();
    await w.find('[data-test="publish-btn"]').trigger('click');
    // 確認モーダルの「公開する」をクリック
    await w.find('[data-test="publish-confirm"]').trigger('click');
    await flushPromises();
    expect(api.adminPublishCurriculum).toHaveBeenCalledWith('ai-driven-dev');
  });

  it('discard button triggers confirm modal then discard', async () => {
    (api.adminCurriculumDetail as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue(fakeDetail(1));
    (api.adminDiscardCurriculumDrafts as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValue(undefined as never);
    const w = mount(AdminCurriculumEditView, {
      props: { courseSlug: 'ai-driven-dev' },
    });
    await flushPromises();
    await w.find('[data-test="discard-btn"]').trigger('click');
    await w.find('[data-test="discard-confirm"]').trigger('click');
    await flushPromises();
    expect(api.adminDiscardCurriculumDrafts).toHaveBeenCalledWith('ai-driven-dev');
  });
});
```

- [ ] **Step 2: View を作成**

`frontend/src/views/admin/AdminCurriculumEditView.vue` を新規作成:

```vue
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useAdminCurriculumStore } from '@/stores/admin_curriculum';
import CurriculumPhaseEditor from '@/components/admin/CurriculumPhaseEditor.vue';

const props = defineProps<{ courseSlug: string }>();
const store = useAdminCurriculumStore();
const publishOpen = ref(false);
const discardOpen = ref(false);

onMounted(load);
watch(() => props.courseSlug, load);

async function load() {
  await store.fetchDetail(props.courseSlug);
}

// draft 件数: 全 phase + task の draft_* で非 NULL のもの。
const draftCount = computed(() => {
  if (!store.detail) return 0;
  let n = 0;
  for (const p of store.detail.phases) {
    for (const f of ['draft_title', 'draft_goal', 'draft_system_prompt'] as const) {
      if (p[f] !== null) n += 1;
    }
    for (const t of p.tasks) {
      for (const f of [
        'draft_title', 'draft_description', 'draft_skill_tags',
        'draft_deliverable', 'draft_week_label',
      ] as const) {
        if (t[f] !== null) n += 1;
      }
    }
  }
  return n;
});

async function confirmPublish() {
  publishOpen.value = false;
  await store.publish(props.courseSlug);
}

async function confirmDiscard() {
  discardOpen.value = false;
  await store.discardDrafts(props.courseSlug);
}
</script>

<template>
  <section v-if="store.detail" class="edit">
    <header class="course-head">
      <h1>{{ store.detail.title }}</h1>
      <span v-if="draftCount > 0" class="draft-count">
        {{ draftCount }} 件の draft あり
      </span>
      <div class="actions">
        <button
          type="button"
          :disabled="draftCount === 0"
          data-test="publish-btn"
          @click="publishOpen = true"
        >Publish</button>
        <button
          type="button"
          class="ghost"
          :disabled="draftCount === 0"
          data-test="discard-btn"
          @click="discardOpen = true"
        >Discard drafts</button>
      </div>
    </header>

    <p v-if="store.saveError" class="error">{{ store.saveError }}</p>

    <CurriculumPhaseEditor
      v-for="p in store.detail.phases"
      :key="p.phase_no"
      :course-slug="courseSlug"
      :phase="p"
    />

    <!-- Publish confirm -->
    <div v-if="publishOpen" class="modal" role="dialog">
      <div class="modal-body">
        <p>{{ draftCount }} 件の draft を公開しますか？</p>
        <p class="muted">公開すると受講者の表示が即座に切り替わります。</p>
        <div class="modal-actions">
          <button type="button" data-test="publish-confirm" @click="confirmPublish">公開する</button>
          <button type="button" class="ghost" @click="publishOpen = false">キャンセル</button>
        </div>
      </div>
    </div>

    <!-- Discard confirm -->
    <div v-if="discardOpen" class="modal" role="dialog">
      <div class="modal-body">
        <p>{{ draftCount }} 件の draft を破棄しますか？</p>
        <div class="modal-actions">
          <button type="button" data-test="discard-confirm" @click="confirmDiscard">破棄する</button>
          <button type="button" class="ghost" @click="discardOpen = false">キャンセル</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.edit { max-width: 880px; margin: 1.5rem auto; }
.course-head { display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; }
.course-head h1 { margin: 0; flex: 1; }
.draft-count {
  background: #fef3c7; color: #92400e;
  padding: 0.25rem 0.7rem; border-radius: 999px; font-size: 0.85rem;
}
.actions { display: flex; gap: 0.5rem; }
button { padding: 0.45rem 1rem; border-radius: 8px; border: 0; cursor: pointer; }
.ghost { background: transparent; border: 1px solid #d1d5db; }
button:disabled { opacity: 0.4; cursor: not-allowed; }
.error { color: #b91c1c; background: #fee2e2; padding: 0.5rem 0.8rem; border-radius: 8px; }
.modal {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center;
}
.modal-body {
  background: #fff; padding: 1.5rem; border-radius: 12px;
  max-width: 420px;
}
.modal-actions { display: flex; gap: 0.5rem; margin-top: 1rem; }
.muted { color: #6b7280; font-size: 0.85rem; }
</style>
```

- [ ] **Step 3: テスト緑を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run src/__tests__/AdminCurriculumEditView.spec.ts 2>&1 | tail -3
```

Expected: `3 passed`。

- [ ] **Step 4: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/views/admin/AdminCurriculumEditView.vue frontend/src/__tests__/AdminCurriculumEditView.spec.ts
git commit -m "feat(sprint-9): AdminCurriculumEditView with publish/discard modals"
```

---

## Task 17: router + AdminLayout nav

**Files:**
- Modify: `frontend/src/router/admin.ts`
- Modify: `frontend/src/layouts/AdminLayout.vue`

- [ ] **Step 1: router にルート追加**

`frontend/src/router/admin.ts` を読んで、既存 `adminRoutes` 配列にアルファベット順で追加:

```typescript
import AdminCurriculumListView from '@/views/admin/AdminCurriculumListView.vue';
import AdminCurriculumEditView from '@/views/admin/AdminCurriculumEditView.vue';
// ...
export const adminRoutes = [
  // ... 既存 ...
  {
    path: '/admin/curriculum',
    name: 'admin-curriculum-list',
    component: AdminCurriculumListView,
    meta: { requiresAdmin: true },
  },
  {
    path: '/admin/curriculum/:courseSlug',
    name: 'admin-curriculum-edit',
    component: AdminCurriculumEditView,
    props: true,
    meta: { requiresAdmin: true },
  },
];
```

- [ ] **Step 2: `AdminLayout.vue` の nav に追加**

`frontend/src/layouts/AdminLayout.vue` を読んで、既存 nav の `<RouterLink>` 群に追加:

```vue
<RouterLink to="/admin/curriculum">カリキュラム編集</RouterLink>
```

- [ ] **Step 3: build を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm run build 2>&1 | tail -3
```

Expected: 成功。

- [ ] **Step 4: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/router/admin.ts frontend/src/layouts/AdminLayout.vue
git commit -m "feat(sprint-9): admin curriculum routes + AdminLayout nav link"
```

---

## Task 18: Playwright E2E (`admin-curriculum.spec.ts`)

**Files:**
- Create: `frontend/e2e/admin-curriculum.spec.ts`

> **ANTI-HALLUCINATION:** stub mode (`CLAUDE_STUB_MODE=true`) で backend を起動する前提。admin user は env から取得する仕組みが既存 spec にない (smoke / dashboard では新規 register → login)。本 spec も新規 register → admin 昇格は手動 (promote_admin script) で行うか、`auth_user` を直接 admin にする backend 側 helper を仮定するのではなく、register 後に backend の db に直接 admin フラグを立てる選択肢にする。

実装簡素化: backend のテスト helper を E2E から呼ぶのは難しいので、本 E2E では既存 dev DB に admin ユーザが既に存在する前提で書く。CI ではこのテストは `.skip` で外し、ローカルでのみ実行する。 (CI で動かしたい場合は別途 `make e2e-admin-curriculum` を作る方針を follow-up に。)

- [ ] **Step 1: spec を作成**

`frontend/e2e/admin-curriculum.spec.ts` を新規作成:

```typescript
import { test, expect } from '@playwright/test';

/**
 * Sprint 9 — admin curriculum 編集 → publish → 受講者画面で反映を確認。
 *
 * 前提:
 *   - backend が CLAUDE_STUB_MODE=true で起動
 *   - dev DB に admin ユーザ (instructor@example.com / password123) が
 *     promote_admin 経由で存在 (`uv run python -m scripts.promote_admin
 *     instructor@example.com`)
 *
 * CI ではこの spec は `.skip` 扱い (admin 昇格手順が CI フローに無いため)。
 * ローカル動作確認用。
 */

const ADMIN_EMAIL = 'instructor@example.com';
const ADMIN_PASSWORD = 'password123';
const LEARNER_PASSWORD = 'password12345';

test.skip(
  'admin edits a task title and the learner sees the change',
  async ({ page, browser }) => {
    // 1. 学習者を新規登録 (Sprint 7 LoginView)
    const learnerEmail = `learner-${Date.now()}@example.com`;
    await page.goto('/login');
    await page.getByRole('tab', { name: '新規登録' }).click();
    await page.getByLabel('メールアドレス').fill(learnerEmail);
    await page.getByLabel('お名前').fill('テスト学習者');
    await page.locator('[data-test="course-select"]').waitFor();
    await page
      .locator('[data-test="course-select"]')
      .selectOption('ai-driven-dev');
    await page.getByLabel('パスワード').fill(LEARNER_PASSWORD);
    await page.getByRole('button', { name: '登録する' }).click();
    await expect(page.getByText('登録できました')).toBeVisible();

    // 2. admin で別 context にログインして編集
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    await adminPage.goto('/login');
    await adminPage.getByLabel('メールアドレス').fill(ADMIN_EMAIL);
    await adminPage.getByLabel('パスワード').fill(ADMIN_PASSWORD);
    await adminPage.getByRole('button', { name: 'ログイン' }).click();
    await adminPage.goto('/admin/curriculum/ai-driven-dev');

    const NEW_TITLE = `Sprint9 E2E ${Date.now()}`;
    const taskCard = adminPage.locator('[data-test="task-edit-1"]');
    await taskCard.locator('[data-test="task-title-input"]').fill(NEW_TITLE);
    // debounce + PUT
    await adminPage.waitForTimeout(700);

    // publish
    await adminPage.locator('[data-test="publish-btn"]').click();
    await adminPage.locator('[data-test="publish-confirm"]').click();
    // バッジが 0 件に戻るまで待機
    await expect(adminPage.locator('.draft-count')).toHaveCount(0, {
      timeout: 10000,
    });

    // 3. 学習者ページに戻って Phase 1 で title が NEW_TITLE になっていることを確認
    await page.getByLabel('パスワード').fill(LEARNER_PASSWORD);
    await page.getByRole('button', { name: 'ログイン' }).click();
    await page.goto('/courses/ai-driven-dev/phases/1');
    await expect(page.locator('body')).toContainText(NEW_TITLE);

    await adminContext.close();
  },
);
```

- [ ] **Step 2: dry-run (skip されるので即座に終了する)**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npx playwright test e2e/admin-curriculum.spec.ts 2>&1 | tail -5
```

Expected: 1 skipped (CI / 通常実行ではスキップ)。

- [ ] **Step 3: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/e2e/admin-curriculum.spec.ts
git commit -m "test(sprint-9): admin curriculum E2E (skipped, requires manual admin seed)"
```

---

## Task 19: 全件テスト緑確認 + ローカル動作確認 (手動 E2E)

**Files:** なし

- [ ] **Step 1: バックエンド全件テスト**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q 2>&1 | tail -5
```

Expected: `395 passed`。

- [ ] **Step 2: フロントエンド全件テスト + build**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run 2>&1 | grep "Tests" | head -1
npm run build 2>&1 | tail -3
```

Expected: `94 passed`、build 成功。

- [ ] **Step 3: Playwright E2E (smoke + dashboard、admin-curriculum は skip)**

```bash
# backend を 8001 で起動
cd /Volumes/Seagate3TB/projects/edu/backend && \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  JWT_SECRET_KEY=test-secret ANTHROPIC_API_KEY=test-key \
  GRADING_ASYNC_ENABLED=false CLAUDE_STUB_MODE=true \
  RATE_LIMIT_ENABLED=false BCRYPT_ROUNDS=4 \
  CORS_ALLOW_ORIGINS=http://localhost:5173 \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 &
sleep 6

cd /Volumes/Seagate3TB/projects/edu/frontend && \
  VITE_API_BASE_URL=http://127.0.0.1:8001 npx playwright test 2>&1 | tail -8

# 終了後
lsof -ti:8001 | xargs -r kill
```

Expected: 4 passed (smoke 2 + dashboard 2)、1 skipped (admin-curriculum)。

- [ ] **Step 4: 手動動作確認 (MCP playwright か dev サーバで確認)**

```bash
# 既存 admin user (instructor@example.com) を作成 + 昇格
cd /Volumes/Seagate3TB/projects/edu/backend && \
  set -a && . ../.env && set +a && \
  DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
  uv run python -m scripts.promote_admin instructor@example.com
```

dev サーバを起動して以下の確認:

```bash
cd /Volumes/Seagate3TB/projects/edu && make dev
```

ブラウザで:
1. `/login` → admin (instructor@example.com / password123) でログイン
2. `/admin/curriculum` で 2 course (ai-driven-dev / ai-era-se) が見える
3. `/admin/curriculum/ai-driven-dev` で Task 1 title を変更 → 500ms 後にバッジが「1 件の draft あり」
4. [Publish] → 確認モーダル → 「公開する」 → バッジが 0 に
5. 別タブで受講者として `/courses/ai-driven-dev/phases/1` を開き、Task 1 title が新値になっていることを確認

問題があれば該当 Task に戻って修正、本 Task はリプレイ。

---

## Task 20: code-reviewer + security-reviewer

**Files:** review 指摘箇所のみ

- [ ] **Step 1: code-reviewer agent を実行**

```
Sprint 9 curriculum 編集機能 (admin GUI) の実装が main HEAD = f389bd0 を起点とする feature/sprint-9 ブランチで完了した。重点的に確認してほしい点:
- get_course() の cache rewire が既存 service 群 (enrollment / submission / dashboard / progress) と互換であること
- Alembic migration の seed dict literal が ai_driven_dev.py / ai_era_se.py の現値と一致
- PUT routes の exclude_unset セマンティクスが「key 不在 = 変更なし」「明示 None = draft クリア」「値あり = draft 設定」を満たすこと
- 既存 admin route との CSP / CORS / rate limit の整合
- conftest 改修で他テストが破綻していないこと
spec: docs/superpowers/specs/2026-06-13-sprint-9-curriculum-editing-design.md
plan: docs/superpowers/plans/2026-06-13-ai-tutor-curriculum-sprint-9.md
HIGH / MEDIUM / LOW で出力。
```

- [ ] **Step 2: security-reviewer agent を実行**

```
Sprint 9 curriculum 編集機能を OWASP Top 10 + Sprint 4 セキュリティ系項目で監査。
重点:
- /api/admin/curriculum/* が is_admin 以外で叩けないこと (BOLA / IDOR)
- skill_tags JSONB に injection 可能性なし (Postgres 標準 escape)
- system_prompt の文字列長キャップが Claude API トークン上限に対し十分か
- publish の cache 差し替えが TOCTOU を起こさないか
- conftest の seed_curriculum fixture が他テストの状態を漏らさないか
- rate limit 値 (write=120/min、publish=10/min) が暴力的編集を抑えられるか
```

- [ ] **Step 3: HIGH 指摘を本 Sprint 内で修正**

各 reviewer が HIGH を出した箇所を個別 commit で修正:

```bash
git commit -m "fix(sprint-9): address HIGH-N from code/security review"
```

MEDIUM/LOW は `docs/superpowers/specs/2026-06-1X-sprint-9-followups.md` に記載 (Task 22 で作成)。

- [ ] **Step 4: 再度全件テスト**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q 2>&1 | tail -3
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run 2>&1 | grep "Tests" | head -1
```

Expected: 全件緑。

---

## Task 21: follow-up doc 作成

**Files:**
- Create: `docs/superpowers/specs/2026-06-1X-sprint-9-followups.md` (実装日に合わせて 1X 置換)

- [ ] **Step 1: follow-up doc を作成**

`docs/superpowers/specs/2026-06-1X-sprint-9-followups.md` に code/security review で出た MEDIUM/LOW 指摘 + 元 spec の out-of-scope を整理:

```markdown
# Sprint 9 follow-up tickets

> 起点: docs/superpowers/specs/2026-06-13-sprint-9-curriculum-editing-design.md
> 完了 sprint: Sprint 9 (commit <hash>)
> ベースライン: backend 395 / frontend 94 (Sprint 9 完了時)

## MEDIUM

(code/security review からの追加項目をここに記入)

## LOW

### LOW-1: Phase / Task の追加・削除・並び替え
add task / delete task / reorder の UI と API。`progress.total_tasks` 整合性、
submission UNIQUE 制約の更新を含む。

### LOW-2: Course 自体の追加・削除
new course の作成、deprecated course の archive。

### LOW-3: 編集履歴 / バージョン管理
`curriculum_versions` テーブルを追加し、各 publish を 1 version として保存。
誰がいつ何を変えたかの監査トレイル。

### LOW-4: multi-worker キャッシュ無効化
Redis pub/sub で publish イベントを N 個の worker に broadcast、各
worker が `reload_course` を実行。

### LOW-5: embeddings の自動再生成
publish 時に arq job で `seed_embeddings` を実行、変更されたタスクだけ
embedding を更新。

### LOW-6: 編集中の楽観ロック
`updated_at` を ETag として HTTP header に乗せ、PUT 時に `If-Match` で
チェック。

### LOW-7: セッション固定モード
チャット途中の Phase で system_prompt が publish されても、セッションが
終わるまで古い prompt を使い続けるオプション。

### LOW-8: 専用 RBAC ロール
`User.is_curriculum_editor` フラグ追加。admin の中で curriculum 編集
できる人を分離。

## INFRA

### INFRA-1: admin-curriculum E2E を CI で動かす
現状は admin 昇格手順が CI フローにないので skip。CI で `make
promote-admin-ci` のような targets を追加して E2E を起動。
```

- [ ] **Step 2: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add docs/superpowers/specs/2026-06-1X-sprint-9-followups.md
git commit -m "docs(sprint-9): follow-up tickets for Sprint 10+ candidates"
```

---

## Task 22: README 更新

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README の Sprint 完了マークに Sprint 9 を追加**

`README.md` の Sprint 完了表に追記:

```markdown
- [x] Sprint 9: curriculum 編集機能 (admin GUI、DB 永続化、draft → publish 二段階、process-local cache、PUT exclude_unset)
```

「マルチコース運用」セクションの後に「curriculum 編集運用」セクションを追加:

```markdown
## curriculum 編集運用 (Sprint 9〜)

- admin は `/admin/curriculum` で 2 course のタスク本文・skill_tags・Phase の system_prompt 等を編集できる
- 500ms debounce で draft が自動保存 (明示 "保存" ボタンなし)
- ✏️ アイコン = draft あり、ヘッダのバッジで draft 件数を表示
- [Publish] ボタンで course 単位に draft を一括公開、確認モーダル付き
- 公開後は受講者画面に即座に反映 (Phase 一覧 / Task カード / チャットの system_prompt)
- 既存のグレーディング履歴・weakness 計算は新しい skill_tags で再計算 (snapshot しない)
- embeddings は手動再生成: `make seed-embeddings`
- Alembic 初回 seed はマイグレーション内 dict literal で固定 (将来 Python ファイルを編集しても migration 挙動不変)
```

- [ ] **Step 2: Commit**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add README.md
git commit -m "docs(sprint-9): README — curriculum 編集運用セクション追加"
```

---

## Task 23: main マージ + feature ブランチ削除

**Files:** なし

- [ ] **Step 1: main へ fast-forward マージ**

```bash
cd /Volumes/Seagate3TB/projects/edu
git checkout main
git pull --ff-only || true
git merge --ff-only feature/sprint-9
git log --oneline -5
```

Expected: feature/sprint-9 の最新コミットが main の HEAD に。

- [ ] **Step 2: feature ブランチを削除**

```bash
git branch -d feature/sprint-9
```

- [ ] **Step 3: 最終 sanity check (main で)**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend && uv run pytest -q 2>&1 | tail -3
cd /Volumes/Seagate3TB/projects/edu/frontend && npm test -- --run 2>&1 | grep "Tests" | head -1
```

Expected: backend `395 passed` / frontend `94 passed`。

- [ ] **Step 4: memory を更新 (人間運用)**

Sprint 完了状態を memory に記録:
- `MEMORY.md` の Sprint workflow 1 行を Sprint 9 完了に更新
- `edu_sprint7_followups.md` の残件から「curriculum 編集 (admin GUI)」を消去
- 必要に応じて新規 `edu_sprint9_followups.md` を作成

---

## Plan 完了確認

- [ ] backend 395 passed
- [ ] frontend 94 passed
- [ ] E2E 4 passed + 1 skipped (admin-curriculum はローカルのみ)
- [ ] Alembic upgrade / downgrade 両方成功
- [ ] admin が `/admin/curriculum` で 2 course を編集 → publish → 受講者画面に反映を確認
- [ ] code-reviewer + security-reviewer 完了、HIGH 修正済
- [ ] follow-up doc + README 更新済
- [ ] main HEAD = Sprint 9 完了 commit
