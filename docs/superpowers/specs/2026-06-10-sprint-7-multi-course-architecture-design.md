# Sprint 7 — マルチコース化アーキテクチャ設計

**作成日:** 2026-06-10
**起点:** `docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md`（Cursor IDE プロトタイプの引き継ぎメモ、Sprint 7 完了時に削除予定）
**前提 HEAD:** `89ca06f`（Sprint 6 完了 + follow-up batch 2）
**前提 Alembic:** `57242832bf0f`
**前提テスト:** backend 298 passed / frontend 64 passed

---

## 1. ゴールと非目標

### ゴール

AI tutor を 1 コース固定から複数コース並走可能な基盤に切り替え、既存「AI駆動型開発 補足カリキュラム」(`ai-driven-dev`) と新規「AI時代SE育成カリキュラム」(`ai-era-se`) の Phase 1 パイロットを同時運用できるようにする。既存ユーザは何もせずに `ai-driven-dev` を継続利用でき、新規登録者は登録時にコースを選択する。

### コース構成

| slug | タイトル | 内容 | Sprint 7 投入範囲 |
|---|---|---|---|
| `ai-driven-dev` | AI駆動型開発 補足カリキュラム | 既存 4 フェーズ・各 3〜5 課題 | 既存データを移設 |
| `ai-era-se` | AI時代SE育成カリキュラム | 12 ヶ月・4 フェーズ | **Phase 1 (8 課題) のみ** |

固定 UUID（マイグレーション seed 用）:

```
ai-driven-dev  → 00000000-0000-4000-8000-000000000001
ai-era-se      → 00000000-0000-4000-8000-000000000002
```

`DEFAULT_COURSE_SLUG = "ai-driven-dev"` — `?course=` 未指定時と旧 URL の redirect 先。

### 含むもの (in-scope)

1. `courses` / `enrollments` テーブル新設、主要テーブル (`progress` / `submissions` / `chat_history` / `embeddings` / `user_nudges`) への `course_id` FK 追加
2. `backend/app/data/courses/` Python レジストリ + 既存 `curriculum.py` を `ai-driven-dev` として移設
3. `ai-era-se` Phase 1 課題 8 件をコードに反映、AI 活用ルール 5 条と Phase 1 評価基準を全フェーズ `system_prompt` にリテラル注入
4. 登録時のコース選択（`POST /api/auth/register` に `course_slug` 必須）
5. 既存 API すべてに `?course={slug}` クエリでのスコープ追加
6. フロント: `LoginView` でコース選択、`CourseListView` 新規、ルートを `/courses/:slug/phases/:phase` 構成へ、`/phases/:phase` は `ai-driven-dev` への redirect
7. 既存ユーザ全員（admin 含む）を `ai-driven-dev` に auto-enroll する Alembic マイグレーション
8. `GET /api/me/dashboard` および `GET /api/admin/users/{id}/dashboard` のコーススコープ化（弱点・推奨・nudge・進捗サマリーを active course で算出）
9. Cursor プロトタイプメモ (`docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md`) を最終タスクで削除

### 含まないもの (out-of-scope / follow-up 候補)

- `ai-era-se` Phase 2-4 の課題定義（パイロット成功後）
- `POST /api/admin/users/{id}/enrollments`（admin 経由の追加 enroll API）
- `scripts/seed_embeddings.py` の `source_ref` をコース付き形式 `course:{slug}:phase:{n}:task:{m}` に変更
- broadcast 通知のコーススコープ化
- 採点ジョブの非同期化、curriculum 編集機能、Playwright headless 導入

### 非機能要件

- 既存 backend テスト 298 件 + 新規 ≈40 件で **338 passed** 目標、実行 60s 以内
- 既存 frontend テスト 64 件 + 新規 ≈15 件で **79 passed** 目標
- Alembic マイグレーション 1 リビジョン、`alembic downgrade -1` で完全に巻き戻せる（`ai-era-se` 投入データは消える旨明記）
- 既存ユーザのデータ可視性に欠落が起きないこと（auto-enroll + course_id バックフィル）

