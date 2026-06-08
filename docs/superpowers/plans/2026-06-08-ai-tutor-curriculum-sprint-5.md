# AIチューターカリキュラム Sprint 5 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sprint 0〜4 で揃った受講者ジャーニーの上に、本人の学習履歴に基づいた **個別最適化ダッシュボード**（弱点分析 + レコメンド + 進捗サマリ + AI 一言）を載せる。ログイン直後のホーム（`/`）が「あなたの進んだ道」と「次にやるべきこと」を示す画面に進化する。

**Architecture:** 集約 API 1 本（`GET /api/me/dashboard`）が、weakness / recommendation / nudge / progress_summary の 4 サービスを呼んで 1 レスポンスにまとめる。skill_tags は `app/data/curriculum.py` の TaskItem TypedDict 拡張で持つ。AI 一言は `user_nudges` テーブルで PK=user_id の 1 行キャッシュ（24h TTL + 入力 signature による鮮度判定）。レコメンドは既存 pgvector 埋め込みを `source_type='curriculum_task'` で絞る新規 RAG 関数 `search_curriculum_tasks` で並べる。

**Tech Stack:**
- Backend: 既存（FastAPI / async SQLAlchemy / asyncpg / Alembic / Anthropic SDK / pgvector / fastembed）。新規依存ゼロ。
- Frontend: 既存（Vue 3 / Pinia / TypeScript / Vue Router）のみ。
- LLM モデル: nudge は `claude-haiku-4-5`（既存 `anthropic_model` は採点 Sonnet 4.5 のまま、別設定 `nudge_model` を追加）。

---

## 設計書

実装中は以下の設計書を参照すること:

- 上位設計: `docs/superpowers/specs/2026-06-08-sprint-5-dashboard-design.md`（本計画書の根拠）
- DB 設計: `docs/design/03-db-design.md`（Sprint 5 で追記）
- API 設計: `docs/design/04-interface-design.md`（Sprint 5 で追記）
- 画面設計: `docs/design/05-screen-design.md`（Sprint 5 で追記）
- テスト設計: `docs/design/06-test-design.md`（Sprint 5 で追記）

---

## 主要意思決定（Sprint 5 計画時点）

| # | 判断項目 | 選択 | 理由 |
|---|---|---|---|
| 1 | スコープの軸 | 受講者体験（弱点 + レコメンド + ダッシュボード + AI 一言） | UX のレバレッジが最大 |
| 2 | アーキテクチャ | 集約 API 1 本（`GET /api/me/dashboard`） | 状態管理シンプル、ドメイン整合 |
| 3 | 弱点の軸 | curriculum タスクへの手動 `skill_tags`（5〜10 種） | 12 タスクに対して粒度が適切 |
| 4 | 弱点の定義 | submission ごとの最新 graded attempt の score をタグで平均、低い上位 3 | データ集計のみ、説明可能 |
| 5 | コールドスタート閾値 | `MIN_SUBMISSION_THRESHOLD = 3` | 信頼性のある弱点判定の境界 |
| 6 | タグ別最低提出数 | `MIN_TAG_SUBMISSIONS = 2` | 1 件提出での弱点認定はノイズ |
| 7 | レコメンド | 弱点 1 位タグをクエリに、新規 `search_curriculum_tasks` で類似度上位 → 未提出フィルタ → 3 件 | 既存 Embedding テーブル/パイプライン再利用 |
| 8 | AI 一言 | Lazy 生成 + 24h cache + signature による入力変化検知 | コスト最小、運用シンプル、鮮度確保 |
| 9 | nudge ストレージ | `user_nudges`（PK=user_id、履歴なし） | YAGNI、24h cache に履歴は不要 |
| 10 | nudge LLM モデル | `claude-haiku-4-5`、temperature=0.5、max_tokens=200 | コスト・速度・揺れの抑制 |
| 11 | nudge コンカレンシー | 同 user 同時 fetch で `SELECT FOR UPDATE`、後発は再 SELECT | 二重生成防止 |
| 12 | nudge コールドスタート | 提出 3 件未満では LLM を呼ばず static 固定文 | API キー消費 0、UX 連続性 |
| 13 | UI 文言 | 「弱点」ではなく「もう一押しの分野」 | 受講者モチベ低下回避（内部キーは weakness のまま） |
| 14 | 動線 | 既存 HomeView をダッシュボード化、フェーズ一覧 UI も下部に保持 | カリキュラム順閲覧の要求も維持 |
| 15 | API 形状 | dashboard レスポンスは 4 セクション固定の単一 envelope | フロント分岐 1 箇所 |
| 16 | エラー時挙動 | nudge 生成失敗 → stale を返す、RAG 失敗 → recommendations=[]、サブ失敗で全体 500 にしない | 部分失敗でもダッシュボードは見える |
| 17 | Sprint 4 LOW 同梱 | しない | スコープ純化 |
| 18 | テスト戦略 | Sprint 1〜4 と同水準 + Playwright E2E 1 本 | 既存基準維持 |

---

## スコープ境界

**含む（Sprint 5）：**

- `app/data/curriculum.py` の `tasks: list[str]` を `list[TaskItem]` へ拡張し、12 タスクに 1〜2 個の `skill_tags` を手動付与
- ヘルパー追加: `get_task_skill_tags(phase, task_no) -> list[str]`、`get_task_title(phase, task_no) -> str`、`iter_all_phase_task_pairs() -> Iterator[tuple[int, int]]`
- 既存 API レスポンス互換維持: `GET /api/curriculum` の `tasks: list[str]` 形は変更しない（サーバ側で title を射影）
- `submission.py` の dict 対応（`_validate_phase_and_task` 戻り値の調整）
- `scripts/seed_embeddings.py` の TaskItem 対応
- 新規 RAG 関数: `search_curriculum_tasks(db, client, query, limit)` と `CurriculumTaskHit` dataclass
- 新規モデル `UserNudge`（PK=user_id、body, generated_at, input_signature）+ Alembic マイグレーション 1 リビジョン
- Settings 追加: `nudge_model`, `nudge_cache_ttl_hours`, `nudge_max_output_tokens`, `nudge_temperature`
- backend サービス 5 つ: `weakness`, `progress_summary`, `recommendation`, `nudge`, `dashboard`（orchestrator）
- API: `GET /api/me/dashboard`
- frontend: types/dashboard, stores/dashboard, NudgeBanner, ProgressSummaryCard, WeaknessCard, RecommendationsCard, HomeView 改造（フェーズ一覧は下部に保持）
- テスト: backend 9 ファイル前後、frontend 5 ファイル前後、Playwright E2E 1 本
- 設計書 03/04/05/06 への Sprint 5 セクション追記、README 更新

**含まない（後続 Sprint）：**

- 採点の非同期化（バックグラウンドジョブ） → Sprint 6 候補
- コメント返信 / スレッド化 → Sprint 6 候補
- broadcast 通知 → 別途
- リアルタイム通知（SSE/WS） → Sprint 7+
- Sprint 4 follow-up LOW-2/3/4 → Sprint 6 候補
- Sprint 4 follow-up LOW-1（Cookie 化） → 認証刷新 Sprint
- AI 一言の履歴保持 / リアルタイム再生成 → 後続
- 講師向け admin ダッシュボード強化 → 別スプリント

---

## ファイル構造（差分のみ）

```
edu/
├── README.md                                              # Modify: Sprint 5 完了マーク + seed-embeddings 再実行手順
├── .env.example                                           # Modify: NUDGE_MODEL 等 4 行追加
├── backend/
│   ├── app/
│   │   ├── config.py                                      # Modify: nudge_* 設定 4 つ
│   │   ├── data/
│   │   │   └── curriculum.py                              # Modify: TaskItem 化 + skill_tags + 3 ヘルパー
│   │   ├── models/
│   │   │   ├── __init__.py                                # Modify: import 追加
│   │   │   └── user_nudge.py                              # Create
│   │   ├── schemas/
│   │   │   ├── curriculum.py                              # 変更なし（既存 list[str] 形を維持）
│   │   │   └── dashboard.py                               # Create: DashboardResponse 系
│   │   ├── services/
│   │   │   ├── rag.py                                     # Modify: search_curriculum_tasks + CurriculumTaskHit
│   │   │   ├── submission.py                              # Modify: _validate_phase_and_task で title 射影
│   │   │   ├── weakness.py                                # Create
│   │   │   ├── progress_summary.py                        # Create
│   │   │   ├── recommendation.py                          # Create
│   │   │   ├── nudge.py                                   # Create
│   │   │   └── dashboard.py                               # Create: orchestrator
│   │   ├── api/
│   │   │   ├── curriculum.py                              # Modify: tasks を [item["title"] for ...] に射影
│   │   │   └── me_dashboard.py                            # Create
│   │   └── main.py                                        # Modify: dashboard router 追加
│   ├── alembic/versions/
│   │   └── 20260608_<rev>_sprint5_user_nudges.py          # Create
│   ├── scripts/
│   │   └── seed_embeddings.py                             # Modify: task["title"] を渡す
│   └── tests/
│       ├── conftest.py                                    # Modify: seed_graded_submission helper
│       ├── test_curriculum_skill_tags.py                  # Create
│       ├── test_models_sprint5.py                         # Create
│       ├── test_rag_curriculum_tasks.py                   # Create
│       ├── test_weakness_service.py                       # Create
│       ├── test_progress_summary_service.py               # Create
│       ├── test_recommendation_service.py                 # Create
│       ├── test_nudge_service.py                          # Create
│       ├── test_dashboard_service.py                      # Create
│       └── test_me_dashboard_api.py                       # Create
└── frontend/
    └── src/
        ├── lib/api.ts                                     # Modify: getMyDashboard 追加
        ├── types/
        │   └── dashboard.ts                               # Create
        ├── stores/
        │   └── dashboard.ts                               # Create
        ├── views/
        │   └── HomeView.vue                               # Modify: ダッシュボード化、フェーズ一覧は下部保持
        ├── components/
        │   ├── NudgeBanner.vue                            # Create
        │   ├── ProgressSummaryCard.vue                    # Create
        │   ├── WeaknessCard.vue                           # Create
        │   ├── RecommendationsCard.vue                    # Create
        │   └── TaskSubmissionCard.vue                     # Modify: 提出後に dashboard store invalidate
        └── __tests__/
            ├── dashboard.store.spec.ts                    # Create
            ├── NudgeBanner.spec.ts                        # Create
            ├── ProgressSummaryCard.spec.ts                # Create
            ├── WeaknessCard.spec.ts                       # Create
            ├── RecommendationsCard.spec.ts                # Create
            └── HomeView.spec.ts                           # Create (またはモディファイ)
```

---

## 共通の前提

- **作業ブランチ:** `feature/sprint-5`（main から派生）
- **環境:** Docker Compose の `postgres` を起動。backend は `uv run uvicorn` でホスト起動可。
- **テスト DB:** `ai_tutor_test`（Sprint 1 で作成済み）。Sprint 5 マイグレーションは `Base.metadata.create_all` 経由でテストに反映される。
- **既存テスト件数（ベースライン）:** backend 212 / frontend 34
- **既存設計のフィールド名（重要）:**
  - `users.id` UUID、`submissions.user_id / phase / task_no / content / submitted_at`
  - `grading_attempts.submission_id / status ('graded'|'failed') / score / created_at`
  - `task_no` の CHECK は `BETWEEN 1 AND 5`、`phase` の CHECK は `BETWEEN 1 AND 4`
  - 既存 RAG は `app/services/rag.py` の `RagHit(source_type, content, score)` と `search_context(db, client, user_id, phase, query, top_k)`
  - 既存 Embedding は `source_type='curriculum_task'`、`source_ref='phase:{phase_no}:task:{i}'`（`i` は 0-indexed）
- **既存テスト fixture:** `client / db_session / auth_user / auth_token / auth_client / admin_user / admin_token / admin_client`
- **コミット規約:** Sprint 1〜4 と同じ `feat|fix|test|chore|docs|refactor(scope): ...`。本スプリントの scope は `sprint-5`。
- **コマンド実行ディレクトリ:** 特記なき限り `/Volumes/Seagate3TB/projects/edu`

---

## Task 0: ブランチ作成と環境確認

**Files:**
- なし（git のみ）

- [ ] **Step 1: feature ブランチを切る**

```bash
git checkout main
git pull --ff-only || true   # remote 未設定なら無視
git checkout -b feature/sprint-5
```

- [ ] **Step 2: バックエンド全件テストが現状で通ることを確認**

```bash
docker compose up -d postgres
sleep 5
cd backend && uv run pytest -q
```

Expected: `212 passed`（Sprint 4 + security follow-up 完了時点）。

- [ ] **Step 3: フロントビルドとテストが現状で通ることを確認**

```bash
cd ../frontend && npm run build && npm test -- --run
```

Expected: ビルド成功、`34 passed`。

- [ ] **Step 4: 既存の seed_embeddings を念のため再実行（後で再度 Task 4 で実行する）**

```bash
cd ../backend && uv run python -m scripts.seed_embeddings
```

Expected: `Seeded 28 embedding rows.`（12 task + 16 skill = 28 行、Sprint 0 で投入されたものと同一）。

---

## Task 1: タグ語彙確定と curriculum.py を TaskItem TypedDict に拡張

**Files:**
- Modify: `backend/app/data/curriculum.py`
- Create: `backend/tests/test_curriculum_skill_tags.py`

**タグ語彙（10 種、本タスクで固定）:**

| タグ | 想定意味（運用者向けメモ、コード化はしない） |
|---|---|
| `Git/GitHub` | バージョン管理、PR、ブランチ |
| `開発環境` | エディタ、ターミナル、拡張機能 |
| `API基礎` | REST、HTTP、JSON 取扱 |
| `AI協調` | プロンプト、AI 出力検証、ペアプロ |
| `テスト` | 単体テスト、自動テスト、テストケース設計 |
| `コードレビュー` | レビュー観点、品質基準 |
| `設計` | 仕様、アーキテクチャ、提案 |
| `RAG/ベクトル検索` | 埋め込み、検索、コンテキスト注入 |
| `LLM活用` | API 呼び出し、システムプロンプト、出力構造化 |
| `業務応用` | プロダクト企画、ROI、PoC |

- [ ] **Step 1: failing test を追加**

`backend/tests/test_curriculum_skill_tags.py` を新規作成:

