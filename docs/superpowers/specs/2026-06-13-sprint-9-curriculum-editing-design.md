# Sprint 9 — curriculum 編集機能 (admin GUI) アーキテクチャ設計

**作成日:** 2026-06-13
**前提 HEAD:** `5dbc6a6` (chore(infra): vite 5→8 + vitest 3→4 upgrade)
**前提テスト:** backend 370 passed / frontend 83 passed / E2E 4 passed

---

## 1. ゴールと非目標

### ゴール

admin が GUI から curriculum (タスク本文・skill_tags・deliverable・week_label・Phase title/goal/system_prompt) を編集できる admin UI を追加する。DB を curriculum の唯一の真実とし、Python レジストリ (`backend/app/data/courses/{ai_driven_dev,ai_era_se}.py`) は初期 seeder に格下げ。draft → publish 二段階で公開し、誤公開を防ぐ。

### 含むもの (in-scope)

1. 新規テーブル `curriculum_phases` / `curriculum_tasks` の Alembic マイグレーション
2. 既存 Python レジストリを初回 seeder として DB に投入 (マイグレーション内で dict literal をコピペ、registry import に依存しない)
3. 起動時 in-process キャッシュへの DB ロード、`get_course()` をキャッシュ経由に切替（同期 API シグネチャを保持）
4. 編集サービス `app/services/curriculum_edit.py`（draft の put、course 単位の publish / discard）
5. admin API:
   - `GET /api/admin/curriculum/` — 一覧 (draft 件数バッジ用)
   - `GET /api/admin/curriculum/{slug}` — 詳細 (全 phase / task の published + draft)
   - `PUT /api/admin/curriculum/{slug}/phases/{phase_no}` — phase の draft 更新
   - `PUT /api/admin/curriculum/{slug}/phases/{phase_no}/tasks/{task_no}` — task の draft 更新
   - `POST /api/admin/curriculum/{slug}/publish` — draft を全て公開
   - `POST /api/admin/curriculum/{slug}/draft` (DELETE 相当) — draft 破棄
6. admin frontend:
   - `/admin/curriculum` 一覧ビュー (draft 件数バッジ)
   - `/admin/curriculum/:slug` 編集ビュー (debounce 自動保存 + Publish/Discard ボタン)
7. **skill_tags / system_prompt の再計算**: 公開時にキャッシュ再構築、weakness / recommendation は常に最新 task 定義を参照、submission には snapshot しない

### 含まないもの (out-of-scope / follow-up)

- Phase / Task の追加・削除・並び替え (Sprint 10 候補)
- Course 自体の追加・削除 (同上)
- 編集履歴 / バージョン管理
- 別プロセス間のキャッシュ同期 (multi-worker 運用の follow-up)
- embeddings の自動再生成 (`make seed-embeddings` を別途実行する運用)
- 編集中の楽観ロック / 同時編集競合解決 (admin 1 名運用前提)
- 専用 RBAC (Sprint 4 の `is_admin` をそのまま使用)

### 非機能要件

- backend 既存 370 件は全て緑、新規 ≈25 件、目標 **backend ≈395 passed**
- frontend 既存 83 件は全て緑、新規 ≈11 件、目標 **frontend ≈94 passed**
- Playwright E2E 既存 4 件は全て緑、新規 1 件、目標 **E2E 5 passed**
- Alembic マイグレーションは `alembic downgrade -1` で完全に巻き戻せる
- 既存 `COURSE_REGISTRY` が import される箇所の挙動は不変

---

## 2. データモデル

### 新規テーブル

#### `curriculum_phases` — Phase の published / draft 両状態を 1 行に保持

| 列 | 型 | 説明 |
|---|---|---|
| `id` | UUID | PK |
| `course_id` | UUID NOT NULL | FK `courses(id)` ON DELETE RESTRICT |
| `phase_no` | INTEGER NOT NULL | Phase 番号 (1-indexed) |
| `title` | TEXT NOT NULL | published 値 (runtime が読む) |
| `goal` | TEXT NOT NULL | published |
| `system_prompt` | TEXT NOT NULL | published |
| `draft_title` | TEXT NULL | NULL = 未編集、非 NULL = 次 publish 候補 |
| `draft_goal` | TEXT NULL | 同上 |
| `draft_system_prompt` | TEXT NULL | 同上 |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | 直近 PUT 時刻 |
| | | UNIQUE (`course_id`, `phase_no`) |

#### `curriculum_tasks` — Task の published / draft 両状態を 1 行に保持