---

## 2. データモデル

### 新規テーブル

**`courses`** — コース定義

| 列 | 型 | 制約 |
|---|---|---|
| `id` | UUID | PK |
| `slug` | TEXT | UNIQUE NOT NULL |
| `title` | TEXT | NOT NULL |
| `description` | TEXT | NULL |
| `sort_order` | INT | NOT NULL DEFAULT 0 |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() |

**`enrollments`** — 受講関係（many-to-many）

| 列 | 型 | 制約 |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | NOT NULL, FK users(id) ON DELETE CASCADE |
| `course_id` | UUID | NOT NULL, FK courses(id) ON DELETE RESTRICT |
| `status` | TEXT | NOT NULL DEFAULT 'active' (`'active' \| 'paused' \| 'completed'`) |
| `enrolled_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() |
| | | UNIQUE (`user_id`, `course_id`) |

### 既存テーブル変更

| テーブル | 変更内容 |
|---|---|
| `progress` | `course_id UUID NOT NULL FK courses(id) ON DELETE RESTRICT`、`UNIQUE (user_id, course_id, phase)` |
| `submissions` | `course_id` 同上、既存 `UNIQUE (user_id, phase, task_no)` → `UNIQUE (user_id, course_id, phase, task_no)`、**`CHECK (task_no BETWEEN 1 AND 5)` 削除** |
| `chat_history` | `course_id` 同上、index `(user_id, course_id, phase, created_at)` |
| `embeddings` | `course_id` 同上、index `(course_id, phase)` |
| `user_nudges` | `course_id` 同上、`UNIQUE (user_id, course_id, day_bucket)` |
| `instructor_comments` | **変更なし**（`submission_id` 経由で course_id 一意決定） |
| `notifications` | **変更なし**（sender/recipient 個別、コース横断） |

### Alembic マイグレーション

リビジョン名: `20260610_<hash>_sprint7_multi_course.py`、down_revision = `57242832bf0f`

**upgrade 手順 (順序を厳守):**

1. `courses` テーブル作成 + 2 行 seed（固定 UUID、`ai-driven-dev` は sort_order=0、`ai-era-se` は sort_order=1）
2. `enrollments` テーブル作成
3. 既存 5 テーブル (`progress` / `submissions` / `chat_history` / `embeddings` / `user_nudges`) に `course_id` 列を NULLABLE で追加（FK は同時設定）
4. 既存全行を `ai-driven-dev` の UUID で一括バックフィル (`UPDATE progress SET course_id = '00000000-...001'` 他、5 テーブル分)
5. 既存全ユーザ (admin 含む) を `ai-driven-dev` に `enrollments` insert (`INSERT INTO enrollments (id, user_id, course_id, status) SELECT gen_random_uuid(), id, '00000000-...001', 'active' FROM users ON CONFLICT DO NOTHING`)
6. すべての `course_id` 列を NOT NULL 化
7. `submissions` の `task_no` CHECK 制約削除
8. `submissions` の旧 `UNIQUE (user_id, phase, task_no)` を drop して新 `UNIQUE (user_id, course_id, phase, task_no)` を追加
9. `progress` / `user_nudges` の UNIQUE 制約も同様に再作成
10. `embeddings` / `chat_history` の新 index を作成

**downgrade 手順 (逆順):**

1. `embeddings` / `chat_history` の新 index drop
2. `progress` / `user_nudges` / `submissions` の UNIQUE 旧版復元
3. `submissions` の `task_no BETWEEN 1 AND 5` CHECK を **`ai-driven-dev` の course_id を持つ行のみに限定して**復元（`ai-era-se` 行は事前に削除）
4. 5 テーブルから `course_id` 列を drop
5. `enrollments` テーブル drop
6. `courses` テーブル drop

`ai-era-se` の投入データ（submission / chat_history など）は downgrade で失われる旨を migration の docstring に明記。

### 設計判断

- `progress.course_id` を NOT NULL にする以上、admin も含めた全ユーザ auto-enroll は必須
- バックフィルは migration 内で 1 トランザクションで完結（途中失敗時 NOT NULL 化前に rollback）
- ON DELETE: `courses` 削除は RESTRICT（運用上 hard delete しない想定）、`users` 削除は CASCADE で `enrollments` も消す

---

## 3. バックエンド設計

### カリキュラムレジストリ

```
backend/app/data/courses/
├── __init__.py          # COURSE_REGISTRY, get_course, get_phases, get_phase, DEFAULT_COURSE_SLUG
├── types.py             # CourseData, PhaseData, TaskItem (@dataclass(frozen=True))
├── ai_driven_dev.py     # 既存 curriculum.py から移設
└── ai_era_se.py         # 新規 — Phase 1 (8 課題) + AI_USAGE_RULES + _SE_TUTOR_BASE
backend/app/data/curriculum.py  # 後方互換 shim: ai-driven-dev を re-export
```

**`types.py`:**

```python
from dataclasses import dataclass
import uuid