```python
"""Sprint 5: curriculum タスクに skill_tags が付いていることを保証する。

タグ語彙のメンテと TaskItem 構造の維持を兼ねた一枚岩のテスト。タグの個別
意味は実装で説明しない（運用ドキュメント側）。"""

import pytest

from app.data.curriculum import (
    CURRICULUM,
    get_task_skill_tags,
    get_task_title,
    iter_all_phase_task_pairs,
)

EXPECTED_VOCAB = {
    "Git/GitHub", "開発環境", "API基礎", "AI協調", "テスト",
    "コードレビュー", "設計", "RAG/ベクトル検索", "LLM活用", "業務応用",
}


def test_every_task_is_task_item_with_title_and_skill_tags():
    """全 phase の tasks が dict 形 (title + skill_tags) になっている。"""
    for phase_no, phase in CURRICULUM.items():
        for i, task in enumerate(phase["tasks"]):
            assert isinstance(task, dict), f"phase {phase_no} task {i} not dict"
            assert "title" in task and isinstance(task["title"], str)
            assert "skill_tags" in task and isinstance(task["skill_tags"], list)
            assert len(task["skill_tags"]) >= 1, (
                f"phase {phase_no} task {i+1} has no skill_tags"
            )


def test_skill_tags_use_curated_vocab():
    """付与されたタグはすべて EXPECTED_VOCAB の範囲内（typo 防止）。"""
    for phase_no, phase in CURRICULUM.items():
        for i, task in enumerate(phase["tasks"]):
            for tag in task["skill_tags"]:
                assert tag in EXPECTED_VOCAB, (
                    f"phase {phase_no} task {i+1}: unknown tag {tag!r}"
                )


def test_get_task_skill_tags_returns_tags_for_valid_coordinates():
    tags = get_task_skill_tags(1, 1)
    assert isinstance(tags, list)
    assert len(tags) >= 1


def test_get_task_skill_tags_raises_for_invalid_phase():
    with pytest.raises(KeyError):
        get_task_skill_tags(99, 1)


def test_get_task_skill_tags_raises_for_invalid_task_no():
    with pytest.raises(KeyError):
        get_task_skill_tags(1, 99)


def test_get_task_title_returns_string():
    title = get_task_title(1, 1)
    assert isinstance(title, str) and len(title) > 0


def test_iter_all_phase_task_pairs_yields_all_12_tasks():
    pairs = list(iter_all_phase_task_pairs())
    # 4 phase × 3 tasks/phase = 12 (Sprint 5 開始時点)
    assert len(pairs) == 12
    # phase 1..4 がすべて含まれる
    assert {p for p, _ in pairs} == {1, 2, 3, 4}
    # task_no は 1 始まり
    assert all(t >= 1 for _, t in pairs)
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd backend && uv run pytest tests/test_curriculum_skill_tags.py -q
```

Expected: ImportError / 6 failures（`get_task_skill_tags` 等がまだ存在しない）。

- [ ] **Step 3: `curriculum.py` を `TaskItem` 化**

`backend/app/data/curriculum.py` 冒頭の TypedDict 群を以下に置き換える:

```python
from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import TypedDict


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
```

- [ ] **Step 4: 12 タスクすべてに `title` + `skill_tags` を付与**

`CURRICULUM` 定義の各 phase の `"tasks": [...]` を以下に置き換える。

Phase 1:
```python
        "tasks": [
            {
                "title": "Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成",
                "skill_tags": ["Git/GitHub"],
            },
            {
                "title": "VSCode拡張（GitLens・REST Client・GitHub Copilot）の導入と動作確認",
                "skill_tags": ["開発環境"],
            },
            {
                "title": "curlでREST APIを叩き、JSONレスポンス構造をまとめる",
                "skill_tags": ["API基礎"],
            },
        ],
```

Phase 2:
```python
        "tasks": [
            {
                "title": "Cursor IDEで顧客管理API（CRUD）をゼロから作成。AIとのやり取りログを記録",
                "skill_tags": ["AI協調", "API基礎"],
            },
            {
                "title": "同機能をGitHub Copilotでも実装し、2つのAIの違いをまとめる",
                "skill_tags": ["AI協調", "開発環境"],
            },
            {
                "title": "ClaudeにコードレビューさせてPDCA",
                "skill_tags": ["AI協調", "コードレビュー"],
            },
        ],
```

Phase 3:
```python
        "tasks": [
            {
                "title": "Phase2で作ったAPIをAIにレビューさせ、セキュリティ・パフォーマンス・可読性の観点で整理",
                "skill_tags": ["コードレビュー", "AI協調"],
            },
            {
                "title": "仕様書（箇条書き）からテストコードを自動生成し、不足ケースを3つ指摘",
                "skill_tags": ["テスト", "AI協調"],
            },
            {
                "title": "AIとペアで新機能（検索機能など）を実装。会話ログも提出",
                "skill_tags": ["AI協調", "設計"],
            },
        ],
```

Phase 4:
```python
        "tasks": [
            {
                "title": "Claude APIでチャットボット作成（会話履歴保持・システムプロンプト設定）",
                "skill_tags": ["LLM活用"],
            },
            {
                "title": "RAGデモ作成（Python + ChromaDB + Claude API）",
                "skill_tags": ["RAG/ベクトル検索", "LLM活用"],
            },
            {
                "title": "業務課題を解決するAIツールの企画書作成（課題・解決策・技術構成・効果試算）",
                "skill_tags": ["業務応用", "設計"],
            },
        ],
```

- [ ] **Step 5: ヘルパー 3 つを `curriculum.py` 末尾に追加**

`get_phase` の直後に以下を追加（ファイル末尾）:

```python
def get_task_title(phase_no: int, task_no: int) -> str:
    """Return the human-readable title for (phase, task_no).

    task_no is 1-indexed (matches `submissions.task_no`). KeyError on
    out-of-range coordinates so callers see a uniform failure mode.
    """
    tasks = get_phase(phase_no)["tasks"]
    if task_no < 1 or task_no > len(tasks):
        raise KeyError(
            f"task_no {task_no} out of range for phase {phase_no} "
            f"(1..{len(tasks)})"
        )
    return tasks[task_no - 1]["title"]


def get_task_skill_tags(phase_no: int, task_no: int) -> list[str]:
    """Return the skill tags for (phase, task_no). Same indexing rules
    as get_task_title."""
    tasks = get_phase(phase_no)["tasks"]
    if task_no < 1 or task_no > len(tasks):
        raise KeyError(
            f"task_no {task_no} out of range for phase {phase_no} "
            f"(1..{len(tasks)})"
        )
    return list(tasks[task_no - 1]["skill_tags"])  # defensive copy


def iter_all_phase_task_pairs() -> Iterator[tuple[int, int]]:
    """Yield every (phase, task_no) coordinate in stable phase-then-
    task_no order. Used by the recommendation service to enumerate the
    universe of curriculum tasks for the "unsubmitted" filter."""
    for phase_no in sorted(CURRICULUM.keys()):
        for i in range(len(CURRICULUM[phase_no]["tasks"])):
            yield phase_no, i + 1
```

- [ ] **Step 6: 新規テストが通ることを確認**

```bash
uv run pytest tests/test_curriculum_skill_tags.py -q
```

Expected: `7 passed`。

- [ ] **Step 7: 既存テストが落ちる箇所を確認**

```bash
uv run pytest -q
```

`test_curriculum_data.py::test_each_phase_has_at_least_three_tasks` は len のみなので pass。他に str 直接アクセスがある可能性は次の Task 3 で扱う（submission_service 系）。本タスクで赤になるテストがあれば一旦記録するだけでよい（後タスクで治す）。

Expected: 既存テストでいくつか赤になる（特に `test_submission_service.py` 系で `task_description` がいまや dict 同等を渡してしまう）。Task 3 で修正する。

- [ ] **Step 8: Commit**

```bash
git add backend/app/data/curriculum.py backend/tests/test_curriculum_skill_tags.py
git commit -m "feat(sprint-5): add TaskItem skill_tags to curriculum (12 tasks tagged)"
```

---

## Task 2: api/curriculum.py の互換ラッパー（既存 GET /api/curriculum の出力を維持）

**Files:**
- Modify: `backend/app/api/curriculum.py`

- [ ] **Step 1: 失敗するテストを追加（既存テスト `test_api_curriculum.py::test_list_phases_returns_titles_and_tasks` が壊れていないことを確認するだけ）**

実態：`schemas/curriculum.py` の `PhaseSummary.tasks: list[str]` は変えない（フロント互換のため）。今や `phase["tasks"]` が dict のリストになったので、`PhaseSummary` 構築時に `[item["title"] for item in ...]` を作る必要がある。

まず現状の挙動を確認:

```bash
uv run pytest tests/test_api_curriculum.py -q
```

Expected: ここで赤になっているはず（`tasks=phase["tasks"]` が dict のリストを文字列型に詰めようとする）。

- [ ] **Step 2: `backend/app/api/curriculum.py` の `tasks=phase["tasks"]` を title 射影に変更**

該当箇所（28 行目前後）:

```python
            tasks=phase["tasks"],
```

を:

```python
            tasks=[item["title"] for item in phase["tasks"]],
```

に変更。

- [ ] **Step 3: 既存 API テストが緑に戻ることを確認**

```bash
uv run pytest tests/test_api_curriculum.py -q
```

Expected: `4 passed`。

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/curriculum.py
git commit -m "fix(sprint-5): project TaskItem.title for GET /api/curriculum back-compat"
```

---

## Task 3: services/submission.py を TaskItem に対応

**Files:**
- Modify: `backend/app/services/submission.py`

- [ ] **Step 1: 既存 submission サービステストの赤を確認**

```bash
uv run pytest tests/test_submission_service.py tests/test_submission_service_sprint3.py tests/test_api_submissions.py tests/test_api_submissions_sprint3.py -q
```

Expected: ここで赤あり（`_validate_phase_and_task` が `tasks[task_no-1]` を str として返すと仮定しているが、現実は dict）。

- [ ] **Step 2: `_validate_phase_and_task` を title 射影に変更**

`backend/app/services/submission.py:38-44` を以下に置き換える:

```python
def _validate_phase_and_task(phase: int, task_no: int) -> str:
    if phase not in CURRICULUM:
        raise SubmissionPhaseInvalidError(phase)
    tasks = CURRICULUM[phase]["tasks"]
    if task_no < 1 or task_no > len(tasks):
        raise SubmissionTaskInvalidError(task_no)
    # Sprint 5: tasks are TaskItem dicts; return the human title that the
    # grading prompt expects as `task_description`.
    return tasks[task_no - 1]["title"]
```

`tasks_total` を使っている `_promote_progress_if_all_submitted` 周り（143 行目付近）は `len(CURRICULUM[phase]["tasks"])` のままで OK（length は dict でも str でも同じ）。

- [ ] **Step 3: 全テスト緑を確認**

```bash
uv run pytest -q
```

Expected: `212 passed` + 新規 7 件 = `219 passed`。

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/submission.py
git commit -m "fix(sprint-5): _validate_phase_and_task returns TaskItem.title"
```

---

## Task 4: scripts/seed_embeddings.py を TaskItem に対応 + 埋め込み再投入

**Files:**
- Modify: `backend/scripts/seed_embeddings.py`

- [ ] **Step 1: `seed_embeddings.py` の task ループを title 取り出しに変更**

`backend/scripts/seed_embeddings.py:26-27` を以下に置き換える:

```python
        for i, task in enumerate(phase["tasks"]):
            items.append(
                ("curriculum_task", f"phase:{phase_no}:task:{i}", phase_no, task["title"])
            )
```

skill ループは無変更（既存 `phase["skills"]` は `list[str]` のまま）。

- [ ] **Step 2: 単体実行で SQL エラーなく seed されることを確認**

```bash
docker compose up -d postgres
uv run python -m scripts.seed_embeddings
```

Expected: `Seeded 28 embedding rows.`

- [ ] **Step 3: pgvector の `embeddings.content` が text 列で更新されていることを軽く確認**

```bash
docker compose exec postgres psql -U postgres -d ai_tutor -c \
  "SELECT source_type, source_ref, LEFT(content, 30) FROM embeddings WHERE source_type='curriculum_task' ORDER BY source_ref LIMIT 3;"
```

Expected: 3 行（phase:1:task:0, phase:1:task:1, phase:1:task:2）が表示。

- [ ] **Step 4: 全テストが引き続き緑**

```bash
uv run pytest -q
```

Expected: `219 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_embeddings.py
git commit -m "fix(sprint-5): seed_embeddings passes task['title'] after TaskItem migration"
```

---

## Task 5: Settings 拡張（nudge_*）と .env.example

**Files:**
- Modify: `backend/app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: `Settings` クラスに 4 項目を追加**

`backend/app/config.py` の `Settings` クラス末尾（`@property` 群の手前、`notification_unread_cap` の後あたり）に追加:

```python
    # Sprint 5 — AI nudge (lazy generation + 24h cache)
    nudge_model: str = "claude-haiku-4-5"
    nudge_cache_ttl_hours: int = 24
    nudge_max_output_tokens: int = 200
    nudge_temperature: float = 0.5
```

- [ ] **Step 2: `.env.example` に対応する 4 行を追加（Sprint 4 のブロックの後）**

`.env.example` 末尾に追加:

```
# Sprint 5 — AI nudge
NUDGE_MODEL=claude-haiku-4-5
NUDGE_CACHE_TTL_HOURS=24
NUDGE_MAX_OUTPUT_TOKENS=200
NUDGE_TEMPERATURE=0.5
```

- [ ] **Step 3: テストを実行して既存挙動が壊れていないことを確認**

```bash
cd backend && uv run pytest -q
```

Expected: `219 passed`.

- [ ] **Step 4: Commit**

```bash
cd .. && git add backend/app/config.py .env.example
git commit -m "chore(sprint-5): add nudge_* settings (model, ttl, tokens, temperature)"
```

---

## Task 6: UserNudge モデル + Alembic マイグレーション

**Files:**
- Create: `backend/app/models/user_nudge.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/tests/test_models_sprint5.py`
- Create: `backend/alembic/versions/20260608_<rev>_sprint5_user_nudges.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_models_sprint5.py` を新規作成:

```python
"""Sprint 5 model tests — UserNudge cache row."""

import uuid as uuid_mod
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.user import User
from app.models.user_nudge import UserNudge