| 列 | 型 | 説明 |
|---|---|---|
| `id` | UUID | PK |
| `phase_id` | UUID NOT NULL | FK `curriculum_phases(id)` ON DELETE CASCADE |
| `task_no` | INTEGER NOT NULL | Task 番号 (1-indexed) |
| `title` | TEXT NOT NULL | published |
| `description` | TEXT NOT NULL | published |
| `skill_tags` | JSONB NOT NULL | published (`list[str]`) |
| `deliverable` | TEXT NULL | published |
| `week_label` | TEXT NULL | published |
| `draft_title` | TEXT NULL | NULL = 未編集 |
| `draft_description` | TEXT NULL | 同上 |
| `draft_skill_tags` | JSONB NULL | 同上 |
| `draft_deliverable` | TEXT NULL | 空文字 sentinel で "明示的に空" を表現 |
| `draft_week_label` | TEXT NULL | 同上 |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| | | UNIQUE (`phase_id`, `task_no`) |

### 設計判断 (確定済)

- **同一行 draft / published 方式**: publish は単純 UPDATE `SET title = COALESCE(draft_title, title), draft_title = NULL`、読み取り join 不要
- **`skill_tags` = JSONB**: pydantic / SQLAlchemy で `list[str]` ↔ JSON 変換が自然 (text[] の場合 GIN index 検索が高速だが現状そういうクエリは無し)
- **`deliverable` / `week_label` の sentinel**: NULL = 未編集、空文字 `""` = "明示的に空にしたい"。published は NULL もあり得るが、draft 列で `""` を区別する規約
- **`progress.total_tasks` への影響**: 編集スコープに add/delete を含まないので不変
- **`submissions.task_no` への影響**: 同上、不変
- **`embeddings` への影響**: title / description が変わると content がずれる。runtime には影響しない (RAG 検索結果が古いだけ)。admin が手動で `make seed-embeddings` 実行する運用

### Alembic マイグレーション

リビジョン名: `20260613_<rev>_sprint9_curriculum_editing.py`、`down_revision = <現 head>`

#### upgrade 手順

1. `curriculum_phases` テーブル作成
2. `curriculum_tasks` テーブル作成
3. **初回 seed**: マイグレーション内に dict literal で `COURSE_REGISTRY` の値をコピペ、`curriculum_phases` / `curriculum_tasks` に INSERT (draft は全て NULL)
   - docstring に「seed 値はマイグレーション作成時点でフリーズ、以後の registry 変更は反映されない」と明記
   - registry import に依存しないため、将来 Python ファイル削除しても過去 migration は動く

#### downgrade

`curriculum_tasks` → `curriculum_phases` を drop。`courses` テーブルは Sprint 7 migration が所有、ここでは触らない。

---

## 3. ランタイム / キャッシュ

### `get_course()` の挙動切替

- **現状**: `app/data/courses/__init__.py` の `get_course(slug) -> CourseData` が in-memory `COURSE_REGISTRY` 辞書を直接 lookup (同期 API)
- **Sprint 9 後**: 同じ同期 API のままで内部実装が in-process **キャッシュ**を返す。キャッシュは DB から構築済みの `CourseData` を保持

### 新規モジュール `app/data/courses/runtime.py`

```
_CACHE: dict[str, CourseData]  # process-local
async def reload_from_db(db: AsyncSession) -> None
    """全 published フィールドを SELECT → build CourseData → _CACHE 置換。"""
async def reload_course(db: AsyncSession, slug: str) -> None
    """1 course だけを差し替え (publish 後に呼ぶ)。"""
def get_cached_course(slug: str) -> CourseData
    """同期 API。CourseNotFoundError on miss."""
```

`app/data/courses/__init__.py`:
- `get_course(slug)` → `get_cached_course(slug)` に rewire
- `COURSE_REGISTRY` → cache の dict view として legacy alias で保持 (test で参照される)

### ライフサイクル

1. **app 起動 (lifespan)**: `reload_from_db(db)` を 1 度実行。`_CACHE` が DB の published 値で満たされる
2. **publish 完了時**: 当該 course の CourseData だけを再構築して `_CACHE[slug]` を差し替え (`reload_course(db, slug)`)
3. **discard draft**: DB 変更のみ、キャッシュ更新不要 (runtime は published を読んでいるため)

### `lifespan` への組み込み

`app/main.py` 既存 lifespan (arq プール init/close) に、起動直後の `reload_from_db()` を追加。**curriculum_phases が 0 行ならエラーで起動失敗** (Alembic migration 未実行を明示)。

### multi-worker

dev / docker-compose は uvicorn 単一プロセス前提なので process-local キャッシュで十分。Sprint 9 follow-up doc に「将来 multi-worker 時は Redis pub/sub でキャッシュ無効化」を follow-up として記録。