@dataclass(frozen=True)
class TaskItem:
    task_no: int
    title: str
    description: str
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

**`__init__.py`:**

```python
COURSE_REGISTRY: dict[str, CourseData] = {
    "ai-driven-dev": AI_DRIVEN_DEV_COURSE,
    "ai-era-se": AI_ERA_SE_COURSE,
}
DEFAULT_COURSE_SLUG = "ai-driven-dev"

def get_course(slug: str) -> CourseData: ...      # raises CourseNotFoundError
def get_phases(slug: str) -> tuple[PhaseData, ...]: ...
def get_phase(slug: str, phase: int) -> PhaseData: ...  # raises PhaseNotFoundError
```

**`ai_era_se.py` — Phase 1 課題タイトル一覧（シラバスより）:**

| task_no | week | title | プロジェクト |
|---|---|---|---|
| 1 | 第1週 | Git・ターミナル・VS Code 基礎 | 共通 |
| 2 | 第2週 | PHPフレームワーク比較 (Phalcon/Laravel/Yii) | MFRS |
| 3 | 第3週 | HTTP・API・DBの仕組み（センサーデータフロー図） | Nichinichi |
| 4 | 第4週 | 業務DB読解（IES 96 テーブルから受注 ER 図） | IES |
| 5 | 第5週 | Docker・ローカル環境構築（3 プロジェクト） | 共通 |
| 6 | 第6週 | AWSインフラ概念（MFRS の ALB→EC2→RDS 構成図） | MFRS |
| 7 | 第7週 | SQL実践 (SELECT・JOIN)（ekap_test 受注集計） | IES |
| 8 | 第8週 | フェーズ1振り返り発表 | 共通 |

各課題本文（実習課題・成果物）は `ai_era_se.py` の `TaskItem.description` / `deliverable` にリテラル記述。シラバスファイル (`/Volumes/4TB_NAS/syllabus_weekly_12months.md`) 本文への依存なし。

**`AI_USAGE_RULES`** — 全フェーズ `system_prompt` にプレフィックスとして注入:

```
【AI 活用ルール】
1. AIに聞いた内容は必ず自分の言葉で再説明できること（コピペ禁止）
2. AIが生成したコードは理解してから使うこと（動けばOKは禁止）
3. プロンプトはバージョン管理すること（Gitで管理、改善履歴を残す）
4. AIが見逃した問題を自分で探す習慣を付けること
5. 「AIに任せた場面」と「自分で判断した場面」を毎週の作業ログに記録すること
```

**`_SE_TUTOR_BASE`** — 全フェーズ共通:

```
あなたは AI 時代の SE 育成を担う AI チューターです。受講者が初級エンジニア（プログラミング経験 1 年未満）であることを前提に、対話を通じて学習を支援してください。
{AI_USAGE_RULES}
```