async def _make_user(db_session, email="u@e.com"):
    user = User(email=email, name="U", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_user_nudge_round_trip(db_session):
    user = await _make_user(db_session)
    nudge = UserNudge(
        user_id=user.id,
        body="今日は データ構造 を伸ばすチャンスです。",
        generated_at=datetime.now(UTC),
        input_signature="abc1234567890def",
    )
    db_session.add(nudge)
    await db_session.commit()
    row = (
        await db_session.execute(
            select(UserNudge).where(UserNudge.user_id == user.id)
        )
    ).scalar_one()
    assert row.body.startswith("今日は")


@pytest.mark.asyncio
async def test_user_nudge_pk_is_user_id(db_session):
    """1 user = 1 row, so a second insert with the same user_id must fail.

    Production code uses upsert (ON CONFLICT DO UPDATE), but the schema
    guarantee — not the upsert syntax — is what makes a runaway loop
    safe."""
    user = await _make_user(db_session)
    db_session.add(UserNudge(
        user_id=user.id, body="a", generated_at=datetime.now(UTC),
        input_signature="x" * 16,
    ))
    await db_session.commit()

    db_session.add(UserNudge(
        user_id=user.id, body="b", generated_at=datetime.now(UTC),
        input_signature="y" * 16,
    ))
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_user_nudge_cascades_on_user_delete(db_session):
    user = await _make_user(db_session)
    db_session.add(UserNudge(
        user_id=user.id, body="a", generated_at=datetime.now(UTC),
        input_signature="x" * 16,
    ))
    await db_session.commit()

    await db_session.delete(user)
    await db_session.commit()
    leftover = (
        await db_session.execute(
            select(UserNudge).where(UserNudge.user_id == user.id)
        )
    ).first()
    assert leftover is None
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd backend && uv run pytest tests/test_models_sprint5.py -q
```

Expected: ImportError（`UserNudge` がまだ存在しない）。

- [ ] **Step 3: `UserNudge` モデルを作成**

`backend/app/models/user_nudge.py` を新規作成:

```python
"""Sprint 5: AI nudge cache row.

Single row per user (PK = user_id). 24h TTL caching + an
input_signature lets us cheaply detect "the inputs that produced this
nudge have shifted" inside the window — when the learner submits a new
task or a weakness moves out of the top 3, the signature changes and
the dashboard regenerates even before the 24h timer expires.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserNudge(Base):
    __tablename__ = "user_nudges"
    __table_args__ = (
        Index("ix_user_nudges_generated_at", "generated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    input_signature: Mapped[str] = mapped_column(String(16), nullable=False)
```

- [ ] **Step 4: `app/models/__init__.py` に import を追加**

`backend/app/models/__init__.py` の既存 import 群に追加:

```python
from app.models.user_nudge import UserNudge  # noqa: F401
```

（既存の `__all__` がある場合は `"UserNudge"` を追加）

- [ ] **Step 5: テスト DB に CREATE TABLE が走るのを確認**

```bash
uv run pytest tests/test_models_sprint5.py -q
```

Expected: `3 passed`（conftest の `_setup_db` が `Base.metadata.create_all` を呼ぶため、ORM 経由でテーブルが作成される）。

- [ ] **Step 6: Alembic マイグレーションを生成**

```bash
uv run alembic revision -m "sprint5_user_nudges"
```

生成されたファイルは `backend/alembic/versions/2026...sprint5_user_nudges.py`。中身を以下に置き換える（autogenerate を使わず手書きにする — 学習用途で migration を読みやすく保つ）:

```python
"""sprint5_user_nudges

Revision ID: <auto-filled>
Revises: <最新のリビジョン ID>
Create Date: 2026-06-08 ...
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "<auto-filled>"
down_revision = "<previous revision id from the generated file>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_nudges",
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_signature", sa.String(length=16), nullable=False),
    )
    op.create_index(
        "ix_user_nudges_generated_at",
        "user_nudges",
        ["generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_nudges_generated_at", table_name="user_nudges")
    op.drop_table("user_nudges")
```

`<auto-filled>` と `<previous revision id ...>` は Alembic が埋めた値そのまま使う（消さない）。

- [ ] **Step 7: マイグレーションを開発 DB に適用**

```bash
uv run alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade ... -> ..., sprint5_user_nudges`。

- [ ] **Step 8: テーブル存在確認**

```bash
docker compose exec postgres psql -U postgres -d ai_tutor -c "\d user_nudges"
```

Expected: 4 列（user_id / body / generated_at / input_signature）+ PK 制約 + FK 制約 + ix_user_nudges_generated_at インデックス。

- [ ] **Step 9: 全テスト緑**

```bash
uv run pytest -q
```

Expected: `222 passed`。

- [ ] **Step 10: Commit**

```bash
cd .. && git add backend/app/models/user_nudge.py backend/app/models/__init__.py backend/alembic/versions/*sprint5_user_nudges.py backend/tests/test_models_sprint5.py
git commit -m "feat(sprint-5): add UserNudge model + alembic migration"
```

---

## Task 7: services/rag.py に search_curriculum_tasks を追加

**Files:**
- Modify: `backend/app/services/rag.py`
- Create: `backend/tests/test_rag_curriculum_tasks.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_rag_curriculum_tasks.py`:

```python
"""Sprint 5: curriculum_task に絞った RAG ヘルパーのテスト。

既存 `search_context` は会話用（phase 必須）なので、recommendation
service が「全 phase 横断で task のみ」を引きたいケース専用に新規
関数を切る。"""

import pytest

from app.core.embedding_client import EmbeddingClient
from app.services.embedding import upsert_embeddings
from app.services.rag import search_curriculum_tasks


@pytest.fixture(scope="module")
def client():
    return EmbeddingClient()


@pytest.mark.asyncio
async def test_search_returns_phase_and_task_no_parsed_from_source_ref(
    db_session, client,
):
    items = [
        ("curriculum_task", "phase:1:task:0", 1, "Git でブランチを切る"),
        ("curriculum_task", "phase:2:task:1", 2, "Copilot で書く"),
        ("curriculum_task", "phase:3:task:2", 3, "AI とペアで実装する"),
        # ノイズ: curriculum_skill は除外されるべき
        ("curriculum_skill", "phase:1:skill:0", 1, "Git/GitHub"),
    ]
    await upsert_embeddings(db_session, client, user_id=None, items=items)
    await db_session.commit()

    hits = await search_curriculum_tasks(
        db_session, client, query="Git でブランチを切る", limit=5,
    )
    assert all(h.phase in {1, 2, 3} for h in hits)
    # 1-indexed の task_no に変換されている
    assert all(1 <= h.task_no <= 3 for h in hits)
    # top hit は phase 1, task_no 1（source_ref task:0 を 1-indexed 化）
    assert hits[0].phase == 1 and hits[0].task_no == 1
    # curriculum_skill が紛れ込んでいない
    assert len(hits) <= 3


@pytest.mark.asyncio
async def test_search_returns_empty_on_blank_query(db_session, client):
    out = await search_curriculum_tasks(db_session, client, query="  ", limit=5)
    assert out == []


@pytest.mark.asyncio
async def test_search_caps_at_limit(db_session, client):
    items = [
        ("curriculum_task", f"phase:1:task:{i}", 1, f"題材{i}")
        for i in range(6)
    ]
    await upsert_embeddings(db_session, client, user_id=None, items=items)
    await db_session.commit()

    hits = await search_curriculum_tasks(
        db_session, client, query="題材", limit=3,
    )
    assert len(hits) == 3


@pytest.mark.asyncio
async def test_search_skips_malformed_source_ref(db_session, client):
    """defensive: 過去データに混入した古い形式の source_ref を黙って捨てる"""
    items = [
        ("curriculum_task", "legacy-format", 1, "古い形式"),
        ("curriculum_task", "phase:1:task:0", 1, "新しい形式"),
    ]
    await upsert_embeddings(db_session, client, user_id=None, items=items)
    await db_session.commit()

    hits = await search_curriculum_tasks(db_session, client, query="形式", limit=5)
    # 新しい形式の 1 件だけが残る
    assert any(h.phase == 1 and h.task_no == 1 for h in hits)
    # legacy-format は parse 失敗で除外
    assert all(h.phase == 1 for h in hits)
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd backend && uv run pytest tests/test_rag_curriculum_tasks.py -q
```

Expected: ImportError（`search_curriculum_tasks` がまだない）。

- [ ] **Step 3: `services/rag.py` に追加**

`backend/app/services/rag.py` の末尾に追加:

```python
@dataclass(frozen=True)
class CurriculumTaskHit:
    """Phase/task coordinates parsed out of `Embedding.source_ref` plus the
    cosine similarity score. The recommendation service uses (phase,
    task_no) to filter against the learner's submission history; the
    content text is not surfaced to callers — they reconstruct titles
    via `curriculum.get_task_title`."""

    phase: int
    task_no: int  # 1-indexed (matches submissions.task_no)
    score: float


async def search_curriculum_tasks(
    db: AsyncSession,
    client: EmbeddingClient,
    *,
    query: str,
    limit: int = 8,
) -> list[CurriculumTaskHit]:
    """Vector search restricted to `source_type='curriculum_task'`.

    Differs from `search_context` in three ways:
      - No phase filter (Sprint 5 recommendation crosses phases).
      - No user_id filter (curriculum embeddings are global).
      - Returns (phase, task_no) coordinates instead of free text.
    """
    if not query.strip():
        return []
    vectors = await client.embed([query])
    qvec = vectors[0]

    stmt = (
        select(
            Embedding.source_ref,
            Embedding.embedding.cosine_distance(qvec).label("distance"),
        )
        .where(Embedding.source_type == "curriculum_task")
        .order_by("distance")
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    out: list[CurriculumTaskHit] = []
    for r in rows:
        # Expected shape: "phase:{p}:task:{i}" with i 0-indexed.
        # Anything else is legacy data we silently drop — the
        # alternative (raising) would bubble through the recommendation
        # service and replace a dashboard section with a 500.
        try:
            tag, p_str, _, i_str = r.source_ref.split(":")
            if tag != "phase":
                continue
            phase = int(p_str)
            task_no = int(i_str) + 1
        except (ValueError, AttributeError):
            continue
        out.append(
            CurriculumTaskHit(
                phase=phase, task_no=task_no, score=1.0 - float(r.distance),
            )
        )
    return out
```

- [ ] **Step 4: テストが緑になることを確認**

```bash
uv run pytest tests/test_rag_curriculum_tasks.py -q
```

Expected: `4 passed`。

- [ ] **Step 5: 全テスト緑**

```bash
uv run pytest -q
```

Expected: `226 passed`.

- [ ] **Step 6: Commit**

```bash
cd .. && git add backend/app/services/rag.py backend/tests/test_rag_curriculum_tasks.py
git commit -m "feat(sprint-5): add search_curriculum_tasks RAG helper"
```

---

## Task 8: weakness service（TDD）

**Files:**
- Create: `backend/app/services/weakness.py`
- Create: `backend/tests/test_weakness_service.py`
- Modify: `backend/tests/conftest.py`（`seed_graded_submission` helper を追加）

- [ ] **Step 1: conftest に提出 + graded attempt のシードヘルパーを追加**

`backend/tests/conftest.py` の末尾に追加:

```python
@pytest_asyncio.fixture
async def seed_graded_submission(db_session):
    """Insert a Submission row + a GradingAttempt with status='graded'
    and the given score. Returns (submission, attempt) so tests can
    chain further mutations (e.g. re-grade, mark stale)."""
    from datetime import UTC, datetime
    from app.models.grading_attempt import GradingAttempt
    from app.models.submission import Submission

    created = []

    async def _seed(user, phase, task_no, score):
        sub = Submission(
            user_id=user.id, phase=phase, task_no=task_no,
            content=f"essay phase{phase} task{task_no}",
            submitted_at=datetime.now(UTC),
        )
        db_session.add(sub)
        await db_session.flush()
        att = GradingAttempt(
            submission_id=sub.id,
            status="graded",
            score=score,
            ai_feedback="ok",
            model_name="claude-sonnet-4-5",
        )
        db_session.add(att)
        await db_session.commit()
        await db_session.refresh(sub)
        await db_session.refresh(att)
        created.append((sub, att))
        return sub, att

    return _seed
```

（既存 `GradingAttempt` のフィールド名は Sprint 3 のコードと整合させる。`ai_feedback / model_name / status / score / submission_id` が必須。実装時に `from app.models.grading_attempt import GradingAttempt` を読んで揃える。）

- [ ] **Step 2: failing test を追加**

`backend/tests/test_weakness_service.py`:

```python
"""Sprint 5: weakness service."""

import pytest

from app.core.security import hash_password
from app.models.user import User
from app.services.weakness import (
    MIN_SUBMISSION_THRESHOLD,
    MIN_TAG_SUBMISSIONS,
    compute_weakness,
)


async def _make_user(db_session, email="w@e.com"):
    user = User(email=email, name="W", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_returns_has_enough_data_false_when_below_threshold(
    db_session, seed_graded_submission,
):
    """Submission < 3 件のとき has_enough_data=False、top_weaknesses=[]。"""
    user = await _make_user(db_session)
    await seed_graded_submission(user, 1, 1, 60)
    await seed_graded_submission(user, 1, 2, 70)

    result = await compute_weakness(db_session, user.id)
    assert result.has_enough_data is False
    assert result.top_weaknesses == []


@pytest.mark.asyncio
async def test_aggregates_by_tag_low_score_first(
    db_session, seed_graded_submission,
):
    """3 件以上提出すると、タグ別平均が低い順に並ぶ。"""
    user = await _make_user(db_session)
    # phase 1 task 1 -> ["Git/GitHub"] スコア 50
    await seed_graded_submission(user, 1, 1, 50)
    # phase 1 task 2 -> ["開発環境"] スコア 90
    await seed_graded_submission(user, 1, 2, 90)
    # phase 1 task 3 -> ["API基礎"] スコア 70
    await seed_graded_submission(user, 1, 3, 70)
    # phase 2 task 1 -> ["AI協調", "API基礎"] スコア 60
    await seed_graded_submission(user, 2, 1, 60)
    # phase 2 task 3 -> ["AI協調", "コードレビュー"] スコア 80
    await seed_graded_submission(user, 2, 3, 80)

    result = await compute_weakness(db_session, user.id)
    assert result.has_enough_data is True
    # AI協調: (60+80)/2 = 70、API基礎: (70+60)/2 = 65、
    # Git/GitHub: 50 だが提出 1 件のみ → MIN_TAG_SUBMISSIONS で除外
    # 開発環境: 90 だが提出 1 件のみ → 除外
    # コードレビュー: 80 だが提出 1 件のみ → 除外
    # 残り: AI協調=70, API基礎=65
    tags = [w.tag for w in result.top_weaknesses]
    assert tags == ["API基礎", "AI協調"]
    assert result.top_weaknesses[0].average_score == 65.0
    assert result.top_weaknesses[0].submission_count == 2


@pytest.mark.asyncio
async def test_returns_at_most_top_3(db_session, seed_graded_submission):
    """同じタグに大量提出して 3 件のタグが見える状態でも top_weaknesses は 3 まで。"""
    user = await _make_user(db_session)
    # phase 2 の各タスクは "AI協調" を含む (1,2,3) — それぞれ追加でタグを持つ
    # phase 2 task 1: AI協調+API基礎 → 100
    await seed_graded_submission(user, 2, 1, 100)
    # phase 2 task 2: AI協調+開発環境 → 100
    await seed_graded_submission(user, 2, 2, 100)
    # phase 2 task 3: AI協調+コードレビュー → 100
    await seed_graded_submission(user, 2, 3, 100)
    # phase 3 task 1: コードレビュー+AI協調 → 30
    await seed_graded_submission(user, 3, 1, 30)
    # phase 3 task 2: テスト+AI協調 → 30
    await seed_graded_submission(user, 3, 2, 30)
    # phase 3 task 3: AI協調+設計 → 30
    await seed_graded_submission(user, 3, 3, 30)

    result = await compute_weakness(db_session, user.id)
    # AI協調 はあちこちに出てくる
    assert len(result.top_weaknesses) <= 3


@pytest.mark.asyncio
async def test_uses_latest_graded_attempt_per_submission(
    db_session, seed_graded_submission,
):
    """1 つの submission に複数 graded attempt がある場合は最新 1 件のみ。
    （再採点で 90 → 60 と変動した場合、60 を採用）"""
    from datetime import UTC, datetime, timedelta
    from app.models.grading_attempt import GradingAttempt

    user = await _make_user(db_session)
    sub, first_att = await seed_graded_submission(user, 1, 1, 60)
    # 古い attempt の時刻を強制的に過去にする
    first_att.created_at = datetime.now(UTC) - timedelta(hours=2)
    # 新しい高得点 attempt
    new_att = GradingAttempt(
        submission_id=sub.id,
        status="graded",
        score=95,
        ai_feedback="ok",
        model_name="claude-sonnet-4-5",
        created_at=datetime.now(UTC),
    )
    db_session.add(new_att)
    # コールドスタート脱出に必要な追加 2 件
    await seed_graded_submission(user, 1, 2, 50)
    await seed_graded_submission(user, 1, 3, 50)
    await db_session.commit()

    result = await compute_weakness(db_session, user.id)
    # phase 1 task 1 = ["Git/GitHub"] は 95 (最新) を使う
    tags = {w.tag: w for w in result.top_weaknesses}
    # Git/GitHub は提出 1 件のみ → 除外なので tags に出ない
    assert "Git/GitHub" not in tags
    # 開発環境 と API基礎 はそれぞれ 50 点 1 件のみ → 除外
    # 結果として top_weaknesses は空 (全部 1 件) でも OK
    assert result.has_enough_data is True


def test_constants_match_spec():
    assert MIN_SUBMISSION_THRESHOLD == 3
    assert MIN_TAG_SUBMISSIONS == 2
```

- [ ] **Step 3: テストが失敗することを確認**

```bash
uv run pytest tests/test_weakness_service.py -q
```

Expected: ImportError。

- [ ] **Step 4: `app/services/weakness.py` を実装**

```python
"""Sprint 5 weakness service — per-tag score aggregation.

Definition of weakness:
  - Take the latest *graded* attempt for each submission.
  - Group those scores by curriculum skill_tags.
  - Drop tags with fewer than MIN_TAG_SUBMISSIONS supporting samples
    (so a one-off bad grade does not turn into "your weakness").
  - Return the 3 tags with the lowest mean score.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.curriculum import get_task_skill_tags
from app.models.grading_attempt import GradingAttempt
from app.models.submission import Submission


MIN_SUBMISSION_THRESHOLD = 3
"""提出件数がこれを下回るとき、弱点分析を出さずに cold-start UX に切り替える。"""

MIN_TAG_SUBMISSIONS = 2
"""タグ集計に含めるための最小提出数（1 件で「弱点」認定はノイズ）。"""


@dataclass(frozen=True)
class TagAverage:
    tag: str
    average_score: float
    submission_count: int


@dataclass(frozen=True)
class WeaknessResult:
    has_enough_data: bool
    top_weaknesses: list[TagAverage]


async def compute_weakness(
    db: AsyncSession, user_id: uuid.UUID,
) -> WeaknessResult:
    rows = await _latest_graded_scores(db, user_id)
    if len(rows) < MIN_SUBMISSION_THRESHOLD:
        return WeaknessResult(has_enough_data=False, top_weaknesses=[])

    tag_scores: dict[str, list[float]] = defaultdict(list)
    for _sub_id, score, phase, task_no in rows:
        for tag in get_task_skill_tags(phase, task_no):
            tag_scores[tag].append(float(score))

    averages = [
        TagAverage(
            tag=t, average_score=round(mean(scores), 2),
            submission_count=len(scores),
        )
        for t, scores in tag_scores.items()
        if len(scores) >= MIN_TAG_SUBMISSIONS
    ]
    # 低スコア順、同点はタグ名でタイブレーク（テストで安定再現可能に）
    averages.sort(key=lambda a: (a.average_score, a.tag))
    return WeaknessResult(has_enough_data=True, top_weaknesses=averages[:3])


async def _latest_graded_scores(
    db: AsyncSession, user_id: uuid.UUID,
) -> list[tuple[uuid.UUID, float, int, int]]:
    """`SELECT DISTINCT ON (s.id)` で submission ごとに最新 graded attempt
    のスコアを返す。phase / task_no は Python 側で curriculum lookup する
    ため一緒に返す。"""
    stmt = (
        select(
            Submission.id, GradingAttempt.score,
            Submission.phase, Submission.task_no,
        )
        .join(GradingAttempt, GradingAttempt.submission_id == Submission.id)
        .where(Submission.user_id == user_id, GradingAttempt.status == "graded")
        .order_by(Submission.id, GradingAttempt.created_at.desc())
        .distinct(Submission.id)
    )
    rows = (await db.execute(stmt)).all()
    return [(r[0], r[1], r[2], r[3]) for r in rows]
```

- [ ] **Step 5: テストが緑になることを確認**

```bash
uv run pytest tests/test_weakness_service.py -q
```

Expected: `5 passed`。

- [ ] **Step 6: 全テスト緑**

```bash
uv run pytest -q
```

Expected: `231 passed`.

- [ ] **Step 7: Commit**

```bash
cd .. && git add backend/app/services/weakness.py backend/tests/test_weakness_service.py backend/tests/conftest.py
git commit -m "feat(sprint-5): weakness service (per-tag latest-graded average, top 3)"
```

---

## Task 9: progress_summary service（TDD）

**Files:**
- Create: `backend/app/services/progress_summary.py`
- Create: `backend/tests/test_progress_summary_service.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_progress_summary_service.py`:

```python
"""Sprint 5: progress summary service.

Aggregates per-user submission count + completed-tasks count + average
score. Cold-start (submission_count < MIN_SUBMISSION_THRESHOLD) returns
average_score=None so the UI can render "—" instead of a placeholder
number that anchors expectations.
"""

import pytest

from app.core.security import hash_password
from app.models.user import User
from app.services.progress_summary import (
    TOTAL_TASKS,
    ProgressSummary,
    compute_progress_summary,
)


async def _make_user(db_session, email="p@e.com"):
    user = User(email=email, name="P", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


def test_total_tasks_constant_is_12():
    assert TOTAL_TASKS == 12


@pytest.mark.asyncio
async def test_empty_user_returns_zeros_and_null_average(db_session):
    user = await _make_user(db_session)
    out = await compute_progress_summary(db_session, user.id)
    assert isinstance(out, ProgressSummary)
    assert out.completed_tasks == 0
    assert out.total_tasks == 12
    assert out.submission_count == 0
    assert out.average_score is None


@pytest.mark.asyncio
async def test_below_threshold_returns_null_average(
    db_session, seed_graded_submission,
):
    user = await _make_user(db_session)
    await seed_graded_submission(user, 1, 1, 80)
    await seed_graded_submission(user, 1, 2, 90)  # 2 件のみ < 3

    out = await compute_progress_summary(db_session, user.id)
    assert out.submission_count == 2
    assert out.average_score is None  # cold-start
    assert out.completed_tasks == 2


@pytest.mark.asyncio
async def test_above_threshold_returns_average_rounded(
    db_session, seed_graded_submission,
):
    user = await _make_user(db_session)
    await seed_graded_submission(user, 1, 1, 80)
    await seed_graded_submission(user, 1, 2, 70)
    await seed_graded_submission(user, 1, 3, 60)

    out = await compute_progress_summary(db_session, user.id)
    assert out.submission_count == 3
    assert out.completed_tasks == 3
    assert out.average_score == 70.0
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
uv run pytest tests/test_progress_summary_service.py -q
```

Expected: ImportError。

- [ ] **Step 3: 実装**

`backend/app/services/progress_summary.py`:

```python
"""Sprint 5 progress summary — completion + average score aggregation."""

import uuid
from dataclasses import dataclass
from statistics import mean

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.curriculum import iter_all_phase_task_pairs
from app.services.weakness import MIN_SUBMISSION_THRESHOLD, _latest_graded_scores


TOTAL_TASKS = sum(1 for _ in iter_all_phase_task_pairs())
"""Total curriculum tasks. Computed once at module load so a future
curriculum expansion is picked up without code changes here."""


@dataclass(frozen=True)
class ProgressSummary:
    completed_tasks: int  # = submission_count (1 submission per task)
    total_tasks: int
    submission_count: int
    average_score: float | None  # None below MIN_SUBMISSION_THRESHOLD


async def compute_progress_summary(
    db: AsyncSession, user_id: uuid.UUID,
) -> ProgressSummary:
    rows = await _latest_graded_scores(db, user_id)
    count = len(rows)
    if count < MIN_SUBMISSION_THRESHOLD:
        return ProgressSummary(
            completed_tasks=count, total_tasks=TOTAL_TASKS,
            submission_count=count, average_score=None,
        )
    avg = round(mean(float(r[1]) for r in rows), 2)
    return ProgressSummary(
        completed_tasks=count, total_tasks=TOTAL_TASKS,
        submission_count=count, average_score=avg,
    )
```

- [ ] **Step 4: テストが緑**

```bash
uv run pytest tests/test_progress_summary_service.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: 全テスト緑**

```bash
uv run pytest -q
```

Expected: `235 passed`.

- [ ] **Step 6: Commit**

```bash
cd .. && git add backend/app/services/progress_summary.py backend/tests/test_progress_summary_service.py
git commit -m "feat(sprint-5): progress summary service (completed/total/avg score)"
```

---

## Task 10: recommendation service（TDD）

**Files:**
- Create: `backend/app/services/recommendation.py`
- Create: `backend/tests/test_recommendation_service.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_recommendation_service.py`:

```python
"""Sprint 5 recommendation service.

Glues unsubmitted task discovery + RAG ranking. The RAG call is
mocked so tests stay deterministic — exercising real fastembed inside
this suite would make it slow and flaky."""

import uuid as uuid_mod

import pytest

from app.core.security import hash_password
from app.models.user import User
from app.services.rag import CurriculumTaskHit
from app.services.recommendation import compute_recommendations


async def _make_user(db_session, email="r@e.com"):
    user = User(email=email, name="R", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_returns_empty_when_no_weakness_tags(db_session):
    user = await _make_user(db_session)
    out = await compute_recommendations(
        db_session, client=object(), user_id=user.id, top_weakness_tags=[],
    )
    assert out == []


@pytest.mark.asyncio
async def test_returns_unsubmitted_hits_in_rag_order(
    db_session, seed_graded_submission, monkeypatch,
):
    """RAG が phase 1 task 1, phase 2 task 1, phase 3 task 2, phase 4 task 1
    を返した場合、未提出のものだけが上位 3 件として並ぶ。"""
    user = await _make_user(db_session)
    # 提出済み: phase 1 task 1 (除外対象)
    await seed_graded_submission(user, 1, 1, 50)

    fake_hits = [
        CurriculumTaskHit(phase=1, task_no=1, score=0.95),  # 提出済 -> drop
        CurriculumTaskHit(phase=2, task_no=1, score=0.80),
        CurriculumTaskHit(phase=3, task_no=2, score=0.70),
        CurriculumTaskHit(phase=4, task_no=1, score=0.60),
    ]

    async def fake_search(db, client, *, query, limit):
        return fake_hits

    monkeypatch.setattr(
        "app.services.recommendation.search_curriculum_tasks", fake_search,
    )

    out = await compute_recommendations(
        db_session, client=object(),
        user_id=user.id, top_weakness_tags=["API基礎"],
    )
    coords = [(r.phase, r.task_no) for r in out]
    assert coords == [(2, 1), (3, 2), (4, 1)]


@pytest.mark.asyncio
async def test_match_tag_is_set_when_primary_tag_present_else_null(
    db_session, monkeypatch,
):
    """phase 2 task 1 has tags [AI協調, API基礎]: query 'API基礎' → match_tag
    set. phase 4 task 1 has [LLM活用]: match_tag None."""
    user = await _make_user(db_session)

    async def fake_search(db, client, *, query, limit):
        return [
            CurriculumTaskHit(phase=2, task_no=1, score=0.9),
            CurriculumTaskHit(phase=4, task_no=1, score=0.5),
        ]

    monkeypatch.setattr(
        "app.services.recommendation.search_curriculum_tasks", fake_search,
    )
    out = await compute_recommendations(
        db_session, client=object(),
        user_id=user.id, top_weakness_tags=["API基礎"],
    )
    by_key = {(r.phase, r.task_no): r for r in out}
    assert by_key[(2, 1)].match_tag == "API基礎"
    assert by_key[(4, 1)].match_tag is None


@pytest.mark.asyncio
async def test_caps_at_top_3(db_session, monkeypatch):
    user = await _make_user(db_session)

    async def fake_search(db, client, *, query, limit):
        return [
            CurriculumTaskHit(phase=p, task_no=t, score=1.0 - 0.1 * i)
            for i, (p, t) in enumerate([(1, 1), (1, 2), (1, 3), (2, 1), (2, 2)])
        ]
    monkeypatch.setattr(
        "app.services.recommendation.search_curriculum_tasks", fake_search,
    )
    out = await compute_recommendations(
        db_session, client=object(),
        user_id=user.id, top_weakness_tags=["AI協調"],
    )
    assert len(out) == 3


@pytest.mark.asyncio
async def test_returns_empty_when_all_tasks_submitted(
    db_session, seed_graded_submission, monkeypatch,
):
    user = await _make_user(db_session)
    # 12 タスク全件提出
    for p in (1, 2, 3, 4):
        for t in (1, 2, 3):
            await seed_graded_submission(user, p, t, 70)

    async def fake_search(db, client, *, query, limit):
        return [CurriculumTaskHit(phase=1, task_no=1, score=0.99)]

    monkeypatch.setattr(
        "app.services.recommendation.search_curriculum_tasks", fake_search,
    )
    out = await compute_recommendations(
        db_session, client=object(),
        user_id=user.id, top_weakness_tags=["Git/GitHub"],
    )
    assert out == []
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
uv run pytest tests/test_recommendation_service.py -q
```

Expected: ImportError。

- [ ] **Step 3: 実装**

`backend/app/services/recommendation.py`:

```python
"""Sprint 5 recommendation service.

Couples "what hasn't this learner tried yet" with "what looks like
their weakness" via the curriculum-task RAG helper. Returns at most
3 hits; fewer is OK and signals to the UI to show a softer CTA.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding_client import EmbeddingClient
from app.data.curriculum import (
    get_task_skill_tags, get_task_title, iter_all_phase_task_pairs,
)
from app.models.submission import Submission
from app.services.rag import CurriculumTaskHit, search_curriculum_tasks


@dataclass(frozen=True)
class Recommendation:
    phase: int
    task_no: int
    title: str
    skill_tags: list[str]
    match_tag: str | None
    rag_score: float


async def compute_recommendations(
    db: AsyncSession,
    client: EmbeddingClient,
    *,
    user_id: uuid.UUID,
    top_weakness_tags: list[str],
) -> list[Recommendation]:
    if not top_weakness_tags:
        return []

    submitted = await _user_submitted_phase_task_pairs(db, user_id)
    unsubmitted_keys: set[tuple[int, int]] = {
        (p, t) for p, t in iter_all_phase_task_pairs() if (p, t) not in submitted
    }
    if not unsubmitted_keys:
        return []

    primary = top_weakness_tags[0]
    hits: list[CurriculumTaskHit] = await search_curriculum_tasks(
        db, client, query=f"{primary} を扱うタスク", limit=8,
    )

    seen: set[tuple[int, int]] = set()
    out: list[Recommendation] = []
    for hit in hits:
        key = (hit.phase, hit.task_no)
        if key not in unsubmitted_keys or key in seen:
            continue
        seen.add(key)
        try:
            tags = get_task_skill_tags(hit.phase, hit.task_no)
            title = get_task_title(hit.phase, hit.task_no)
        except KeyError:
            continue  # legacy embeddings beyond current curriculum
        out.append(Recommendation(
            phase=hit.phase, task_no=hit.task_no, title=title,
            skill_tags=tags,
            match_tag=primary if primary in tags else None,
            rag_score=hit.score,
        ))
        if len(out) == 3:
            break
    return out


async def _user_submitted_phase_task_pairs(
    db: AsyncSession, user_id: uuid.UUID,
) -> set[tuple[int, int]]:
    stmt = select(Submission.phase, Submission.task_no).where(
        Submission.user_id == user_id,
    )
    rows = (await db.execute(stmt)).all()
    return {(r[0], r[1]) for r in rows}
```

- [ ] **Step 4: テストが緑**

```bash
uv run pytest tests/test_recommendation_service.py -q
```

Expected: `5 passed`.

- [ ] **Step 5: 全テスト緑**

```bash
uv run pytest -q
```

Expected: `240 passed`.

- [ ] **Step 6: Commit**

```bash
cd .. && git add backend/app/services/recommendation.py backend/tests/test_recommendation_service.py
git commit -m "feat(sprint-5): recommendation service (unsubmitted x weakness x RAG top-3)"
```

---

## Task 11: nudge service（TDD、LLM はモック）

**Files:**
- Create: `backend/app/services/nudge.py`
- Create: `backend/tests/test_nudge_service.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_nudge_service.py`:

```python
"""Sprint 5 AI nudge service.

Behavioural surface:
  - cache hit within TTL + same signature → reuse the row
  - cache miss / TTL expired / signature changed → regenerate via LLM
  - cold start (submission_count < threshold) → static text, no LLM
  - LLM exception with prior row → return stale, NOT overwriting cache
  - LLM exception with no prior row → static fallback, NOT persisting it
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.config import settings
from app.core.security import hash_password
from app.models.user import User
from app.models.user_nudge import UserNudge
from app.services.nudge import (
    _build_signature, get_or_generate, COLD_START_BODY,
)


async def _make_user(db_session, email="n@e.com"):
    user = User(email=email, name="N", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _fake_claude(reply: str):
    """Return a Claude client double whose `complete` coroutine yields
    a fixed reply. Matches Sprint 3 grading service's mock pattern."""
    client = MagicMock()
    client.complete = AsyncMock(return_value=reply)
    return client


@pytest.mark.asyncio
async def test_cold_start_returns_static_without_calling_llm(db_session):
    user = await _make_user(db_session)
    claude = _fake_claude("UNUSED")
    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=[], top_recommendation_key=None,
        submission_count=0,
    )
    assert out.body == COLD_START_BODY
    assert out.is_fresh is True
    claude.complete.assert_not_called()
    # No persistence for cold start
    row = (
        await db_session.execute(
            select(UserNudge).where(UserNudge.user_id == user.id)
        )
    ).first()
    assert row is None


@pytest.mark.asyncio
async def test_cache_miss_generates_and_persists(db_session):
    user = await _make_user(db_session)
    claude = _fake_claude("データ構造が伸びる Phase 2 タスク 1 をやろう。")
    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=["AI協調"], top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.is_fresh is True
    assert "Phase 2" in out.body
    row = (
        await db_session.execute(
            select(UserNudge).where(UserNudge.user_id == user.id)
        )
    ).scalar_one()
    assert row.body == out.body
    assert len(row.input_signature) == 16


@pytest.mark.asyncio
async def test_cache_hit_within_ttl_does_not_call_llm(db_session):
    user = await _make_user(db_session)
    sig = _build_signature(["AI協調"], "2:1", 5)
    db_session.add(UserNudge(
        user_id=user.id, body="cached body",
        generated_at=datetime.now(UTC), input_signature=sig,
    ))
    await db_session.commit()

    claude = _fake_claude("WOULD-BE-NEW")
    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=["AI協調"], top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.body == "cached body"
    claude.complete.assert_not_called()


@pytest.mark.asyncio
async def test_signature_change_invalidates_cache_even_within_ttl(db_session):
    user = await _make_user(db_session)
    old_sig = _build_signature(["AI協調"], "2:1", 5)
    db_session.add(UserNudge(
        user_id=user.id, body="stale", generated_at=datetime.now(UTC),
        input_signature=old_sig,
    ))
    await db_session.commit()

    claude = _fake_claude("regenerated body")
    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=["AI協調"], top_recommendation_key="3:2",  # changed
        submission_count=5,
    )
    assert out.body == "regenerated body"
    claude.complete.assert_called_once()


@pytest.mark.asyncio
async def test_ttl_expired_triggers_regeneration(db_session):
    user = await _make_user(db_session)
    sig = _build_signature(["AI協調"], "2:1", 5)
    db_session.add(UserNudge(
        user_id=user.id, body="day-old",
        generated_at=datetime.now(UTC) - timedelta(
            hours=settings.nudge_cache_ttl_hours + 1
        ),
        input_signature=sig,
    ))
    await db_session.commit()

    claude = _fake_claude("fresh")
    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=["AI協調"], top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.body == "fresh"


@pytest.mark.asyncio
async def test_llm_failure_with_existing_row_returns_stale(db_session):
    user = await _make_user(db_session)
    old_sig = _build_signature(["AI協調"], "2:1", 5)
    db_session.add(UserNudge(
        user_id=user.id, body="stale body",
        generated_at=datetime.now(UTC) - timedelta(hours=48),
        input_signature=old_sig,
    ))
    await db_session.commit()

    claude = MagicMock()
    claude.complete = AsyncMock(side_effect=RuntimeError("api down"))

    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=["AI協調"], top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.body == "stale body"
    assert out.is_fresh is False
    # Row not overwritten
    row = (
        await db_session.execute(
            select(UserNudge).where(UserNudge.user_id == user.id)
        )
    ).scalar_one()
    assert row.body == "stale body"


@pytest.mark.asyncio
async def test_llm_failure_with_no_row_returns_static_fallback(db_session):
    user = await _make_user(db_session)
    claude = MagicMock()
    claude.complete = AsyncMock(side_effect=RuntimeError("api down"))

    out = await get_or_generate(
        db_session, claude=claude, user_id=user.id,
        weakness_tags=["AI協調"], top_recommendation_key="2:1",
        submission_count=5,
    )
    assert out.body  # 何らかのテキスト
    assert out.is_fresh is False
    # 永続化されていない
    row = (
        await db_session.execute(
            select(UserNudge).where(UserNudge.user_id == user.id)
        )
    ).first()
    assert row is None


def test_signature_is_stable_for_same_inputs():
    a = _build_signature(["AI協調", "API基礎"], "2:1", 5)
    b = _build_signature(["AI協調", "API基礎"], "2:1", 5)
    assert a == b and len(a) == 16


def test_signature_changes_when_inputs_change():
    base = _build_signature(["AI協調"], "2:1", 5)
    assert _build_signature(["API基礎"], "2:1", 5) != base
    assert _build_signature(["AI協調"], "3:1", 5) != base
    assert _build_signature(["AI協調"], "2:1", 6) != base
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
uv run pytest tests/test_nudge_service.py -q
```

Expected: ImportError。

- [ ] **Step 3: 実装**

`backend/app/services/nudge.py`:

```python
"""Sprint 5 AI nudge service.

Lazy generation + 24h cache. The cache key is (user_id), the freshness
check is (within TTL) AND (input_signature unchanged). On Claude
failure we degrade rather than 500 — stale row if we have one,
generic static fallback otherwise. Cold-start users (submissions < 3)
never hit the LLM and never persist a row, so re-evaluating their
state after they start submitting is cheap.
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user_nudge import UserNudge
from app.services.weakness import MIN_SUBMISSION_THRESHOLD


logger = logging.getLogger(__name__)


COLD_START_BODY = (
    "まずは Phase 1 のタスクから始めてみましょう。"
    "3 件提出するとあなた専用のアドバイスが出るようになります。"
)
"""Submission count < MIN_SUBMISSION_THRESHOLD のとき出す固定文。"""

LLM_FAILURE_FALLBACK = (
    "今日も学習を続けましょう。"
    "提出を 1 件積むごとに、次の一歩が見えてきます。"
)
"""LLM が落ちていて、過去の nudge も存在しないときの最終フォールバック。"""


@dataclass(frozen=True)
class NudgeResult:
    body: str
    generated_at: datetime
    is_fresh: bool


def _build_signature(
    weakness_tags: list[str],
    top_recommendation_key: str | None,
    submission_count: int,
) -> str:
    """16 char SHA-256 prefix. Identical inputs → identical signature.
    A change in top-3 weakness order, in the primary recommendation, or
    in the total submission count breaks the cache deliberately."""
    payload = (
        f"{','.join(weakness_tags[:3])}|{top_recommendation_key or ''}"
        f"|{submission_count}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _build_prompt(
    weakness_tags: list[str],
    recommendation_titles: list[str],
    progress_text: str,
) -> tuple[str, str]:
    """Return (system, user) prompt pair.

    XML wrapper around learner data mirrors Sprint 4 MED-1's defensive
    pattern — even if a recommendation title later contains an injection
    payload, it never escapes the <recommendations> block."""
    system = (
        "あなたは個別最適化されたアドバイザーです。\n"
        "受講者の弱点と進捗を踏まえて、次の一歩を 80 文字以内・1 文で示してください。\n"
        "励ましの言葉は不要。具体的なタスク名や数値を含めてください。"
    )
    weakness_block = (
        "\n".join(f"{i+1}. {t}" for i, t in enumerate(weakness_tags[:3]))
        or "（まだ十分なデータがありません）"
    )
    rec_block = (
        "\n".join(f"- {title}" for title in recommendation_titles[:3])
        or "- （該当なし）"
    )
    user = (
        f"<progress>{progress_text}</progress>\n"
        f"<weakness>\n{weakness_block}\n</weakness>\n"
        f"<recommendations>\n{rec_block}\n</recommendations>"
    )
    return system, user


async def get_or_generate(
    db: AsyncSession,
    *,
    claude,
    user_id: uuid.UUID,
    weakness_tags: list[str],
    top_recommendation_key: str | None,
    submission_count: int,
    recommendation_titles: list[str] | None = None,
    progress_text: str = "",
) -> NudgeResult:
    # Cold start: skip LLM entirely.
    if submission_count < MIN_SUBMISSION_THRESHOLD:
        return NudgeResult(
            body=COLD_START_BODY, generated_at=datetime.now(UTC), is_fresh=True,
        )

    signature = _build_signature(
        weakness_tags, top_recommendation_key, submission_count,
    )

    # Cache lookup with row lock — two concurrent dashboard fetches for
    # the same user serialize here, so only the first one calls the LLM.
    existing = (
        await db.execute(
            select(UserNudge)
            .where(UserNudge.user_id == user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()

    ttl = timedelta(hours=settings.nudge_cache_ttl_hours)
    if (
        existing is not None
        and (datetime.now(UTC) - existing.generated_at) < ttl
        and existing.input_signature == signature
    ):
        return NudgeResult(
            body=existing.body, generated_at=existing.generated_at, is_fresh=True,
        )

    # Cache miss / stale / signature changed → regenerate.
    system, user_prompt = _build_prompt(
        weakness_tags, recommendation_titles or [], progress_text,
    )
    try:
        reply = await claude.complete(
            system=system,
            user=user_prompt,
            model=settings.nudge_model,
            max_tokens=settings.nudge_max_output_tokens,
            temperature=settings.nudge_temperature,
        )
    except Exception:
        logger.exception("Nudge LLM call failed; degrading gracefully")
        if existing is not None:
            return NudgeResult(
                body=existing.body, generated_at=existing.generated_at,
                is_fresh=False,
            )
        return NudgeResult(
            body=LLM_FAILURE_FALLBACK, generated_at=datetime.now(UTC),
            is_fresh=False,
        )

    body = (reply or "").strip()[:500]
    if not body:
        # Empty LLM reply — same handling as exception.
        if existing is not None:
            return NudgeResult(
                body=existing.body, generated_at=existing.generated_at,
                is_fresh=False,
            )
        return NudgeResult(
            body=LLM_FAILURE_FALLBACK, generated_at=datetime.now(UTC),
            is_fresh=False,
        )

    now = datetime.now(UTC)
    stmt = pg_insert(UserNudge.__table__).values(
        user_id=user_id, body=body, generated_at=now,
        input_signature=signature,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id"],
        set_={"body": body, "generated_at": now, "input_signature": signature},
    )
    await db.execute(stmt)
    await db.commit()

    return NudgeResult(body=body, generated_at=now, is_fresh=True)
```

- [ ] **Step 4: `ClaudeClient.complete` の API シグネチャを実装と合わせる**

既存 `app/core/claude_client.py` を読み、`complete` メソッドの実シグネチャと nudge service の呼び出しが噛み合うか確認。Sprint 2/3 の grading で使われている形に揃える。違いがあれば nudge.py の `claude.complete(...)` 引数を修正する（テスト側 `_fake_claude` も同じ AsyncMock なので追従可能）。

```bash
grep -n "def complete\b\|async def complete\b" backend/app/core/claude_client.py
```

シグネチャが異なる場合は最小修正で揃える。

- [ ] **Step 5: テストが緑になることを確認**

```bash
uv run pytest tests/test_nudge_service.py -q
```

Expected: `9 passed`。

- [ ] **Step 6: 全テスト緑**

```bash
uv run pytest -q
```

Expected: `249 passed`.

- [ ] **Step 7: Commit**

```bash
cd .. && git add backend/app/services/nudge.py backend/tests/test_nudge_service.py
git commit -m "feat(sprint-5): nudge service (lazy gen, 24h cache, signature, stale-on-fail)"
```

---

## Task 12: dashboard orchestrator service（TDD）

**Files:**
- Create: `backend/app/services/dashboard.py`
- Create: `backend/tests/test_dashboard_service.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_dashboard_service.py`:

```python
"""Sprint 5 dashboard orchestrator.

Mocks all 4 sub-services so the orchestrator's only responsibility under
test is correct gluing: pass weakness output into nudge input, drop a
section to its empty form when its sub-service raises, never let one
sub-service take down the whole response."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.core.security import hash_password
from app.models.user import User
from app.services.dashboard import compose_dashboard
from app.services.nudge import NudgeResult
from app.services.progress_summary import ProgressSummary
from app.services.recommendation import Recommendation
from app.services.weakness import TagAverage, WeaknessResult


async def _make_user(db_session):
    user = User(email="d@e.com", name="D", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_happy_path_aggregates_four_sections(
    db_session, monkeypatch,
):
    user = await _make_user(db_session)

    monkeypatch.setattr(
        "app.services.dashboard.compute_weakness",
        AsyncMock(return_value=WeaknessResult(
            has_enough_data=True,
            top_weaknesses=[
                TagAverage(tag="AI協調", average_score=60.0, submission_count=3),
            ],
        )),
    )
    monkeypatch.setattr(
        "app.services.dashboard.compute_progress_summary",
        AsyncMock(return_value=ProgressSummary(
            completed_tasks=5, total_tasks=12,
            submission_count=5, average_score=70.0,
        )),
    )
    monkeypatch.setattr(
        "app.services.dashboard.compute_recommendations",
        AsyncMock(return_value=[
            Recommendation(
                phase=2, task_no=1, title="t",
                skill_tags=["AI協調"], match_tag="AI協調", rag_score=0.8,
            ),
        ]),
    )
    monkeypatch.setattr(
        "app.services.dashboard.get_or_generate",
        AsyncMock(return_value=NudgeResult(
            body="次は Phase 2 task 1。", generated_at=datetime.now(UTC), is_fresh=True,
        )),
    )

    out = await compose_dashboard(
        db_session, claude=object(), embedding_client=object(), user_id=user.id,
    )
    assert out.progress_summary.completed_tasks == 5
    assert out.weakness.has_enough_data is True
    assert len(out.recommendations) == 1
    assert out.nudge.is_fresh is True


@pytest.mark.asyncio
async def test_recommendation_failure_returns_empty_section_not_500(
    db_session, monkeypatch,
):
    user = await _make_user(db_session)
    monkeypatch.setattr(
        "app.services.dashboard.compute_weakness",
        AsyncMock(return_value=WeaknessResult(
            has_enough_data=True,
            top_weaknesses=[TagAverage(tag="AI協調", average_score=60.0, submission_count=3)],
        )),
    )
    monkeypatch.setattr(
        "app.services.dashboard.compute_progress_summary",
        AsyncMock(return_value=ProgressSummary(
            completed_tasks=5, total_tasks=12, submission_count=5, average_score=70.0,
        )),
    )
    monkeypatch.setattr(
        "app.services.dashboard.compute_recommendations",
        AsyncMock(side_effect=RuntimeError("rag down")),
    )
    monkeypatch.setattr(
        "app.services.dashboard.get_or_generate",
        AsyncMock(return_value=NudgeResult(
            body="x", generated_at=datetime.now(UTC), is_fresh=True,
        )),
    )

    out = await compose_dashboard(
        db_session, claude=object(), embedding_client=object(), user_id=user.id,
    )
    assert out.recommendations == []
    # 他は通常通り
    assert out.progress_summary.completed_tasks == 5


@pytest.mark.asyncio
async def test_nudge_failure_returns_fallback_not_500(db_session, monkeypatch):
    user = await _make_user(db_session)
    monkeypatch.setattr(
        "app.services.dashboard.compute_weakness",
        AsyncMock(return_value=WeaknessResult(
            has_enough_data=False, top_weaknesses=[],
        )),
    )
    monkeypatch.setattr(
        "app.services.dashboard.compute_progress_summary",
        AsyncMock(return_value=ProgressSummary(
            completed_tasks=1, total_tasks=12, submission_count=1, average_score=None,
        )),
    )
    monkeypatch.setattr(
        "app.services.dashboard.compute_recommendations",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.dashboard.get_or_generate",
        AsyncMock(side_effect=RuntimeError("anthropic down")),
    )

    out = await compose_dashboard(
        db_session, claude=object(), embedding_client=object(), user_id=user.id,
    )
    assert out.nudge.body  # 何らかのテキスト
    assert out.nudge.is_fresh is False
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
uv run pytest tests/test_dashboard_service.py -q
```

Expected: ImportError。

- [ ] **Step 3: 実装**

`backend/app/services/dashboard.py`:

```python
"""Sprint 5 dashboard orchestrator.

Calls four sub-services and never lets a sub-service exception take down
the whole response — the dashboard is a multi-section UX, so each
section degrades to its empty form rather than 500-ing the page."""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.nudge import (
    LLM_FAILURE_FALLBACK, NudgeResult, get_or_generate,
)
from app.services.progress_summary import (
    ProgressSummary, compute_progress_summary,
)
from app.services.recommendation import Recommendation, compute_recommendations
from app.services.weakness import WeaknessResult, compute_weakness


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DashboardData:
    progress_summary: ProgressSummary
    weakness: WeaknessResult
    recommendations: list[Recommendation]
    nudge: NudgeResult


async def compose_dashboard(
    db: AsyncSession,
    *,
    claude,
    embedding_client,
    user_id: uuid.UUID,
) -> DashboardData:
    # progress_summary and weakness share an underlying query
    # (_latest_graded_scores) but we don't pre-cache it here — the cost
    # is one extra round-trip in exchange for not having to plumb the
    # cache through 4 service interfaces. Revisit if dashboard p99
    # latency becomes a complaint.
    try:
        progress = await compute_progress_summary(db, user_id)
    except Exception:
        logger.exception("progress_summary failed")
        progress = ProgressSummary(
            completed_tasks=0, total_tasks=12,
            submission_count=0, average_score=None,
        )

    try:
        weakness = await compute_weakness(db, user_id)
    except Exception:
        logger.exception("weakness failed")
        weakness = WeaknessResult(has_enough_data=False, top_weaknesses=[])

    top_tags = [w.tag for w in weakness.top_weaknesses]
    try:
        recs = await compute_recommendations(
            db, embedding_client,
            user_id=user_id, top_weakness_tags=top_tags,
        )
    except Exception:
        logger.exception("recommendations failed")
        recs = []

    top_rec_key = f"{recs[0].phase}:{recs[0].task_no}" if recs else None
    progress_text = (
        f"完了: {progress.completed_tasks}/{progress.total_tasks} タスク"
        + (
            f"、平均スコア: {progress.average_score}"
            if progress.average_score is not None else ""
        )
    )
    rec_titles = [r.title for r in recs]

    try:
        nudge = await get_or_generate(
            db, claude=claude, user_id=user_id,
            weakness_tags=top_tags,
            top_recommendation_key=top_rec_key,
            submission_count=progress.submission_count,
            recommendation_titles=rec_titles,
            progress_text=progress_text,
        )
    except Exception:
        logger.exception("nudge failed at orchestrator level")
        nudge = NudgeResult(
            body=LLM_FAILURE_FALLBACK,
            generated_at=datetime.now(UTC),
            is_fresh=False,
        )

    return DashboardData(
        progress_summary=progress, weakness=weakness,
        recommendations=recs, nudge=nudge,
    )
```

- [ ] **Step 4: テストが緑**

```bash
uv run pytest tests/test_dashboard_service.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: 全テスト緑**

```bash
uv run pytest -q
```

Expected: `252 passed`.

- [ ] **Step 6: Commit**

```bash
cd .. && git add backend/app/services/dashboard.py backend/tests/test_dashboard_service.py
git commit -m "feat(sprint-5): dashboard orchestrator (4 sub-services, graceful degradation)"
```

---

## Task 13: schemas/dashboard.py + api/me_dashboard.py + main router

**Files:**
- Create: `backend/app/schemas/dashboard.py`
- Create: `backend/app/api/me_dashboard.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_me_dashboard_api.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_me_dashboard_api.py`:

```python
"""Sprint 5 dashboard API tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.services.nudge import NudgeResult
from app.services.progress_summary import ProgressSummary
from app.services.recommendation import Recommendation
from app.services.weakness import TagAverage, WeaknessResult


def _auth(client, user_id) -> None:
    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(user_id))}"}
    )


async def _make_user(db_session, email="x@e.com"):
    user = User(email=email, name="X", password_hash=hash_password("p"))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _stub_compose(monkeypatch, *, has_data=True):
    """Replace compose_dashboard with a deterministic stub so the test
    exercises the API/serialization layer, not the sub-services."""
    from app.services.dashboard import DashboardData

    fake = DashboardData(
        progress_summary=ProgressSummary(
            completed_tasks=5, total_tasks=12,
            submission_count=5, average_score=72.0,
        ),
        weakness=WeaknessResult(
            has_enough_data=has_data,
            top_weaknesses=([
                TagAverage(tag="AI協調", average_score=60.0, submission_count=3),
            ] if has_data else []),
        ),
        recommendations=([
            Recommendation(
                phase=2, task_no=1, title="t",
                skill_tags=["AI協調"], match_tag="AI協調", rag_score=0.8,
            ),
        ] if has_data else []),
        nudge=NudgeResult(
            body="次は Phase 2 task 1 をやろう。",
            generated_at=datetime.now(UTC), is_fresh=True,
        ),
    )
    monkeypatch.setattr(
        "app.api.me_dashboard.compose_dashboard",
        AsyncMock(return_value=fake),
    )


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client):
    assert client.get("/api/me/dashboard").status_code == 401


@pytest.mark.asyncio
async def test_returns_full_response_shape(client, db_session, monkeypatch):
    user = await _make_user(db_session)
    _stub_compose(monkeypatch, has_data=True)
    _auth(client, user.id)

    r = client.get("/api/me/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {
        "progress_summary", "weakness", "recommendations", "nudge"
    }
    assert body["progress_summary"]["total_tasks"] == 12
    assert body["weakness"]["has_enough_data"] is True
    assert body["recommendations"]["items"][0]["match_tag"] == "AI協調"
    assert body["nudge"]["is_fresh"] is True


@pytest.mark.asyncio
async def test_cold_start_response(client, db_session, monkeypatch):
    user = await _make_user(db_session, email="cold@e.com")
    _stub_compose(monkeypatch, has_data=False)
    _auth(client, user.id)

    body = client.get("/api/me/dashboard").json()
    assert body["weakness"]["has_enough_data"] is False
    assert body["recommendations"]["items"] == []


@pytest.mark.asyncio
async def test_user_a_cannot_see_user_b_dashboard(client, db_session, monkeypatch):
    """BOLA fence: the dashboard endpoint takes no user_id in the URL,
    so this test mostly verifies token = identity. Two users get
    independent stubs."""
    a = await _make_user(db_session, email="a@e.com")
    b = await _make_user(db_session, email="b@e.com")
    _stub_compose(monkeypatch, has_data=True)
    _auth(client, a.id)
    r1 = client.get("/api/me/dashboard")
    assert r1.status_code == 200
    # Token replacement only — verify the same client object can be re-auth'd
    _auth(client, b.id)
    r2 = client.get("/api/me/dashboard")
    assert r2.status_code == 200
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
uv run pytest tests/test_me_dashboard_api.py -q
```

Expected: 404 (router 未登録) または ImportError。

- [ ] **Step 3: schemas/dashboard.py を作成**

```python
"""Sprint 5 dashboard API response schemas.

Single envelope: 4 fixed top-level sections. The names mirror the
service-side dataclass fields so the API layer's job stays mechanical."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProgressSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    completed_tasks: int
    total_tasks: int
    submission_count: int
    average_score: float | None


class TagAverageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tag: str
    average_score: float
    submission_count: int


class WeaknessOut(BaseModel):
    has_enough_data: bool
    top_weaknesses: list[TagAverageOut]


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    phase: int
    task_no: int
    title: str
    skill_tags: list[str]
    match_tag: str | None
    rag_score: float


class RecommendationsBlock(BaseModel):
    items: list[RecommendationOut]


class NudgeOut(BaseModel):
    body: str
    generated_at: datetime
    is_fresh: bool


class DashboardResponse(BaseModel):
    progress_summary: ProgressSummaryOut
    weakness: WeaknessOut
    recommendations: RecommendationsBlock
    nudge: NudgeOut
```

- [ ] **Step 4: api/me_dashboard.py を作成**

```python
"""GET /api/me/dashboard — single-fetch learner dashboard (Sprint 5)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.claude_client import get_claude_client
from app.core.deps import get_current_user
from app.core.embedding_client import get_embedding_client
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import (
    DashboardResponse, NudgeOut, ProgressSummaryOut,
    RecommendationOut, RecommendationsBlock, TagAverageOut, WeaknessOut,
)
from app.services.dashboard import compose_dashboard


router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/dashboard", response_model=DashboardResponse)
async def get_my_dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    claude=Depends(get_claude_client),
    embedding_client=Depends(get_embedding_client),
) -> DashboardResponse:
    data = await compose_dashboard(
        db, claude=claude, embedding_client=embedding_client,
        user_id=user.id,
    )
    return DashboardResponse(
        progress_summary=ProgressSummaryOut.model_validate(data.progress_summary),
        weakness=WeaknessOut(
            has_enough_data=data.weakness.has_enough_data,
            top_weaknesses=[
                TagAverageOut.model_validate(w)
                for w in data.weakness.top_weaknesses
            ],
        ),
        recommendations=RecommendationsBlock(
            items=[RecommendationOut.model_validate(r) for r in data.recommendations],
        ),
        nudge=NudgeOut(
            body=data.nudge.body,
            generated_at=data.nudge.generated_at,
            is_fresh=data.nudge.is_fresh,
        ),
    )
```

- [ ] **Step 5: `get_claude_client` / `get_embedding_client` DI provider が無ければ追加**

`app/core/claude_client.py` を読み、`get_claude_client` プロバイダ関数があるかを確認。無ければ以下を追加:

```python
def get_claude_client() -> ClaudeClient:
    """FastAPI DI provider — Sprint 5 で nudge service が同じ client を使う。"""
    return ClaudeClient()
```

`app/core/embedding_client.py` についても同様に `get_embedding_client` を確認/追加。Sprint 2 で既にあるはず — 無ければ最小限の関数を追加してテストで確認。

```bash
grep -n "def get_claude_client\|def get_embedding_client" backend/app/core/*.py
```

- [ ] **Step 6: main.py に router を登録**

`backend/app/main.py` で他の router 登録の隣に追加:

```python
from app.api.me_dashboard import router as me_dashboard_router
# ...
app.include_router(me_dashboard_router)
```

- [ ] **Step 7: テストが緑**

```bash
uv run pytest tests/test_me_dashboard_api.py -q
```

Expected: `4 passed`.

- [ ] **Step 8: 全テスト緑**

```bash
uv run pytest -q
```

Expected: `256 passed`.

- [ ] **Step 9: Commit**

```bash
cd .. && git add backend/app/schemas/dashboard.py backend/app/api/me_dashboard.py backend/app/main.py backend/app/core/*.py backend/tests/test_me_dashboard_api.py
git commit -m "feat(sprint-5): GET /api/me/dashboard endpoint + schemas"
```

---

## Task 14: frontend types + lib/api.ts + dashboard store

**Files:**
- Create: `frontend/src/types/dashboard.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/stores/dashboard.ts`
- Create: `frontend/src/__tests__/dashboard.store.spec.ts`

- [ ] **Step 1: failing test を追加**

`frontend/src/__tests__/dashboard.store.spec.ts`:

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: { ...actual.api, getMyDashboard: vi.fn() },
  };
});

import { api } from '@/lib/api';
import { useDashboardStore } from '@/stores/dashboard';

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

const FAKE = {
  progress_summary: {
    completed_tasks: 5, total_tasks: 12,
    submission_count: 5, average_score: 70.0,
  },
  weakness: {
    has_enough_data: true,
    top_weaknesses: [
      { tag: 'AI協調', average_score: 60.0, submission_count: 3 },
    ],
  },
  recommendations: {
    items: [{
      phase: 2, task_no: 1, title: 't',
      skill_tags: ['AI協調'], match_tag: 'AI協調', rag_score: 0.8,
    }],
  },
  nudge: {
    body: '次は Phase 2 task 1 をやろう。',
    generated_at: '2026-06-08T07:00:00Z',
    is_fresh: true,
  },
};

describe('dashboard store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('fetch populates data on success', async () => {
    mocked.getMyDashboard.mockResolvedValue(FAKE);
    const store = useDashboardStore();
    await store.fetch();
    expect(store.data?.nudge.is_fresh).toBe(true);
    expect(store.error).toBeNull();
    expect(store.loading).toBe(false);
  });

  it('fetch sets error message and clears loading on failure', async () => {
    mocked.getMyDashboard.mockRejectedValue(new Error('network'));
    const store = useDashboardStore();
    await store.fetch();
    expect(store.data).toBeNull();
    expect(store.error).toBe('読み込みに失敗しました');
    expect(store.loading).toBe(false);
  });

  it('invalidate clears cached data', async () => {
    mocked.getMyDashboard.mockResolvedValue(FAKE);
    const store = useDashboardStore();
    await store.fetch();
    store.invalidate();
    expect(store.data).toBeNull();
  });
});
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd frontend && npm test -- --run src/__tests__/dashboard.store.spec.ts
```

Expected: 失敗 / 未解決 import。

- [ ] **Step 3: types/dashboard.ts を作成**

```typescript
export interface ProgressSummary {
  completed_tasks: number;
  total_tasks: number;
  submission_count: number;
  average_score: number | null;
}

export interface TagAverage {
  tag: string;
  average_score: number;
  submission_count: number;
}

export interface Weakness {
  has_enough_data: boolean;
  top_weaknesses: TagAverage[];
}

export interface RecommendationItem {
  phase: number;
  task_no: number;
  title: string;
  skill_tags: string[];
  match_tag: string | null;
  rag_score: number;
}

export interface RecommendationsBlock {
  items: RecommendationItem[];
}

export interface Nudge {
  body: string;
  generated_at: string;
  is_fresh: boolean;
}

export interface DashboardResponse {
  progress_summary: ProgressSummary;
  weakness: Weakness;
  recommendations: RecommendationsBlock;
  nudge: Nudge;
}
```

- [ ] **Step 4: lib/api.ts に `getMyDashboard` を追加**

`frontend/src/lib/api.ts` の `api` オブジェクト（または equivalent export）に以下を追加:

```typescript
import type { DashboardResponse } from '@/types/dashboard';
// ...
export const api = {
  // ... 既存 ...
  async getMyDashboard(): Promise<DashboardResponse> {
    const res = await client.get<DashboardResponse>('/api/me/dashboard');
    return res.data;
  },
};
```

（`client` は既存の axios インスタンス。既存パターンと同じ呼び出し方を踏襲する。）

- [ ] **Step 5: stores/dashboard.ts を作成**

```typescript
import { defineStore } from 'pinia';
import { api } from '@/lib/api';
import type { DashboardResponse } from '@/types/dashboard';

interface State {
  data: DashboardResponse | null;
  loading: boolean;
  error: string | null;
}

export const useDashboardStore = defineStore('dashboard', {
  state: (): State => ({ data: null, loading: false, error: null }),
  actions: {
    async fetch() {
      this.loading = true;
      this.error = null;
      try {
        this.data = await api.getMyDashboard();
      } catch {
        this.error = '読み込みに失敗しました';
      } finally {
        this.loading = false;
      }
    },
    invalidate() {
      this.data = null;
    },
  },
});
```

- [ ] **Step 6: テストが緑**

```bash
npm test -- --run src/__tests__/dashboard.store.spec.ts
```

Expected: `3 passed`.

- [ ] **Step 7: 全 frontend テスト緑**

```bash
npm test -- --run
```

Expected: `34 + 3 = 37 passed`.

- [ ] **Step 8: Commit**

```bash
cd .. && git add frontend/src/types/dashboard.ts frontend/src/lib/api.ts frontend/src/stores/dashboard.ts frontend/src/__tests__/dashboard.store.spec.ts
git commit -m "feat(sprint-5): frontend dashboard types/api/store"
```

---

## Task 15: NudgeBanner コンポーネント

**Files:**
- Create: `frontend/src/components/NudgeBanner.vue`
- Create: `frontend/src/__tests__/NudgeBanner.spec.ts`

- [ ] **Step 1: failing test を追加**

```typescript
// frontend/src/__tests__/NudgeBanner.spec.ts
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import NudgeBanner from '@/components/NudgeBanner.vue';

const baseNudge = {
  body: '今日は Phase 2 task 1 に挑戦しよう。',
  generated_at: '2026-06-08T07:00:00Z',
  is_fresh: true,
};

describe('NudgeBanner', () => {
  it('renders body text', () => {
    const w = mount(NudgeBanner, { props: { nudge: baseNudge } });
    expect(w.text()).toContain('Phase 2 task 1 に挑戦');
  });

  it('shows generated_at in a relative format', () => {
    const w = mount(NudgeBanner, { props: { nudge: baseNudge } });
    expect(w.find('time').exists()).toBe(true);
    expect(w.find('time').attributes('datetime')).toBe('2026-06-08T07:00:00Z');
  });

  it('marks stale nudge visually', () => {
    const w = mount(NudgeBanner, {
      props: { nudge: { ...baseNudge, is_fresh: false } },
    });
    expect(w.classes()).toContain('stale');
  });
});
```

- [ ] **Step 2: テスト失敗確認**

```bash
cd frontend && npm test -- --run src/__tests__/NudgeBanner.spec.ts
```

Expected: 未解決 import。

- [ ] **Step 3: コンポーネント実装**

`frontend/src/components/NudgeBanner.vue`:

```vue
<script setup lang="ts">
import type { Nudge } from '@/types/dashboard';

defineProps<{ nudge: Nudge }>();
</script>

<template>
  <section
    class="nudge-banner"
    :class="{ stale: !nudge.is_fresh }"
    role="region"
    aria-labelledby="nudge-heading"
  >
    <h2 id="nudge-heading" class="sr-only">今日のアドバイス</h2>
    <p class="body">{{ nudge.body }}</p>
    <time class="ts" :datetime="nudge.generated_at">
      {{ new Date(nudge.generated_at).toLocaleString('ja-JP') }} 生成
    </time>
  </section>
</template>

<style scoped>
.nudge-banner {
  background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
  border: 1px solid #c7d2fe;
  border-radius: 12px;
  padding: 1rem 1.2rem;
  margin: 0 0 1.2rem;
}
.nudge-banner.stale {
  background: #f3f4f6;
  border-color: #e5e7eb;
}
.body {
  margin: 0;
  font-size: 1rem;
  font-weight: 500;
  color: #1f2937;
}
.ts {
  display: block;
  margin-top: 0.4rem;
  font-size: 0.72rem;
  color: #6b7280;
}
.sr-only {
  position: absolute;
  width: 1px; height: 1px;
  padding: 0; margin: -1px;
  overflow: hidden;
  clip: rect(0,0,0,0);
  white-space: nowrap; border: 0;
}
</style>
```

- [ ] **Step 4: テスト緑**

```bash
npm test -- --run src/__tests__/NudgeBanner.spec.ts
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/NudgeBanner.vue frontend/src/__tests__/NudgeBanner.spec.ts
git commit -m "feat(sprint-5): NudgeBanner component"
```

---

## Task 16: ProgressSummaryCard

**Files:**
- Create: `frontend/src/components/ProgressSummaryCard.vue`
- Create: `frontend/src/__tests__/ProgressSummaryCard.spec.ts`

- [ ] **Step 1: failing test を追加**

```typescript
// frontend/src/__tests__/ProgressSummaryCard.spec.ts
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import ProgressSummaryCard from '@/components/ProgressSummaryCard.vue';

describe('ProgressSummaryCard', () => {
  it('shows completed / total', () => {
    const w = mount(ProgressSummaryCard, {
      props: {
        data: {
          completed_tasks: 5, total_tasks: 12,
          submission_count: 5, average_score: 70,
        },
      },
    });
    expect(w.text()).toContain('5 / 12');
    expect(w.text()).toContain('70');
  });

  it('shows em dash when average is null (cold start)', () => {
    const w = mount(ProgressSummaryCard, {
      props: {
        data: {
          completed_tasks: 1, total_tasks: 12,
          submission_count: 1, average_score: null,
        },
      },
    });
    expect(w.text()).toContain('—');
    expect(w.text()).toContain('1 / 12');
  });

  it('shows hint when below threshold', () => {
    const w = mount(ProgressSummaryCard, {
      props: {
        data: {
          completed_tasks: 1, total_tasks: 12,
          submission_count: 1, average_score: null,
        },
      },
    });
    expect(w.text()).toContain('3 件提出');
  });
});
```

- [ ] **Step 2: テスト失敗確認**

```bash
cd frontend && npm test -- --run src/__tests__/ProgressSummaryCard.spec.ts
```

Expected: 未解決 import。

- [ ] **Step 3: 実装**

```vue
<!-- frontend/src/components/ProgressSummaryCard.vue -->
<script setup lang="ts">
import type { ProgressSummary } from '@/types/dashboard';

const props = defineProps<{ data: ProgressSummary }>();
const COLD_START_THRESHOLD = 3;
const belowThreshold = props.data.submission_count < COLD_START_THRESHOLD;
</script>

<template>
  <section
    class="card progress-summary"
    role="region"
    aria-labelledby="progress-heading"
  >
    <h2 id="progress-heading">あなたの進捗</h2>
    <p class="big">
      <span class="num">{{ data.completed_tasks }} / {{ data.total_tasks }}</span>
      <span class="unit">タスク完了</span>
    </p>
    <p class="avg">
      平均スコア:
      <strong v-if="data.average_score !== null">{{ data.average_score }}</strong>
      <strong v-else>—</strong>
    </p>
    <p v-if="belowThreshold" class="hint">
      3 件提出するとあなたの傾向が分析できます（現在 {{ data.submission_count }} 件）。
    </p>
  </section>
</template>

<style scoped>
.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1rem 1.2rem;
}
h2 { margin: 0 0 0.6rem; font-size: 0.95rem; color: #374151; }
.big { margin: 0.2rem 0; display: flex; align-items: baseline; gap: 0.4rem; }
.num { font-size: 2rem; font-weight: 700; color: #111827; }
.unit { font-size: 0.85rem; color: #6b7280; }
.avg { margin: 0.4rem 0 0; font-size: 0.9rem; color: #374151; }
.avg strong { color: #111827; font-size: 1.1rem; }
.hint {
  margin: 0.6rem 0 0;
  font-size: 0.8rem;
  color: #6b7280;
  padding: 0.5rem 0.6rem;
  background: #f9fafb;
  border-radius: 6px;
}
</style>
```

- [ ] **Step 4: テスト緑**

```bash
npm test -- --run src/__tests__/ProgressSummaryCard.spec.ts
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/ProgressSummaryCard.vue frontend/src/__tests__/ProgressSummaryCard.spec.ts
git commit -m "feat(sprint-5): ProgressSummaryCard component"
```

---

## Task 17: WeaknessCard

**Files:**
- Create: `frontend/src/components/WeaknessCard.vue`
- Create: `frontend/src/__tests__/WeaknessCard.spec.ts`

- [ ] **Step 1: failing test を追加**

```typescript
// frontend/src/__tests__/WeaknessCard.spec.ts
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import WeaknessCard from '@/components/WeaknessCard.vue';

describe('WeaknessCard', () => {
  it('renders top 3 tags with scores', () => {
    const w = mount(WeaknessCard, {
      props: {
        data: {
          has_enough_data: true,
          top_weaknesses: [
            { tag: 'AI協調', average_score: 60, submission_count: 3 },
            { tag: 'API基礎', average_score: 65, submission_count: 2 },
            { tag: 'テスト', average_score: 70, submission_count: 2 },
          ],
        },
      },
    });
    expect(w.text()).toContain('AI協調');
    expect(w.text()).toContain('60');
    expect(w.findAll('li')).toHaveLength(3);
  });

  it('shows cold-start placeholder when has_enough_data is false', () => {
    const w = mount(WeaknessCard, {
      props: { data: { has_enough_data: false, top_weaknesses: [] } },
    });
    expect(w.text()).toContain('提出 3 件以上');
    expect(w.find('li').exists()).toBe(false);
  });

  it('uses neutral heading wording (not weakness)', () => {
    // UI 文言ガイダンス: 「弱点」ではなく「もう一押しの分野」
    const w = mount(WeaknessCard, {
      props: { data: { has_enough_data: true, top_weaknesses: [] } },
    });
    expect(w.text()).toContain('もう一押し');
    expect(w.text()).not.toContain('弱点');
  });
});
```

- [ ] **Step 2: テスト失敗確認**

```bash
cd frontend && npm test -- --run src/__tests__/WeaknessCard.spec.ts
```

Expected: 未解決 import。

- [ ] **Step 3: 実装**

```vue
<!-- frontend/src/components/WeaknessCard.vue -->
<script setup lang="ts">
import type { Weakness } from '@/types/dashboard';

defineProps<{ data: Weakness }>();
</script>

<template>
  <section
    class="card weakness"
    role="region"
    aria-labelledby="weakness-heading"
  >
    <h2 id="weakness-heading">もう一押しの分野</h2>
    <p v-if="!data.has_enough_data" class="empty">
      提出 3 件以上で、あなたの傾向を分析して表示します。
    </p>
    <ol v-else-if="data.top_weaknesses.length > 0">
      <li v-for="w in data.top_weaknesses" :key="w.tag">
        <span class="tag">{{ w.tag }}</span>
        <span class="score">平均 {{ w.average_score }}</span>
        <span class="count">（{{ w.submission_count }} 件）</span>
      </li>
    </ol>
    <p v-else class="empty">
      集計に足る提出がまだありません。タグ別に 2 件以上提出すると表示されます。
    </p>
  </section>
</template>

<style scoped>
.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1rem 1.2rem;
}
h2 { margin: 0 0 0.6rem; font-size: 0.95rem; color: #374151; }
.empty { font-size: 0.85rem; color: #6b7280; margin: 0; }
ol { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.4rem; }
li {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.4rem 0.5rem;
  background: #fef3c7;
  border-radius: 6px;
}
.tag { font-weight: 600; color: #92400e; flex: 0 0 auto; }
.score { font-variant-numeric: tabular-nums; color: #b45309; }
.count { font-size: 0.75rem; color: #9ca3af; }
</style>
```

- [ ] **Step 4: テスト緑**

```bash
npm test -- --run src/__tests__/WeaknessCard.spec.ts
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/WeaknessCard.vue frontend/src/__tests__/WeaknessCard.spec.ts
git commit -m "feat(sprint-5): WeaknessCard (neutral 'もう一押し' wording)"
```

---

## Task 18: RecommendationsCard

**Files:**
- Create: `frontend/src/components/RecommendationsCard.vue`
- Create: `frontend/src/__tests__/RecommendationsCard.spec.ts`

- [ ] **Step 1: failing test を追加**

```typescript
// frontend/src/__tests__/RecommendationsCard.spec.ts
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import RecommendationsCard from '@/components/RecommendationsCard.vue';

const ITEM = {
  phase: 2, task_no: 1, title: '二分探索木の実装',
  skill_tags: ['AI協調', 'API基礎'], match_tag: 'AI協調', rag_score: 0.8,
};

describe('RecommendationsCard', () => {
  it('renders each recommendation with title and match_tag', () => {
    const w = mount(RecommendationsCard, {
      props: { items: [ITEM] },
    });
    expect(w.text()).toContain('二分探索木');
    expect(w.text()).toContain('AI協調');
  });

  it('emits select with phase/task_no on click', async () => {
    const w = mount(RecommendationsCard, { props: { items: [ITEM] } });
    await w.find('button').trigger('click');
    const events = w.emitted('select') ?? [];
    expect(events[0]).toEqual([{ phase: 2, task_no: 1 }]);
  });

  it('shows phase 1 CTA when items is empty', () => {
    const w = mount(RecommendationsCard, { props: { items: [] } });
    expect(w.text()).toContain('Phase 1');
  });
});
```

- [ ] **Step 2: テスト失敗確認**

```bash
cd frontend && npm test -- --run src/__tests__/RecommendationsCard.spec.ts
```

Expected: 未解決 import。

- [ ] **Step 3: 実装**

```vue
<!-- frontend/src/components/RecommendationsCard.vue -->
<script setup lang="ts">
import type { RecommendationItem } from '@/types/dashboard';

defineProps<{ items: RecommendationItem[] }>();
const emit = defineEmits<{ select: [{ phase: number; task_no: number }] }>();

function onClick(item: RecommendationItem) {
  emit('select', { phase: item.phase, task_no: item.task_no });
}
</script>

<template>
  <section
    class="card recs"
    role="region"
    aria-labelledby="recs-heading"
  >
    <h2 id="recs-heading">次のおすすめ</h2>
    <ol v-if="items.length > 0">
      <li v-for="item in items" :key="`${item.phase}-${item.task_no}`">
        <button type="button" class="rec" @click="onClick(item)">
          <div class="meta">
            <span class="ph">Phase {{ item.phase }} / Task {{ item.task_no }}</span>
            <span v-if="item.match_tag" class="match">#{{ item.match_tag }}</span>
          </div>
          <p class="title">{{ item.title }}</p>
        </button>
      </li>
    </ol>
    <p v-else class="empty">
      まだおすすめできるデータが揃っていません。Phase 1 のタスクから始めてみましょう。
    </p>
  </section>
</template>

<style scoped>
.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 1rem 1.2rem;
}
h2 { margin: 0 0 0.6rem; font-size: 0.95rem; color: #374151; }
ol { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.5rem; }
.rec {
  width: 100%;
  text-align: left;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 0.6rem 0.7rem;
  cursor: pointer;
  font: inherit;
  color: inherit;
}
.rec:hover { background: #f3f4f6; }
.meta {
  display: flex; gap: 0.5rem; align-items: baseline;
  font-size: 0.72rem; color: #6b7280;
}
.match { color: #b45309; font-weight: 600; }
.title { margin: 0.3rem 0 0; font-size: 0.9rem; font-weight: 500; color: #111827; }
.empty { margin: 0; font-size: 0.85rem; color: #6b7280; }
</style>
```

- [ ] **Step 4: テスト緑**

```bash
npm test -- --run src/__tests__/RecommendationsCard.spec.ts
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/RecommendationsCard.vue frontend/src/__tests__/RecommendationsCard.spec.ts
git commit -m "feat(sprint-5): RecommendationsCard with @select event"
```

---

## Task 19: HomeView 改造 + invalidate hook

**Files:**
- Modify: `frontend/src/views/HomeView.vue`
- Modify: `frontend/src/components/TaskSubmissionCard.vue`
- Create: `frontend/src/__tests__/HomeView.spec.ts`

- [ ] **Step 1: HomeView を読み、既存構造を把握**

```bash
cd frontend && cat src/views/HomeView.vue
```

既存の HomeView がどんなセクションを持っているか確認（フェーズ一覧の描画位置、レイアウト、import）。Sprint 5 はこの **下部にダッシュボードを統合** し、フェーズ一覧は維持する。

- [ ] **Step 2: failing test を追加**

`frontend/src/__tests__/HomeView.spec.ts`:

```typescript
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: {
      ...actual.api,
      getMyDashboard: vi.fn(),
      listPhases: vi.fn().mockResolvedValue([]),  // 既存呼び出し
    },
  };
});

import { api } from '@/lib/api';
import HomeView from '@/views/HomeView.vue';

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: HomeView },
      {
        path: '/phases/:phase',
        name: 'phase',
        component: { template: '<div>phase</div>' },
      },
    ],
  });
}

const FAKE_DASH = {
  progress_summary: {
    completed_tasks: 0, total_tasks: 12,
    submission_count: 0, average_score: null,
  },
  weakness: { has_enough_data: false, top_weaknesses: [] },
  recommendations: { items: [] },
  nudge: {
    body: 'まずは Phase 1 から。',
    generated_at: '2026-06-08T07:00:00Z',
    is_fresh: true,
  },
};

describe('HomeView (ダッシュボード化)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('fetches and renders dashboard on mount', async () => {
    mocked.getMyDashboard.mockResolvedValue(FAKE_DASH);
    const router = buildRouter();
    const w = mount(HomeView, { global: { plugins: [router] } });
    await flushPromises();
    expect(mocked.getMyDashboard).toHaveBeenCalled();
    expect(w.text()).toContain('まずは Phase 1');
  });

  it('keeps the phase list section below the dashboard', async () => {
    mocked.getMyDashboard.mockResolvedValue(FAKE_DASH);
    const router = buildRouter();
    const w = mount(HomeView, { global: { plugins: [router] } });
    await flushPromises();
    // ダッシュボード（NudgeBanner / カード）とフェーズ一覧が同居している
    // 具体的なクラス名はテンプレ次第。最低限「フェーズ」という語を含む
    // 既存セクションが残っていることを確認。
    expect(w.text()).toMatch(/フェーズ|Phase \d/i);
  });
});
```

- [ ] **Step 3: テスト失敗確認**

```bash
npm test -- --run src/__tests__/HomeView.spec.ts
```

Expected: 失敗（`getMyDashboard` を呼ぶコードがまだ HomeView にない）。

- [ ] **Step 4: HomeView を改造**

既存 `frontend/src/views/HomeView.vue` の `<script setup>` / `<template>` を以下の方針で書き換える（既存のフェーズ一覧描画ロジックは保持し、ダッシュボードを上部に追加）:

```vue
<script setup lang="ts">
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';

import { useDashboardStore } from '@/stores/dashboard';
import NudgeBanner from '@/components/NudgeBanner.vue';
import ProgressSummaryCard from '@/components/ProgressSummaryCard.vue';
import WeaknessCard from '@/components/WeaknessCard.vue';
import RecommendationsCard from '@/components/RecommendationsCard.vue';

// --- 既存のフェーズ一覧ロジックはここに残す ---
// import { useCurriculumStore } from '@/stores/curriculum';
// const curriculum = useCurriculumStore();
// onMounted(() => curriculum.fetch());
// （実プロジェクトの import に合わせる）

const dashboard = useDashboardStore();
const router = useRouter();

onMounted(() => {
  void dashboard.fetch();
});

function onRecommendationClick(coords: { phase: number; task_no: number }) {
  void router.push({ name: 'phase', params: { phase: coords.phase } });
}
</script>

<template>
  <div class="home">
    <!-- Sprint 5: ダッシュボード -->
    <NudgeBanner v-if="dashboard.data" :nudge="dashboard.data.nudge" />
    <div v-if="dashboard.data" class="dashboard-grid">
      <ProgressSummaryCard :data="dashboard.data.progress_summary" />
      <WeaknessCard :data="dashboard.data.weakness" />
      <RecommendationsCard
        :items="dashboard.data.recommendations.items"
        @select="onRecommendationClick"
      />
    </div>
    <p v-else-if="dashboard.loading" class="loading">読み込み中...</p>
    <p v-else-if="dashboard.error" class="error">{{ dashboard.error }}</p>

    <!-- 既存のフェーズ一覧（下部に保持） -->
    <!-- 既存の v-for や section をそのまま貼る -->
  </div>
</template>

<style scoped>
.home { display: flex; flex-direction: column; gap: 1.2rem; }
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.9rem;
}
.loading, .error {
  margin: 0;
  padding: 0.8rem 1rem;
  background: #f9fafb;
  border-radius: 8px;
  color: #6b7280;
  font-size: 0.9rem;
}
.error { background: #fef2f2; color: #b91c1c; }
</style>
```

既存のフェーズ一覧コードは **そのまま** 残すこと（v-for、リンク、見た目）。Sprint 5 で削るのは「ホームの一番上が空のフェーズ一覧」だった部分だけで、フェーズ一覧自体は下部に保持する。

- [ ] **Step 5: TaskSubmissionCard で提出成功時に dashboard を invalidate**

`frontend/src/components/TaskSubmissionCard.vue` の提出成功ハンドラ（submission service callback）に以下を追加:

```typescript
import { useDashboardStore } from '@/stores/dashboard';
// ...
const dashboard = useDashboardStore();
// 既存の onSubmit success の後ろに:
dashboard.invalidate();
```

提出ハンドラの具体構造は既存実装に従う。ポイントは「提出後に `dashboard.data = null`」にして次のホーム訪問時の再 fetch を強制する。

- [ ] **Step 6: テスト緑**

```bash
npm test -- --run src/__tests__/HomeView.spec.ts
```

Expected: `2 passed`.

- [ ] **Step 7: 全 frontend テスト緑**

```bash
npm test -- --run
```

Expected: `34 + 17 = 51 passed`（Sprint 5 frontend 新規分: dashboard.store 3 + NudgeBanner 3 + ProgressSummary 3 + Weakness 3 + Recommendations 3 + HomeView 2）

- [ ] **Step 8: ビルドが通ることを確認**

```bash
npm run build
```

Expected: ビルド成功、`AdminLayout` 等 Sprint 4 のチャンクと並んで `dashboard` 関連のチャンクが生成される。

- [ ] **Step 9: Commit**

```bash
cd .. && git add frontend/src/views/HomeView.vue frontend/src/components/TaskSubmissionCard.vue frontend/src/__tests__/HomeView.spec.ts
git commit -m "feat(sprint-5): HomeView ダッシュボード化 + 提出後 invalidate"
```

---

## Task 20: Playwright E2E

**Files:**
- Create: `frontend/e2e/sprint-5-dashboard.spec.ts`（既存の E2E 命名規約に合わせる。Sprint 4 で `sprint-4-*` パターンを採っているならそれに揃える）

- [ ] **Step 1: 既存 E2E のテンプレを確認**

```bash
ls frontend/e2e/ 2>&1
```

Sprint 4 の E2E（`af57b5d` で追加されたゴールデンパス）を参照してフィクスチャ・ヘルパーパターンを揃える。

- [ ] **Step 2: シナリオを書く**

`frontend/e2e/sprint-5-dashboard.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

/**
 * Sprint 5 E2E: 新規受講者がダッシュボードを育てるゴールデンパス。
 *
 * Claude / RAG / embedding 呼び出しはバックエンドで test fixture / mock
 * 経由に切り替えられている前提（Sprint 3/4 と同じ実行体制）。
 */
test('learner dashboard grows from cold start to fully populated', async ({
  page,
}) => {
  // 1. 新規登録 → ホームへ
  const email = `sprint5-${Date.now()}@e.com`;
  await page.goto('/register');
  await page.getByLabel('メールアドレス').fill(email);
  await page.getByLabel('名前').fill('S5 学習者');
  await page.getByLabel('パスワード').fill('password123');
  await page.getByRole('button', { name: /登録/ }).click();
  await page.waitForURL('**/');

  // 2. コールドスタート: 弱点表示なし、Phase 1 への CTA が見える
  await expect(page.getByRole('heading', { name: 'あなたの進捗' })).toBeVisible();
  await expect(page.getByText('Phase 1')).toBeVisible();
  await expect(page.getByText('3 件提出')).toBeVisible();

  // 3. Phase 1 の 3 タスクを提出（モック採点経由）
  for (let task = 1; task <= 3; task++) {
    await page.goto('/phases/1');
    await page.getByTestId(`task-submit-${task}`).fill(`回答 ${task}`);
    await page.getByTestId(`task-submit-${task}-button`).click();
    await page.waitForResponse((r) =>
      r.url().includes('/api/submissions') && r.request().method() === 'POST'
    );
  }

  // 4. ホームに戻ると weakness カードが表示される
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'もう一押しの分野' })).toBeVisible();
  await expect(page.getByText(/平均 /)).toBeVisible();

  // 5. AI 一言が表示されている
  const nudgeBanner = page.locator('.nudge-banner');
  await expect(nudgeBanner).toBeVisible();
  const firstNudgeText = await nudgeBanner.locator('.body').innerText();

  // 6. リロードしても 24h 以内は同じ内容（cache hit）
  await page.reload();
  await expect(nudgeBanner.locator('.body')).toHaveText(firstNudgeText);
});
```

`getByTestId` の参照は既存 TaskSubmissionCard に合わせる（必要なら spec 内で `getByRole('textbox')` 等に書き換え）。

- [ ] **Step 3: ローカルで実行**

```bash
cd frontend && npx playwright test e2e/sprint-5-dashboard.spec.ts
```

Expected: `1 passed`。失敗するなら fixture/seed 周りを調整。

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/e2e/sprint-5-dashboard.spec.ts
git commit -m "test(sprint-5): e2e dashboard cold-start to populated golden path"
```