### テスト時の注意

- `conftest.py` の `db_session` fixture は `courses` テーブル再 seed と同じ仕組みで、`curriculum_phases` / `curriculum_tasks` も再 seed する
- 各テスト前に `reload_from_db()` を呼んで cache を test DB の内容に合わせる
- `_DEFAULT_AI_DRIVEN_DEV_PHASE_ID` fixture を追加 (FK 参照用)

### 既存呼び出し側への影響

| 呼び出し側 | 影響 |
|---|---|
| `app/services/{enrollment,submission,dashboard,recommendation,progress_summary,progress}.py` | 変更不要 — `get_course()` シグネチャ不変 |
| `app/core/course_deps.py` | 変更不要 |
| `app/api/{auth,curriculum}.py` | 変更不要 |
| `app/data/curriculum.py` (legacy shim) | 変更不要 |

Sprint 7 で `get_course()` 経由に集約しておいた設計が活きる。

---

## 4. API サーフェス

### 新規ルート `app/api/admin/curriculum.py`

prefix `/api/admin/curriculum`、`get_current_admin` 保護。

| メソッド + パス | 役割 | レスポンス型 |
|---|---|---|
| `GET /` | 編集可能 course 一覧 (slug, title, draft 件数) | `AdminCurriculumCourseList` |
| `GET /{slug}` | 1 course の全 phase + 全 task の published + draft | `AdminCurriculumCourseDetail` |
| `PUT /{slug}/phases/{phase_no}` | Phase の draft 更新 | `AdminPhaseEditOut` |
| `PUT /{slug}/phases/{phase_no}/tasks/{task_no}` | Task の draft 更新 | `AdminTaskEditOut` |
| `POST /{slug}/publish` | course の全 draft を published に昇格 + キャッシュ再構築 | `AdminCurriculumPublishOut` |
| `POST /{slug}/draft` | 当該 course の draft をすべて discard | `204 No Content` |

### Schemas (`app/schemas/admin_curriculum.py` 新規)

```python
class AdminCurriculumCourseSummary(BaseModel):
    slug: str
    title: str
    pending_draft_count: int

class AdminCurriculumCourseList(BaseModel):
    items: list[AdminCurriculumCourseSummary]

class AdminTaskEditOut(BaseModel):
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
    slug: str
    title: str
    phases: list[AdminPhaseEditOut]

class AdminTaskUpdateRequest(BaseModel):
    """PUT body — exclude_unset セマンティクス:
    - フィールド省略 (`field not in body`) = 変更なし
    - 明示 None = draft をクリア
    - 明示値 = draft を設定"""
    title: str | None = None
    description: str | None = None
    skill_tags: list[str] | None = None
    deliverable: str | None = None
    week_label: str | None = None

class AdminPhaseUpdateRequest(BaseModel):
    title: str | None = None
    goal: str | None = None
    system_prompt: str | None = None

class AdminCurriculumPublishOut(BaseModel):
    slug: str
    published_phase_count: int
    published_task_count: int
    published_at: datetime
```

### バリデーション

| フィールド | 制約 |
|---|---|
| `title` | 1〜200 文字 |
| `description` | 1〜2000 文字 |
| `system_prompt` | 1〜8000 文字 (Claude API トークン上限ガード) |
| `goal` | 1〜500 文字 |
| `skill_tags` | 配列長 ≤ 10、各要素長 ≤ 50、サーバ側で順序維持 dedup |
| `deliverable` / `week_label` | 0〜200 文字 (空文字 OK) |

### エラーマッピング

| 状況 | ステータス |
|---|---|
| `is_admin=False` | 403 (既存 `get_current_admin`) |
| 未知 `course_slug` | 404 |
| 未知 `phase_no` / `task_no` | 404 |
| バリデーション失敗 | 422 |
| `POST /publish` で draft 0 件 | 200 + `published_*_count=0` (idempotent) |

### Rate limit

新規 settings:
- `admin_curriculum_write_rate_limit = "120/minute"` (PUT 系、debounce 自動保存対応)
- `admin_curriculum_publish_rate_limit = "10/minute"` (POST publish は重いので絞る)

---

## 5. フロントエンド

### 新規ビュー

#### `/admin/curriculum` (`AdminCurriculumListView.vue`)

- onMount: `api.adminCurriculumList()` → 一覧取得
- カード形式で course 別に表示: `title` / `pending_draft_count` バッジ (0 件 hidden、≥1 で色付き)
- "編集する →" ボタンで `/admin/curriculum/:slug` へ遷移