各フェーズの `system_prompt = _SE_TUTOR_BASE + phase_specific_guidance + phase_evaluation_criteria`。

### サービス層

**新規: `app/services/enrollment.py`**

```python
async def enroll_user(db, *, user_id: UUID, course_slug: str) -> Enrollment: ...
async def require_active_enrollment(db, *, user_id: UUID, course_id: UUID) -> Enrollment: ...
async def list_my_courses(db, *, user_id: UUID) -> list[MyCourseItem]: ...

class CourseNotFoundError(Exception): ...
class EnrollmentNotFoundError(Exception): ...
class AlreadyEnrolledError(Exception): ...
```

**新規: `app/core/course_deps.py`** — FastAPI dependency

```python
@dataclass(frozen=True)
class CourseContext:
    course: CourseData
    enrollment: Enrollment | None  # admin の他人コース閲覧時は None

async def get_course_context(
    course: str | None = Query(None, alias="course"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CourseContext: ...
```

挙動:

- `?course=` 未指定 → `DEFAULT_COURSE_SLUG` に解決
- 未知 slug → `CourseNotFoundError` → 404
- 非 admin かつ未 enroll → 403 `EnrollmentNotFoundError`
- admin（`user.is_admin == True`）は未 enroll でも `enrollment=None` で許可

**変更:**

- `app/services/progress.py` — `initialize_progress(db, user_id)` → `initialize_progress_for_course(db, user_id, course_id, phase_count)`
- `app/services/submission.py` — `course_id` 必須引数化、`_validate_phase_and_task(course, phase, task_no)` をコース定義に依存
- `app/services/weakness.py`, `recommendation.py`, `nudge.py`, `progress_summary.py`, `dashboard.py` — すべて `course_id` 引数を必須化、対応するクエリに `WHERE course_id = :course_id`
- `app/memory/chat_store.py` — `get` / `save` に `course_id` 必須

### API サーフェス

| ルート | メソッド | 変更 |
|---|---|---|
| `/api/auth/register` | POST | body に `course_slug: str` 必須、`enroll_user` 呼び出し |
| `/api/courses/catalog` | GET | **新規** — 公開（未認証可）、`COURSE_REGISTRY` から `slug/title/description/sort_order` を返す |
| `/api/courses` | GET | **新規** — 認証必須、自分が enrolled なコース一覧 |
| `/api/curriculum/phases` | GET | `?course=` でスコープ |
| `/api/curriculum/phases/{phase}` | GET | 同上 |
| `/api/progress` | GET | 同上 |
| `/api/chat` | POST | body or `?course=` で対象 course を解決、`phase` 上限緩和（コース定義に依存） |
| `/api/submissions` | POST | `?course=` 必須化、`task_no` 上限はコース定義から |
| `/api/me/dashboard` | GET | `?course=` 必須、active enrollment を要件化 |
| `/api/admin/users/{id}/dashboard` | GET | `?course=` 必須、admin は他コースも閲覧可 |
| `/api/admin/users` | GET | `top_weakness_tag` 列は active enrollment のうち sort_order 最小のコース基準 |
| `/api/admin/users/{id}` | GET | レスポンスに `enrollments: [{course_slug, status, enrolled_at}]` 追加 |
| 既存 `/api/me/submissions/{id}/comments` 等 | POST | `course_id` は submission から逆引きするため body 不変 |

### スキーマ変更

- `app/schemas/auth.py` — `RegisterRequest.course_slug: str`、`COURSE_REGISTRY.keys()` で検証
- `app/schemas/chat.py` — `ChatRequest.phase` の `le=4` を廃止、course との突き合わせはサービス層
- `app/schemas/course.py` — **新規** — `CourseCatalogItem`, `EnrollmentOut`, `MyCourseItem`
- `app/schemas/admin.py` — `AdminUserDetail.enrollments: list[EnrollmentOut]` 追加

### main.py

`app.include_router(courses_router, prefix="/api/courses", tags=["courses"])`