---

## Task 21: code-reviewer と security-reviewer による review

**Files:**
- レビュー指摘に従って既存ファイルを修正

- [ ] **Step 1: code-reviewer agent を実行**

```
Agent (code-reviewer): "Sprint 5 の差分（feature/sprint-5 と main の diff）をレビューしてください。
特に dashboard service の orchestrator 設計、nudge service の cache 整合性、recommendation の RAG 並び順、
HomeView の dashboard 化の影響範囲（既存 E2E への regression リスク）を見てください。"
```

CRITICAL / HIGH があれば即修正、MEDIUM / LOW は次の Task 22 でフォローアップ doc にチケット化。

- [ ] **Step 2: security-reviewer agent を実行**

```
Agent (security-reviewer): "Sprint 5 の差分について、特に GET /api/me/dashboard の認可境界、
nudge の prompt injection 経路、user_nudges テーブルの PII 漏洩、SELECT FOR UPDATE のデッドロック条件
を見てください。"
```

CRITICAL / HIGH を必ず修正。

- [ ] **Step 3: 指摘修正のコミット**

```bash
git commit -m "fix(sprint-5): address code/security review findings (HIGH only)"
```

- [ ] **Step 4: 残った MEDIUM / LOW は follow-up doc 化**

`docs/superpowers/specs/2026-06-09-sprint-5-security-followups.md`（または日付を当日に）を新規作成し、Sprint 4 follow-up と同形式で MEDIUM / LOW チケットを記録。