#### `/admin/curriculum/:courseSlug` (`AdminCurriculumEditView.vue`)

レイアウト:

```
┌─ Course: AI駆動型開発 補足カリキュラム ─────────────────┐
│ [3 件の draft あり]  [Publish] [Discard drafts]      │
├─────────────────────────────────────────────────────┤
│ Phase 1: 開発環境の近代化                            │
│   ── Phase 情報 (折りたたみ) ──                       │
│      title    [input]                                │
│      goal     [textarea]                             │
│      system_prompt [textarea, lines=8]               │
│   ── Task 1 (折りたたみ) ──                           │
│      title       [input]   (✏ if draft)              │
│      description [textarea]                          │
│      skill_tags  [tag chips + add input]             │
│      deliverable [input]                             │
│      week_label  [input]                             │
│   ── Task 2 ...                                      │
│ Phase 2 ...                                          │
└─────────────────────────────────────────────────────┘
```

### 編集 UX

- **インライン edit**: 入力直接編集、500ms debounce で PUT 自動発火 (明示的 "保存" ボタンなし)
- **draft インジケータ**: `draft_*` 非 NULL のフィールド横に ✏️ アイコン、現値との diff を hover で表示
- **draft 件数バッジ**: course header に「N 件の draft あり」(フィールド単位の draft 数を集計)
- **Publish**: 確認モーダル「N 個のフィールドを公開します」→ `POST /publish`、成功時に全 ✏️ が消える
- **Discard**: 確認モーダル「N 個の draft を破棄します」→ `POST /draft`、成功時に draft が全クリア

### 新規ストア `stores/admin_curriculum.ts`

```ts
state:
  list: AdminCurriculumCourseSummary[]
  detail: AdminCurriculumCourseDetail | null
  pendingPuts: Set<string>  // "phases/1/tasks/2" 等
  saveError: string | null

actions:
  fetchList()
  fetchDetail(slug)
  putPhase(slug, phaseNo, payload)
  putTask(slug, phaseNo, taskNo, payload)
  publish(slug)
  discardDrafts(slug)
```

### `lib/api.ts` 追加

```ts
adminCurriculumList: () => Promise<AdminCurriculumCourseList>
adminCurriculumDetail: (slug) => Promise<AdminCurriculumCourseDetail>
adminPutPhase: (slug, phaseNo, body) => Promise<AdminPhaseEditOut>
adminPutTask: (slug, phaseNo, taskNo, body) => Promise<AdminTaskEditOut>
adminPublishCurriculum: (slug) => Promise<AdminCurriculumPublishOut>
adminDiscardCurriculumDrafts: (slug) => Promise<void>
```

### Router 追加 (`router/admin.ts`)

```ts
{ path: '/admin/curriculum', name: 'admin-curriculum-list',
  component: AdminCurriculumListView, meta: { requiresAdmin: true } }
{ path: '/admin/curriculum/:courseSlug', name: 'admin-curriculum-edit',
  component: AdminCurriculumEditView, props: true, meta: { requiresAdmin: true } }
```

`AdminLayout.vue` の nav に「カリキュラム編集」リンク追加。

### コンポーネント分割

- `AdminCurriculumEditView.vue`: トップレベル、course 取得 + publish/discard
- `CurriculumPhaseEditor.vue`: 1 Phase 分の編集 UI
- `CurriculumTaskEditor.vue`: 1 Task 分の編集 UI (debounced PUT)
- `SkillTagInput.vue`: タグ chip + 新タグ追加 input

### 採点 / 受講者画面への影響

- Publish 直後はキャッシュ再構築でランタイムに伝播
- 受講者チャット中の場合: 送信済み system message は古いまま (Anthropic 側に送信済)、次メッセージから新 prompt 適用
- task title 変更: 受講者の Phase 一覧 / TaskSubmissionCard が次回 fetch で更新

これを正常動作として spec に明記。admin GUI で "公開すると受講者の表示が即座に切り替わります" の注意を表示。

---

## 6. テスト・リスク・残課題

### Backend テスト戦略 (≈25 件)

| ファイル | 件数 | 内容 |
|---|---|---|
| `test_models_sprint9.py` | 4 | curriculum_phases / curriculum_tasks の UNIQUE / FK CASCADE |
| `test_curriculum_seed_migration.py` | 3 | マイグレーション seed が COURSE_REGISTRY と一致 |
| `test_curriculum_cache.py` | 5 | reload_from_db / get_cached_course / publish 後の差し替え |
| `test_curriculum_edit_service.py` | 6 | put_phase_draft / put_task_draft / publish / discard / exclude_unset / バリデーション |
| `test_admin_curriculum_api.py` | 7 | GET 一覧 / 詳細 / PUT phase / PUT task / POST publish / POST draft DELETE / RBAC 403 |