---

## 4. フロントエンド設計

### 型・ストア・API クライアント

**新規: `frontend/src/types/course.ts`**

```ts
export interface CourseCatalogItem {
  slug: string;
  title: string;
  description: string | null;
  sort_order: number;
}
export interface EnrollmentOut {
  course_slug: string;
  course_title: string;
  status: 'active' | 'paused' | 'completed';
  enrolled_at: string;
}
export interface MyCourseItem {
  slug: string;
  title: string;
  description: string | null;
  status: 'active' | 'paused' | 'completed';
}
```

**新規: `frontend/src/stores/course.ts`** — Pinia ストア

```
state:
  activeSlug: string | null           # localStorage persist (key: ai-tutor.activeCourse)
  myCourses: MyCourseItem[]
  catalog: CourseCatalogItem[]

actions:
  setActiveCourse(slug)               # localStorage.setItem + state update
  hydrateActiveFromStorage()          # session 復帰時
  fetchMyCourses()
  fetchCatalog()
```

`activeSlug` の解決優先度: `localStorage.ai-tutor.activeCourse` → `myCourses[0]?.slug` → `null`。`null` のとき `/courses` へ誘導。

**変更: `frontend/src/lib/api.ts`**

- `withCourse(slug: string, params?: Record<string, string>): string` ヘルパー（クエリ文字列に `course=` を付与）
- 新規: `listCourseCatalog()`, `listMyCourses()`
- 既存 API（`getMyDashboard`, `getCurriculumPhases`, `postChat`, `createSubmission` 等）に `courseSlug: string` を必須引数追加
- admin 系: `getAdminUserDashboard(userId, courseSlug)` に拡張

**変更: `frontend/src/stores/auth.ts`**

- `register(email, name, password, courseSlug)` のシグネチャに `courseSlug` 必須追加

**変更: `frontend/src/stores/curriculum.ts`, `stores/dashboard.ts`, `stores/chat.ts`** — `useCourseStore().activeSlug` を参照、API 呼び出しに渡す。`activeSlug === null` 時は fetch しない（router guard で `/courses` redirect）。

### ルーティング

```
/login                                     LoginView (コース選択 select)
/courses                                   CourseListView (受講コース一覧)
/courses/:courseSlug                       HomeView (コースホーム = フェーズ一覧 + Dashboard)
/courses/:courseSlug/phases/:phase         PhaseChatView (チャット)
/phases/:phase                             redirect → /courses/ai-driven-dev/phases/:phase
/                                          redirect → /courses
```

admin ルート群はコース横断のため `?course=` クエリで個別解決（パス変更なし）。

### ビュー

**新規: `frontend/src/views/CourseListView.vue`**

- `course` ストアの `myCourses` を表示、各コースに「進む」ボタン (`/courses/:slug`)
- 未受講コースを `catalog` から表示し、「追加受講は管理者へ依頼」案内のみ
- 初回ロード時に `fetchMyCourses()` + `fetchCatalog()`

**変更: `frontend/src/views/LoginView.vue`**

- 登録フォームに `<select v-model="courseSlug">` 追加、選択肢は `catalog` を sort_order 昇順
- 未選択時は submit 不可
- 登録成功時、自動的に `course.setActiveCourse(courseSlug)` を呼ぶ
- ログイン成功時は `fetchMyCourses()` → 1 件なら自動的に active 設定し `/courses/:slug` へ、複数なら `/courses` へ

**変更: `frontend/src/views/HomeView.vue`**

- ルートパラメータ `courseSlug` を受け取り、`course.setActiveCourse(courseSlug)`
- `WeaknessCard` / `RecommendationsCard` / `NudgeBanner` / `ProgressSummaryCard` / `PhaseCard` × N をコーススコープで描画
- コース未受講で URL 直叩き時は 403 → `/courses` redirect

**変更: `frontend/src/views/PhaseChatView.vue`**