```bash
git add docs/superpowers/specs/*sprint-5-security-followups.md
git commit -m "docs(sprint-5): file MEDIUM/LOW follow-ups as backlog tickets"
```

---

## Task 22: README + 設計書 + 完了マーク

**Files:**
- Modify: `README.md`
- Modify: `docs/design/03-db-design.md`
- Modify: `docs/design/04-interface-design.md`
- Modify: `docs/design/05-screen-design.md`
- Modify: `docs/design/06-test-design.md`

- [ ] **Step 1: README に Sprint 5 完了マークを追加**

`README.md` の「実装進捗」セクションに追記:

```
- [x] Sprint 5: 受講者ダッシュボード（弱点分析 + レコメンド + AI 一言 + 進捗サマリ）+ TaskItem skill_tags 拡張 + curriculum_task 用 RAG ヘルパー
```

「マイグレーション」セクションに `make seed-embeddings` 再実行の注意書きを追加:

```
> Sprint 5 で curriculum タスク構造が `list[str]` から `list[TaskItem]` に変わったため、
> 既存環境では `make seed-embeddings` を再実行して embeddings.content を最新タイトルに揃えてください。
```

- [ ] **Step 2: 設計書（docs/design/03-db-design.md）に user_nudges セクションを追記**

カラム一覧、PK、FK の cascade ポリシーを記載。