#### conftest 改修

- `db_session` fixture に curriculum_phases / curriculum_tasks の再 seed を追加
- 各テスト前に `reload_from_db()` 呼び出し → cache を test DB に合わせる
- `_DEFAULT_AI_DRIVEN_DEV_PHASE_ID` fixture を追加 (FK 参照用)

### Frontend テスト戦略 (≈11 件)

| ファイル | 件数 |
|---|---|
| `admin_curriculum.store.spec.ts` | 4 |
| `AdminCurriculumListView.spec.ts` | 2 |
| `AdminCurriculumEditView.spec.ts` | 3 |
| `CurriculumTaskEditor.spec.ts` | 2 |

### Playwright E2E (+1 件)

`frontend/e2e/admin-curriculum.spec.ts`:

- admin でログイン → `/admin/curriculum/ai-driven-dev` → Task 1 title を編集 → debounce で PUT → publish ボタン → 受講者でログイン → `/courses/ai-driven-dev/phases/1` で title が新値に変わったことを確認

### リスク一覧

| リスク | 影響 | 緩和策 |
|---|---|---|
| Alembic seed が `COURSE_REGISTRY` を import → 将来レジストリ変更時にマイグレーション再実行で挙動変化 | 既存環境で downgrade → upgrade すると過去版が DB に流れる | docstring に「seed 値は migration 作成時点でフリーズ」と明記。dict literal をコピペ、registry import なし |
| publish 後のキャッシュ差し替えが multi-worker で不整合 | dev / docker は単一プロセスなので影響なし | follow-up doc に Redis pub/sub 無効化を記載 |
| debounce 自動保存が連続変更で N 回 PUT | rate limit に引っかかる | 500ms debounce + 同一 task 内で「最新値だけ送る」キャンセル可能タイマー |
| skill_tags を全削除して publish | weakness 計算が NaN | 既存 `len(tags) == 0` フォールバックで has_enough_data=False、追加実装不要 |
| admin が system_prompt に巨大文字列貼り付け | Claude API トークン上限超過 / コスト急増 | バリデーション 8000 char ハードキャップ |
| 編集中に別 admin が同じ task を保存 | 後勝ち (最後の PUT が残る) | admin 1 名運用前提で許容、follow-up doc に「同時編集競合」を記載 |

### Sprint 9 内で対応する review 区分

- **HIGH** (in-sprint 修正必須):
  - seed migration の値が現本番の Python 値と不一致
  - PUT の exclude_unset セマンティクス漏れ
  - publish が他 course を巻き込む
- **MED / LOW**: `docs/superpowers/specs/2026-06-1X-sprint-9-followups.md` に切り出し

### Sprint 10 以降の候補

1. Task / Phase の追加・削除・並び替え
2. Course 自体の追加・削除
3. 編集履歴 / バージョン管理 (`curriculum_versions` テーブル)
4. multi-worker 対応のキャッシュ無効化 (Redis pub/sub)
5. embeddings の自動再生成 (publish 時に arq でバックグラウンド `seed_embeddings`)
6. 編集中の楽観ロック (`updated_at` を ETag として活用)
7. システムプロンプト変更が in-flight chat に与える影響を抑える「セッション固定」モード

---

## 7. 動作確認手順 (実装後)

```bash
# 1. DB マイグレーション (seed 含む)
make migrate

# 2. 開発サーバ
make dev

# 3. 手動確認フロー
# - admin でログイン → /admin/curriculum
# - "AI駆動型開発" カードに 0 件バッジが見える (初期 seed のみ)
# - /admin/curriculum/ai-driven-dev → Phase 1 Task 1 title を編集
# - 500ms 後にバッジが「1 件の draft あり」に変わる
# - [Publish] → 確認モーダル → 1 件公開
# - 受講者ログイン → /courses/ai-driven-dev/phases/1 で title が新値
```

---

## 8. 関連

- 前 sprint: `docs/superpowers/specs/2026-06-10-sprint-7-multi-course-architecture-design.md` (Sprint 7 マルチコース化)
- 前 follow-up: `docs/superpowers/specs/2026-06-11-sprint-7-followups.md` (Sprint 7 follow-up + Sprint 8 採点非同期化)
- 現状の curriculum 定義: `backend/app/data/courses/{ai_driven_dev,ai_era_se,types}.py`
- 現状のレジストリ API: `backend/app/data/courses/__init__.py`