- props で `courseSlug` と `phase` を受け取り、API 呼び出しに渡す
- ヘッダーにコース名 + フェーズ名表示

**変更: `frontend/src/components/PhaseCard.vue`**

- リンク先を `/courses/:slug/phases/:phase` に変更

### Admin 画面

**変更: `frontend/src/views/AdminUserDetailView.vue`**

- ユーザの `enrollments` を表示（コース一覧 + status）
- Dashboard セクションに「コース切替セレクタ」追加（`enrollments.filter(e => e.status === 'active')` から）
- 選択中コースで `fetchUserDashboard(userId, courseSlug)`

**変更: `frontend/src/views/AdminUsersView.vue`**

- `top_weakness_tag` 列はバックエンド既定（sort_order 最小の active enrollment 基準）。表示時にコース名を小さく注記

### 後方互換

- 既存 bookmark URL `/phases/3` → `/courses/ai-driven-dev/phases/3` への redirect で温存
- 既存ユーザは自動的に `ai-driven-dev` に enroll されているため、ログイン直後 `/courses/ai-driven-dev` へ自動遷移し、見た目の変化は最小

### Router guard

`router.beforeEach` で:

1. 未ログインで `/login` 以外へのアクセス → `/login`
2. `course.activeSlug === null` で `/courses/...` 配下へのアクセス → `course.hydrateActiveFromStorage()` 後に判定、依然 null なら `/courses`
3. `course.myCourses` 未取得時はその場で `fetchMyCourses()` を待つ（レース防止）

---

## 5. テスト・リスク・残課題

### Backend テスト戦略 (pytest)

**`conftest.py` 改修必須:**

- session-scoped fixture で `COURSE_REGISTRY` 全件を `courses` テーブルへ seed
- `default_course_id` fixture (= `ai-driven-dev` の固定 UUID)
- 登録ヘルパーは `enroll_user` 経由に統一、`Submission` / `ChatHistory` 等の直接生成 fixture には `course_id=default_course_id` を明示

**既存テスト失敗復旧:** `course_id` 必須化で 50 件前後が `null value in column "course_id"` 失敗 → conftest と個別 fixture の改修で復旧。

**新規テスト想定:**

| ファイル | 件数目安 | 内容 |
|---|---|---|
| `test_courses_api.py` | ≈8 | `/api/courses/catalog`, `/api/courses` |
| `test_enrollment_service.py` | ≈10 | `enroll_user`, `require_active_enrollment`, 各 Error |
| `test_auth_api_course.py` | ≈4 | `course_slug` 必須、未知 slug 422 |
| `test_course_deps.py` | ≈6 | `?course=` 解決、未指定 → default、未 enroll → 403 |
| `test_dashboard_api_multi_course.py` | ≈4 | `?course=ai-era-se` で SE 用データのみ返る |
| `test_admin_user_dashboard_multi_course.py` | ≈3 | admin がコース切替で他コース閲覧可 |
| `test_submission_se_8tasks.py` | ≈2 | `task_no=8` 通る、`task_no=9` で 422 |
| `test_alembic_sprint7_upgrade.py` | ≈3 | 既存データの auto-enroll とバックフィルを検証 |

目標: **298 + 40 ≈ 338 passed**、実行 60s 以内。pytest は同時に 1 プロセスのみ（ハンドオフメモの注意点を遵守）。

### Frontend テスト戦略 (vitest)

| ファイル | 件数目安 | 内容 |
|---|---|---|
| `course.store.spec.ts` | ≈4 | `activeSlug` persist、`setActiveCourse`、hydrate |
| `LoginView.spec.ts` | ≈4 | course select 必須、catalog fetch、未選択時 submit 不可 |
| `CourseListView.spec.ts` | ≈3 | 受講コース一覧、未受講案内 |
| `HomeView.spec.ts` 修正 | ≈2 | courseSlug プロパティ対応 |
| `AdminUserDetailView.spec.ts` 修正 | ≈2 | コース切替セレクタ |