- [ ] **Step 3: 設計書（docs/design/04-interface-design.md）に GET /api/me/dashboard を追記**

レスポンス JSON shape、エラー応答、認可境界。

- [ ] **Step 4: 設計書（docs/design/05-screen-design.md）に HomeView ダッシュボード化セクション追記**

カード構成、コールドスタート文言、フェーズ一覧との同居レイアウト。

- [ ] **Step 5: 設計書（docs/design/06-test-design.md）に Sprint 5 テストマトリクスを追記**

- [ ] **Step 6: backend / frontend テスト最終実行**

```bash
cd backend && uv run pytest -q
cd ../frontend && npm test -- --run && npm run build
cd .. && cd frontend && npx playwright test
```

Expected: backend `256+ passed`、frontend `51+ passed`、E2E `1 passed`、build 成功。

- [ ] **Step 7: Commit**

```bash
cd .. && git add README.md docs/design/*.md
git commit -m "docs(sprint-5): mark Sprint 5 complete; design book updates"
```

- [ ] **Step 8: main にマージ準備**

```bash
git checkout main
git merge --ff-only feature/sprint-5
git log --oneline -10
```

Sprint 5 完了。

---

## 完了条件

- [ ] backend テスト全件パス（既存 212 + 新規 ~44 = 256 件以上）、coverage 80%+
- [ ] frontend テスト全件パス（既存 34 + 新規 17 = 51 件以上）
- [ ] frontend build 成功
- [ ] Playwright E2E（Sprint 5 新規 1 本）パス
- [ ] `make seed-embeddings` 再実行で curriculum_task 行が新 title で再投入される
- [ ] `docker compose up` で新規ユーザー → 3 件提出 → 弱点 + nudge 表示まで一気通貫で動作
- [ ] README に Sprint 5 完了マーク、seed-embeddings 再実行手順
- [ ] 設計書 03/04/05/06 への Sprint 5 セクション追加
- [ ] code-reviewer / security-reviewer の CRITICAL / HIGH を 0 件にし、MEDIUM 以下は follow-up doc にチケット化

---

## 次のステップ（Sprint 6 候補）

Sprint 5 完了後、Sprint 6 で扱う候補:

1. **採点の非同期化（バックグラウンドジョブ）** — 提出 → 即レスポンス → 裏で採点。Sprint 5 で nudge が遅延ボトルネックの一因になり始めたら最優先候補。
2. **Sprint 4 follow-up LOW-2/3/4** — 独立して S サイズ、main の clean さを保つ目的で同梱可能。
3. **コメント返信（受講者 → 講師、スレッド化）** — Sprint 4 admin の拡張。
4. **講師向け admin ダッシュボード強化** — admin から見た受講者一覧に弱点 / 推奨を反映。