目標: **64 + 15 ≈ 79 passed**。

### 手動 E2E (MCP playwright)

1. 新規登録 → SE コース選択 → `CourseList` → SE Phase 1 task 1 のチャット送信 → 提出 → admin で SE コース dashboard 確認
2. 既存ユーザログイン → `ai-driven-dev` のデータがそのまま見える + dashboard が `ai-driven-dev` スコープで動く

### リスク一覧

| リスク | 影響 | 緩和策 |
|---|---|---|
| auto-enroll マイグレーションが大量データで遅い | 本番運用時の downtime | `enrollments` と `course_id` バックフィルは一括 UPDATE 1 文ずつ。現規模では batch 不要 |
| `task_no` CHECK 削除が downgrade で復元不能 | downgrade 失敗 | downgrade 時は `ai-era-se` 行を先に削除した上で `ai-driven-dev` 行のみに CHECK 復元 |
| Cursor プロトタイプとの差分による subagent ハルシネーション | Sprint 6 で前科あり | 実装 subagent プロンプトに「ハンドオフメモは参考、現 main HEAD を基準」「修正ファイル allowlist」「git status 確認必須」を明記 |
| AI 活用ルール 5 条の system_prompt 注入で grader 出力が変わる | grading 結果のレグレ | grader は `course_slug` を見てプロンプトを切替、`ai-driven-dev` は既存 prompt をそのまま温存 |
| frontend で `activeSlug` が null のまま fetch されるレース | 初回ロードで 401/403 表示 | `course.store` の hydrate 完了を待つ guard を `router.beforeEach` に追加 |
| `embeddings.course_id` 後付けによる RAG 検索精度低下 | 軽微 | `seed_embeddings.py` の `source_ref` 形式変更は follow-up に切り分け。Sprint 7 内では純粋に `course_id` 列のみ追加 |

### Sprint 7 内で対応する review 区分

- **HIGH** (in-sprint 修正必須): NOT NULL バックフィル漏れ、auth flow の `course_slug` 検証バイパス、dashboard のコース漏洩（他者コースのデータが見える）
- **MEDIUM/LOW**: `docs/superpowers/specs/2026-06-1X-sprint-7-followups.md` に切り出し

### Sprint 8 以降の候補（follow-up doc 化想定）

1. `POST /api/admin/users/{id}/enrollments` — admin 経由の追加 enroll
2. `scripts/seed_embeddings.py` の `source_ref` をコース付き形式へ
3. `ai-era-se` Phase 2-4 投入
4. broadcast 通知のコーススコープ化
5. 採点ジョブの非同期化、curriculum 編集機能（Sprint 6 follow-up からのキャリーオーバー）
6. Playwright headless 環境整備（Sprint 5 INFRA carry-over）

---

## 6. 動作確認手順（実装後）

```bash
# 1. DB マイグレーション
make migrate

# 2. （任意）RAG 再シード（既存方式、source_ref 形式は維持）
make seed-embeddings

# 3. 開発サーバ
make dev

# 4. 手動確認フロー
# - /login → 新規登録 → 「AI時代SE育成カリキュラム」選択
# - /courses → SE コース選択 → Phase 1（8 課題）でチャット・提出
# - 既存ユーザは ai-driven-dev のデータがそのまま見えること
# - admin で /admin/users/{id} → コース切替セレクタで両方の dashboard 確認
```

---

## 7. 関連

- 起点: `docs/superpowers/plans/2026-06-09-sprint-7-multi-course-handoff.md`（Sprint 7 完了時に削除）
- シラバス原文: `/Volumes/4TB_NAS/syllabus_weekly_12months.md`（Phase 1〜4 の週次テーブル・評価基準・AI活用ルール）
- 前 Sprint: `docs/superpowers/specs/2026-06-09-sprint-6-bidirectional-comm-design.md`
- 前 Sprint follow-up: `docs/superpowers/specs/2026-06-09-sprint-6-followups.md`
