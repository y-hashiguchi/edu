# AIチューターカリキュラム Sprint 0 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI駆動型開発カリキュラム（4フェーズ）のAIチューター対話MVPを、FastAPI+Vue.js スケルトン上で動作する形まで構築する。認証・DB・進捗管理は本Sprintには含めない。

**Architecture:** バックエンドはFastAPIでカリキュラムデータをPython定数ファイルから配信し、Claude API（Anthropic SDK）にフェーズ別システムプロンプトを切り替えて投げる。会話履歴は本Sprintではプロセス内メモリ保持（user_id+phaseキー）。フロントエンドはVue 3+Vite+Pinia+Vue Routerで、フェーズ選択→チャット画面の最小フローを提供。Docker Composeでbackend/frontendを同時起動し、ローカル開発の入り口を統一する。

**Tech Stack:**
- Backend: Python 3.12 / FastAPI / Pydantic v2 / Anthropic Python SDK / pytest / httpx
- Frontend: Vue 3 / TypeScript / Vite / Pinia / Vue Router / vitest / Playwright（smoke用、Sprint 0では任意）
- Infra: Docker Compose / .env
- AI: Anthropic Claude（環境変数 `ANTHROPIC_MODEL` でモデル切替。デフォルト `claude-sonnet-4-5`。HANDOVERの `claude-sonnet-4-20250514` は古い表記なので採用しない）

---

## スコープ境界

**含む（Sprint 0）：**
- `/Volumes/Seagate3TB/projects/edu/` 配下にプロジェクトスケルトン新設
- 4フェーズ分のカリキュラムデータをPython定数で定義
- `GET /api/curriculum/phases` でフェーズ一覧JSON配信
- `POST /api/chat` でAIチューター応答（履歴はプロセス内辞書）
- Vue画面：フェーズ選択 → フェーズ詳細＋チャット
- Docker Composeで `make dev` 相当の起動が成立

**含まない（後続Sprint）：**
- JWT認証 / ユーザー管理 / RBAC
- PostgreSQL + pgvector + Alembic マイグレーション
- 進捗管理・フェーズ解放ロック
- 課題提出 / AI採点
- 管理者ダッシュボード
- 会話履歴のDB永続化（メモリ実装にとどめる）

後続スプリントは末尾「ロードマップ」を参照。

---

## ファイル構造

新規作成するファイルと責務:

```
edu/
├── .env.example                  # 環境変数テンプレート
├── .gitignore                    # Python/Node/IDE系の除外
├── docker-compose.yml            # backend + frontend 一括起動
├── Makefile                      # dev / test / lint ショートカット
├── README.md                     # セットアップと起動手順
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml            # 依存定義（uv/pip対応）
│   ├── pytest.ini                # テスト設定
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI起動 + ルーター登録 + CORS
│   │   ├── config.py             # Settings（pydantic-settings）
│   │   ├── data/
│   │   │   ├── __init__.py
│   │   │   └── curriculum.py     # 4フェーズのカリキュラム定数
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── claude_client.py  # Anthropic SDKラッパー
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   └── chat_store.py     # in-memory 会話履歴ストア
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py           # ChatRequest / ChatResponse
│   │   │   └── curriculum.py     # Phase / Task DTO
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── health.py         # GET /healthz
│   │       ├── curriculum.py     # GET /api/curriculum/phases
│   │       └── chat.py           # POST /api/chat
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py           # FastAPI TestClient + ANTHROPIC mock
│       ├── test_curriculum_data.py
│       ├── test_health.py
│       ├── test_claude_client.py
│       ├── test_chat_store.py
│       ├── test_api_curriculum.py
│       └── test_api_chat.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── env.d.ts
│       ├── router/
│       │   └── index.ts
│       ├── stores/
│       │   └── curriculum.ts     # Pinia store
│       ├── lib/
│       │   └── api.ts            # fetch ラッパー
│       ├── types/
│       │   └── curriculum.ts     # 型定義
│       ├── views/
│       │   ├── HomeView.vue      # フェーズ一覧
│       │   └── PhaseChatView.vue # フェーズ詳細 + チャット
│       └── components/
│           ├── PhaseCard.vue
│           ├── ChatLog.vue
│           ├── ChatMessage.vue
│           └── ChatInput.vue
└── docs/
    └── superpowers/
        └── plans/
            └── 2026-06-01-ai-tutor-curriculum-sprint-0.md  # 本書
```

設計の意図:
- `data/curriculum.py` は単一source of truth。スキーマ（DTO）と分離し、API層はpydanticモデルでバリデーションする
- `core/claude_client.py` はAnthropic SDKの薄いラッパー。テスト時にmock差し替えできるよう、`get_claude_client()` を `Depends` で注入
- `memory/chat_store.py` はSprint 0専用。Sprint 1でDB実装に差し替える際、同じインタフェース（`get_history` / `append`）を保つ
- フロントエンドは「フェーズ一覧 → フェーズ詳細＋チャット」の2画面のみ。コンポーネントは表示単位で分割

---

## Task 1: プロジェクト基本ファイルの作成

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/.gitignore`
- Create: `/Volumes/Seagate3TB/projects/edu/.env.example`
- Create: `/Volumes/Seagate3TB/projects/edu/README.md`
- Create: `/Volumes/Seagate3TB/projects/edu/Makefile`

- [ ] **Step 1: `.gitignore` を作成**

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/

# Node
node_modules/
dist/
.vite/

# Env
.env
.env.local

# IDE
.idea/
.vscode/
.DS_Store
```

- [ ] **Step 2: `.env.example` を作成**

```dotenv
# Anthropic Claude API
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-sonnet-4-5

# Backend
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ALLOW_ORIGINS=http://localhost:5173

# Frontend
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 3: `README.md` を作成**

````markdown
# AI駆動型開発 補足カリキュラム — AIチューター

FastAPI + Vue.js による AI駆動型開発カリキュラム学習支援ツールのリファレンス実装。

## セットアップ

```bash
cp .env.example .env
# .env を編集して ANTHROPIC_API_KEY を設定
```

## 開発起動

### Docker Composeで起動

```bash
make dev
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

### ローカル直接起動

```bash
# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## テスト

```bash
make test
```

## ディレクトリ構成

`docs/superpowers/plans/2026-06-01-ai-tutor-curriculum-sprint-0.md` を参照。
````

- [ ] **Step 4: `Makefile` を作成**

```makefile
.PHONY: dev test test-backend test-frontend lint clean

dev:
	docker compose up --build

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest -v

test-frontend:
	cd frontend && npm run test

lint:
	cd backend && uv run ruff check app tests
	cd frontend && npm run lint

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
```

- [ ] **Step 5: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git init
git add .gitignore .env.example README.md Makefile
git commit -m "chore: bootstrap project root scaffolding"
```

---

## Task 2: バックエンドの依存定義とパッケージ初期化

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/pyproject.toml`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/pytest.ini`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/__init__.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/__init__.py`

- [ ] **Step 1: `backend/pyproject.toml` を作成**

```toml
[project]
name = "ai-tutor-backend"
version = "0.1.0"
description = "AI tutor curriculum backend"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "anthropic>=0.39.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.7.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

- [ ] **Step 2: `backend/pytest.ini` を作成**

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
addopts = -ra --strict-markers
```

- [ ] **Step 3: 空の `__init__.py` を2つ作成**

`backend/app/__init__.py`:
```python
"""AI Tutor backend package."""
```

`backend/tests/__init__.py`:
```python
```

- [ ] **Step 4: 依存解決を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
uv sync --extra dev
```

期待: `Installed N packages` が表示され、`backend/.venv` が生成される。`uv` 未導入なら `pip install uv` で先に入れる。

- [ ] **Step 5: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/pyproject.toml backend/pytest.ini backend/app/__init__.py backend/tests/__init__.py
git commit -m "feat(backend): add Python project skeleton with FastAPI deps"
```

---

## Task 3: カリキュラムデータ定数とDTO

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/data/__init__.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/data/curriculum.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/schemas/__init__.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/schemas/curriculum.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_curriculum_data.py`

- [ ] **Step 1: テスト先行 — `tests/test_curriculum_data.py`**

```python
from app.data.curriculum import CURRICULUM, get_phase


def test_curriculum_has_four_phases():
    assert sorted(CURRICULUM.keys()) == [1, 2, 3, 4]


def test_each_phase_has_required_fields():
    required = {"title", "goal", "duration", "skills", "tasks", "system_prompt"}
    for phase_no, phase in CURRICULUM.items():
        missing = required - set(phase.keys())
        assert not missing, f"Phase {phase_no} missing fields: {missing}"


def test_each_phase_has_at_least_three_tasks():
    for phase_no, phase in CURRICULUM.items():
        assert len(phase["tasks"]) >= 3, f"Phase {phase_no} has fewer than 3 tasks"


def test_system_prompt_mentions_phase_label():
    for phase_no, phase in CURRICULUM.items():
        assert f"Phase{phase_no}" in phase["system_prompt"]


def test_get_phase_returns_data_for_valid_id():
    phase = get_phase(1)
    assert phase["title"].startswith("開発環境")


def test_get_phase_raises_for_invalid_id():
    import pytest
    with pytest.raises(KeyError):
        get_phase(99)
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
uv run pytest tests/test_curriculum_data.py -v
```

期待: `ModuleNotFoundError: No module named 'app.data.curriculum'` で失敗。

- [ ] **Step 3: `app/data/__init__.py` を作成**

```python
```

- [ ] **Step 4: `app/data/curriculum.py` を作成**

```python
"""4フェーズのカリキュラム定義（Sprint 0 single source of truth）。"""

from typing import TypedDict


class PhaseData(TypedDict):
    title: str
    goal: str
    duration: str
    skills: list[str]
    tasks: list[str]
    system_prompt: str


CURRICULUM: dict[int, PhaseData] = {
    1: {
        "title": "開発環境の近代化",
        "goal": "AIツールを使いこなすための「土台」を固める",
        "duration": "2〜3週間",
        "skills": [
            "Git / GitHub",
            "VSCode拡張機能",
            "ターミナル操作",
            "REST API基礎",
        ],
        "tasks": [
            "Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成",
            "VSCode拡張（GitLens・REST Client・GitHub Copilot）の導入と動作確認",
            "curlでREST APIを叩き、JSONレスポンス構造をまとめる",
        ],
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
    },
    2: {
        "title": "AIツール活用マスター",
        "goal": "「AIと一緒にコードを書く」体験を積む",
        "duration": "3〜4週間",
        "skills": [
            "プロンプトエンジニアリング",
            "Cursor IDE",
            "GitHub Copilot",
            "Claude活用",
        ],
        "tasks": [
            "Cursor IDEで顧客管理API（CRUD）をゼロから作成。AIとのやり取りログを記録",
            "同機能をGitHub Copilotでも実装し、2つのAIの違いをまとめる",
            "ClaudeにコードレビューさせてPDCA",
        ],
        "system_prompt": (
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
    },
    3: {
        "title": "AI協調型開発ワークフロー",
        "goal": "実際の開発タスクにAIを組み込む",
        "duration": "AI補助コーディング期間",
        "skills": [
            "AIペアプログラミング",
            "AIによるコードレビュー",
            "テスト自動生成",
            "仕様書からのコード生成",
        ],
        "tasks": [
            "Phase2で作ったAPIをAIにレビューさせ、セキュリティ・パフォーマンス・可読性の観点で整理",
            "仕様書（箇条書き）からテストコードを自動生成し、不足ケースを3つ指摘",
            "AIとペアで新機能（検索機能など）を実装。会話ログも提出",
        ],
        "system_prompt": (
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
    },
    4: {
        "title": "AIアプリ開発実践",
        "goal": "「AIを使う」から「AIを組み込む」へ",
        "duration": "4〜6週間",
        "skills": [
            "API連携（Claude / OpenAI）",
            "RAG基礎",
            "PythonでAIツール作成",
            "プロダクト設計",
        ],
        "tasks": [
            "Claude APIでチャットボット作成（会話履歴保持・システムプロンプト設定）",
            "RAGデモ作成（Python + ChromaDB + Claude API）",
            "業務課題を解決するAIツールの企画書作成（課題・解決策・技術構成・効果試算）",
        ],
        "system_prompt": (
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
    },
}


def get_phase(phase_no: int) -> PhaseData:
    """Return phase data; raises KeyError if not found."""
    return CURRICULUM[phase_no]
```

- [ ] **Step 5: テストを実行してパスを確認**

```bash
uv run pytest tests/test_curriculum_data.py -v
```

期待: 6テストすべて PASS。

- [ ] **Step 6: スキーマDTOを作成 — `app/schemas/__init__.py`**

```python
```

- [ ] **Step 7: `app/schemas/curriculum.py` を作成**

```python
"""API応答用のpydanticスキーマ。"""

from pydantic import BaseModel


class PhaseSummary(BaseModel):
    phase: int
    title: str
    goal: str
    duration: str
    skills: list[str]
    tasks: list[str]
```

- [ ] **Step 8: コミット**

```bash
git add backend/app/data backend/app/schemas backend/tests/test_curriculum_data.py
git commit -m "feat(backend): add 4-phase curriculum data with tests"
```

---

## Task 4: 設定ローダーと健康チェック

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/config.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/api/__init__.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/api/health.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/main.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/conftest.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_health.py`

- [ ] **Step 1: テスト先行 — `tests/conftest.py`**

```python
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_MODEL", "claude-sonnet-4-5")


@pytest.fixture
def client() -> TestClient:
    from app.main import app
    return TestClient(app)
```

- [ ] **Step 2: テスト先行 — `tests/test_health.py`**

```python
def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_health.py -v
```

期待: `ModuleNotFoundError: No module named 'app.main'`。

- [ ] **Step 4: `app/config.py` を作成**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-5"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_allow_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


settings = Settings()  # type: ignore[call-arg]
```

- [ ] **Step 5: `app/api/__init__.py` を作成**

```python
```

- [ ] **Step 6: `app/api/health.py` を作成**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 7: `app/main.py` を作成**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="AI Tutor Curriculum API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    return app


app = create_app()
```

- [ ] **Step 8: テストを実行してパスを確認**

```bash
uv run pytest tests/test_health.py -v
```

期待: 1テスト PASS。

- [ ] **Step 9: コミット**

```bash
git add backend/app/config.py backend/app/main.py backend/app/api backend/tests/conftest.py backend/tests/test_health.py
git commit -m "feat(backend): wire FastAPI app with settings and healthz"
```

---

## Task 5: Claude APIクライアントラッパー

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/core/__init__.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/core/claude_client.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_claude_client.py`

- [ ] **Step 1: テスト先行 — `tests/test_claude_client.py`**

```python
from unittest.mock import MagicMock

import pytest

from app.core.claude_client import ClaudeClient


class _StubResponse:
    def __init__(self, text: str) -> None:
        self.content = [MagicMock(text=text)]


def test_complete_returns_assistant_text():
    fake_sdk = MagicMock()
    fake_sdk.messages.create.return_value = _StubResponse("こんにちは、研修生さん")

    client = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")
    reply = client.complete(
        system_prompt="あなたはAIチューターです",
        history=[{"role": "user", "content": "Gitとは？"}],
    )

    assert reply == "こんにちは、研修生さん"
    fake_sdk.messages.create.assert_called_once()
    kwargs = fake_sdk.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-4-5"
    assert kwargs["system"] == "あなたはAIチューターです"
    assert kwargs["messages"] == [{"role": "user", "content": "Gitとは？"}]


def test_complete_propagates_sdk_errors():
    fake_sdk = MagicMock()
    fake_sdk.messages.create.side_effect = RuntimeError("rate limited")

    client = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")

    with pytest.raises(RuntimeError, match="rate limited"):
        client.complete(system_prompt="", history=[])
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_claude_client.py -v
```

期待: `ModuleNotFoundError: No module named 'app.core'`。

- [ ] **Step 3: `app/core/__init__.py` を作成**

```python
```

- [ ] **Step 4: `app/core/claude_client.py` を作成**

```python
"""Anthropic Claude SDK の薄いラッパー。テスト時はSDKをモック注入する。"""

from typing import Protocol

from anthropic import Anthropic

from app.config import settings


class _SDKLike(Protocol):
    messages: object


class ClaudeClient:
    def __init__(self, sdk: _SDKLike, model: str) -> None:
        self._sdk = sdk
        self._model = model

    def complete(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        max_tokens: int = 1024,
    ) -> str:
        response = self._sdk.messages.create(  # type: ignore[attr-defined]
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=history,
        )
        return response.content[0].text


def get_claude_client() -> ClaudeClient:
    """FastAPI Dependsから利用するファクトリ。"""
    sdk = Anthropic(api_key=settings.anthropic_api_key)
    return ClaudeClient(sdk=sdk, model=settings.anthropic_model)
```

- [ ] **Step 5: テストを実行してパスを確認**

```bash
uv run pytest tests/test_claude_client.py -v
```

期待: 2テスト PASS。

- [ ] **Step 6: コミット**

```bash
git add backend/app/core backend/tests/test_claude_client.py
git commit -m "feat(backend): add Claude client wrapper with mock-friendly DI"
```

---

## Task 6: 会話履歴ストア（in-memory）

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/memory/__init__.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/memory/chat_store.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_chat_store.py`

- [ ] **Step 1: テスト先行 — `tests/test_chat_store.py`**

```python
from app.memory.chat_store import InMemoryChatStore


def test_new_store_returns_empty_history():
    store = InMemoryChatStore()
    assert store.get_history(user_id="u1", phase=1) == []


def test_append_then_get_returns_messages_in_order():
    store = InMemoryChatStore()
    store.append(user_id="u1", phase=1, role="user", content="Git とは？")
    store.append(user_id="u1", phase=1, role="assistant", content="バージョン管理…")

    history = store.get_history(user_id="u1", phase=1)
    assert history == [
        {"role": "user", "content": "Git とは？"},
        {"role": "assistant", "content": "バージョン管理…"},
    ]


def test_history_is_scoped_per_user_and_phase():
    store = InMemoryChatStore()
    store.append(user_id="u1", phase=1, role="user", content="A")
    store.append(user_id="u1", phase=2, role="user", content="B")
    store.append(user_id="u2", phase=1, role="user", content="C")

    assert store.get_history("u1", 1) == [{"role": "user", "content": "A"}]
    assert store.get_history("u1", 2) == [{"role": "user", "content": "B"}]
    assert store.get_history("u2", 1) == [{"role": "user", "content": "C"}]


def test_clear_removes_only_targeted_thread():
    store = InMemoryChatStore()
    store.append("u1", 1, "user", "A")
    store.append("u1", 2, "user", "B")

    store.clear("u1", 1)

    assert store.get_history("u1", 1) == []
    assert store.get_history("u1", 2) == [{"role": "user", "content": "B"}]
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_chat_store.py -v
```

期待: `ModuleNotFoundError`。

- [ ] **Step 3: `app/memory/__init__.py` を作成**

```python
```

- [ ] **Step 4: `app/memory/chat_store.py` を作成**

```python
"""Sprint 0 用のプロセス内会話履歴ストア。Sprint 1 でDB実装に差し替える。"""

from threading import Lock


class InMemoryChatStore:
    def __init__(self) -> None:
        self._data: dict[tuple[str, int], list[dict[str, str]]] = {}
        self._lock = Lock()

    def get_history(self, user_id: str, phase: int) -> list[dict[str, str]]:
        with self._lock:
            return list(self._data.get((user_id, phase), []))

    def append(self, user_id: str, phase: int, role: str, content: str) -> None:
        with self._lock:
            self._data.setdefault((user_id, phase), []).append(
                {"role": role, "content": content}
            )

    def clear(self, user_id: str, phase: int) -> None:
        with self._lock:
            self._data.pop((user_id, phase), None)


_store_singleton = InMemoryChatStore()


def get_chat_store() -> InMemoryChatStore:
    return _store_singleton
```

- [ ] **Step 5: テストを実行してパスを確認**

```bash
uv run pytest tests/test_chat_store.py -v
```

期待: 4テスト PASS。

- [ ] **Step 6: コミット**

```bash
git add backend/app/memory backend/tests/test_chat_store.py
git commit -m "feat(backend): add in-memory chat history store"
```

---

## Task 7: カリキュラム一覧API

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/api/curriculum.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/main.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_api_curriculum.py`

- [ ] **Step 1: テスト先行 — `tests/test_api_curriculum.py`**

```python
def test_list_phases_returns_four_phases(client):
    response = client.get("/api/curriculum/phases")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 4
    phase_numbers = [item["phase"] for item in data]
    assert phase_numbers == [1, 2, 3, 4]


def test_list_phases_includes_titles_and_tasks(client):
    response = client.get("/api/curriculum/phases")
    phase1 = response.json()[0]

    assert phase1["title"] == "開発環境の近代化"
    assert len(phase1["tasks"]) >= 3
    assert "Git" in " ".join(phase1["skills"])
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_api_curriculum.py -v
```

期待: 404（ルート未登録）で2件 FAIL。

- [ ] **Step 3: `app/api/curriculum.py` を作成**

```python
from fastapi import APIRouter

from app.data.curriculum import CURRICULUM
from app.schemas.curriculum import PhaseSummary

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


@router.get("/phases", response_model=list[PhaseSummary])
def list_phases() -> list[PhaseSummary]:
    return [
        PhaseSummary(
            phase=phase_no,
            title=phase["title"],
            goal=phase["goal"],
            duration=phase["duration"],
            skills=phase["skills"],
            tasks=phase["tasks"],
        )
        for phase_no, phase in sorted(CURRICULUM.items())
    ]
```

- [ ] **Step 4: `app/main.py` を修正してルーターを登録**

`app/main.py` の `create_app` 内、 `app.include_router(health.router)` の直後に追記:

```python
from app.api import curriculum  # 既存のimport群に追加

# create_app() 内
app.include_router(curriculum.router)
```

修正後の `create_app` 全体:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import curriculum, health
from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="AI Tutor Curriculum API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(curriculum.router)
    return app


app = create_app()
```

- [ ] **Step 5: テストを実行してパスを確認**

```bash
uv run pytest tests/test_api_curriculum.py -v
```

期待: 2テスト PASS。

- [ ] **Step 6: コミット**

```bash
git add backend/app/api/curriculum.py backend/app/main.py backend/tests/test_api_curriculum.py
git commit -m "feat(backend): expose GET /api/curriculum/phases"
```

---

## Task 8: チャットAPI

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/schemas/chat.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/api/chat.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/main.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_api_chat.py`

- [ ] **Step 1: スキーマ — `app/schemas/chat.py` を作成**

```python
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    phase: int = Field(ge=1, le=4)
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    reply: str
    history: list[ChatMessage]
```

- [ ] **Step 2: テスト先行 — `tests/test_api_chat.py`**

```python
from unittest.mock import MagicMock

from app.core.claude_client import ClaudeClient, get_claude_client
from app.memory.chat_store import InMemoryChatStore, get_chat_store


def _fake_client(*replies: str) -> tuple[ClaudeClient, MagicMock]:
    fake_sdk = MagicMock()
    fake_sdk.messages.create.side_effect = [
        MagicMock(content=[MagicMock(text=r)]) for r in replies
    ]
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5"), fake_sdk


def test_chat_returns_reply_and_persists_history(client):
    from app.main import app

    fake, _ = _fake_client("Gitはバージョン管理ツールです")
    store = InMemoryChatStore()
    app.dependency_overrides[get_claude_client] = lambda: fake
    app.dependency_overrides[get_chat_store] = lambda: store

    try:
        response = client.post(
            "/api/chat",
            json={"user_id": "u1", "phase": 1, "message": "Gitとは？"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["reply"] == "Gitはバージョン管理ツールです"
        assert data["history"] == [
            {"role": "user", "content": "Gitとは？"},
            {"role": "assistant", "content": "Gitはバージョン管理ツールです"},
        ]
    finally:
        app.dependency_overrides.clear()


def test_chat_carries_history_across_calls(client):
    from app.main import app

    fake, fake_sdk = _fake_client("一つ目", "二つ目")
    store = InMemoryChatStore()
    app.dependency_overrides[get_claude_client] = lambda: fake
    app.dependency_overrides[get_chat_store] = lambda: store

    try:
        client.post("/api/chat", json={"user_id": "u1", "phase": 1, "message": "Q1"})
        client.post("/api/chat", json={"user_id": "u1", "phase": 1, "message": "Q2"})

        second_call_messages = fake_sdk.messages.create.call_args_list[1].kwargs["messages"]
        roles = [m["role"] for m in second_call_messages]
        assert roles == ["user", "assistant", "user"]
    finally:
        app.dependency_overrides.clear()


def test_chat_rejects_invalid_phase(client):
    response = client.post(
        "/api/chat",
        json={"user_id": "u1", "phase": 99, "message": "hi"},
    )
    assert response.status_code == 422
```

- [ ] **Step 3: テストを実行して失敗を確認**

```bash
uv run pytest tests/test_api_chat.py -v
```

期待: `ModuleNotFoundError: No module named 'app.api.chat'`。

- [ ] **Step 4: `app/api/chat.py` を作成**

```python
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.claude_client import ClaudeClient, get_claude_client
from app.data.curriculum import CURRICULUM
from app.memory.chat_store import InMemoryChatStore, get_chat_store
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    claude: ClaudeClient = Depends(get_claude_client),
    store: InMemoryChatStore = Depends(get_chat_store),
) -> ChatResponse:
    if request.phase not in CURRICULUM:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"phase {request.phase} not found",
        )

    history = store.get_history(request.user_id, request.phase)
    next_history = history + [{"role": "user", "content": request.message}]

    reply = claude.complete(
        system_prompt=CURRICULUM[request.phase]["system_prompt"],
        history=next_history,
    )

    store.append(request.user_id, request.phase, "user", request.message)
    store.append(request.user_id, request.phase, "assistant", reply)

    full_history = store.get_history(request.user_id, request.phase)
    return ChatResponse(
        reply=reply,
        history=[ChatMessage(**m) for m in full_history],
    )
```

- [ ] **Step 5: `app/main.py` にchatルーターを登録**

`app.include_router(curriculum.router)` の直後に1行追加:

```python
from app.api import chat as chat_router  # importに追加（既存と並べる）

# create_app() 内
app.include_router(chat_router.router)
```

修正後の `create_app`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat as chat_router
from app.api import curriculum, health
from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="AI Tutor Curriculum API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(curriculum.router)
    app.include_router(chat_router.router)
    return app


app = create_app()
```

- [ ] **Step 6: テストを実行してパスを確認**

```bash
uv run pytest tests/test_api_chat.py -v
```

期待: 3テスト PASS。

- [ ] **Step 7: 全テスト一括実行**

```bash
uv run pytest -v
```

期待: 全テスト PASS（合計 約18件）。

- [ ] **Step 8: コミット**

```bash
git add backend/app/schemas/chat.py backend/app/api/chat.py backend/app/main.py backend/tests/test_api_chat.py
git commit -m "feat(backend): add POST /api/chat with phase-aware system prompt"
```

---

## Task 9: バックエンドDockerfile

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/Dockerfile`

- [ ] **Step 1: `backend/Dockerfile` を作成**

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install uv

COPY pyproject.toml /app/
RUN uv sync --no-dev

COPY app /app/app

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: イメージビルド確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
docker build -t ai-tutor-backend:dev .
```

期待: 正常完了。

- [ ] **Step 3: コミット**

```bash
git add backend/Dockerfile
git commit -m "feat(backend): add Dockerfile"
```

---

## Task 10: フロントエンドスケルトン

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/package.json`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/tsconfig.json`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/vite.config.ts`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/index.html`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/env.d.ts`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/main.ts`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/App.vue`

- [ ] **Step 1: `frontend/package.json` を作成**

```json
{
  "name": "ai-tutor-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview --host 0.0.0.0 --port 5173",
    "lint": "eslint src --ext .ts,.vue",
    "test": "vitest run"
  },
  "dependencies": {
    "pinia": "^2.2.0",
    "vue": "^3.5.0",
    "vue-router": "^4.4.0"
  },
  "devDependencies": {
    "@types/node": "^22.5.0",
    "@vitejs/plugin-vue": "^5.1.0",
    "typescript": "^5.6.0",
    "vite": "^5.4.0",
    "vitest": "^2.1.0",
    "vue-tsc": "^2.1.0"
  }
}
```

- [ ] **Step 2: `frontend/tsconfig.json` を作成**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "jsx": "preserve",
    "esModuleInterop": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "types": ["vite/client", "node"],
    "paths": {
      "@/*": ["./src/*"]
    },
    "baseUrl": "."
  },
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.vue"]
}
```

- [ ] **Step 3: `frontend/vite.config.ts` を作成**

```ts
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'node:path';

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
});
```

- [ ] **Step 4: `frontend/index.html` を作成**

```html
<!doctype html>
<html lang="ja">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI駆動型開発 補足カリキュラム AIチューター</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 5: `frontend/src/env.d.ts` を作成**

```ts
/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<object, object, unknown>;
  export default component;
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
}
```

- [ ] **Step 6: `frontend/src/App.vue` を作成**

```vue
<script setup lang="ts">
import { RouterView } from 'vue-router';
</script>

<template>
  <header class="app-header">
    <h1>AI駆動型開発 補足カリキュラム</h1>
    <p>AIチューター — 学習サポートシステム</p>
  </header>
  <main class="app-main">
    <RouterView />
  </main>
</template>

<style>
:root {
  --color-bg: #f6f7fb;
  --color-surface: #ffffff;
  --color-text: #1b1f24;
  --color-accent: #2f6df6;
  --radius: 14px;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Inter', system-ui, -apple-system, 'Hiragino Kaku Gothic ProN', sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
}

.app-header {
  padding: 1.5rem 2rem;
  background: var(--color-surface);
  border-bottom: 1px solid #e5e7eb;
}
.app-header h1 { margin: 0; font-size: 1.25rem; }
.app-header p { margin: 0.25rem 0 0; color: #6b7280; font-size: 0.875rem; }

.app-main { padding: 2rem; max-width: 960px; margin: 0 auto; }
</style>
```

- [ ] **Step 7: 依存インストールと型チェック**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend
npm install
npm run build  # vue-tsc が走り、型エラーがないことを確認
```

期待: `dist/` 配下が生成される。

- [ ] **Step 8: コミット**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html frontend/src/env.d.ts frontend/src/App.vue
git commit -m "feat(frontend): bootstrap Vue 3 + Vite scaffold"
```

---

## Task 11: 型定義・APIクライアント・ルーター・Pinia store

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/types/curriculum.ts`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/lib/api.ts`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/stores/curriculum.ts`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/router/index.ts`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/main.ts`

- [ ] **Step 1: `src/types/curriculum.ts` を作成**

```ts
export interface PhaseSummary {
  phase: number;
  title: string;
  goal: string;
  duration: string;
  skills: string[];
  tasks: string[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  reply: string;
  history: ChatMessage[];
}
```

- [ ] **Step 2: `src/lib/api.ts` を作成**

```ts
import type { ChatResponse, PhaseSummary } from '@/types/curriculum';

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listPhases: () => request<PhaseSummary[]>('/api/curriculum/phases'),

  sendChat: (payload: { user_id: string; phase: number; message: string }) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
```

- [ ] **Step 3: `src/stores/curriculum.ts` を作成**

```ts
import { defineStore } from 'pinia';
import { api } from '@/lib/api';
import type { ChatMessage, PhaseSummary } from '@/types/curriculum';

interface State {
  phases: PhaseSummary[];
  loading: boolean;
  error: string | null;
  chatLogs: Record<number, ChatMessage[]>;
  userId: string;
}

export const useCurriculumStore = defineStore('curriculum', {
  state: (): State => ({
    phases: [],
    loading: false,
    error: null,
    chatLogs: {},
    userId: 'demo-user',
  }),
  actions: {
    async fetchPhases() {
      this.loading = true;
      this.error = null;
      try {
        this.phases = await api.listPhases();
      } catch (e) {
        this.error = e instanceof Error ? e.message : 'unknown error';
      } finally {
        this.loading = false;
      }
    },

    async sendChat(phase: number, message: string) {
      const result = await api.sendChat({
        user_id: this.userId,
        phase,
        message,
      });
      this.chatLogs[phase] = result.history;
      return result.reply;
    },

    getPhase(phaseNo: number): PhaseSummary | undefined {
      return this.phases.find((p) => p.phase === phaseNo);
    },
  },
});
```

- [ ] **Step 4: `src/router/index.ts` を作成**

```ts
import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '@/views/HomeView.vue';
import PhaseChatView from '@/views/PhaseChatView.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    {
      path: '/phases/:phase',
      name: 'phase',
      component: PhaseChatView,
      props: (route) => ({ phase: Number(route.params.phase) }),
    },
  ],
});
```

- [ ] **Step 5: `src/main.ts` を作成**

```ts
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from '@/App.vue';
import { router } from '@/router';

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount('#app');
```

- [ ] **Step 6: 仮ファイルを作成して型チェックを通す**

`frontend/src/views/HomeView.vue` （仮）:
```vue
<template><p>home placeholder</p></template>
```

`frontend/src/views/PhaseChatView.vue` （仮）:
```vue
<script setup lang="ts">
defineProps<{ phase: number }>();
</script>
<template><p>phase {{ phase }} placeholder</p></template>
```

- [ ] **Step 7: 型ビルドを実行**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend
npm run build
```

期待: 型エラーなしでビルド成功。

- [ ] **Step 8: コミット**

```bash
git add frontend/src/types frontend/src/lib frontend/src/stores frontend/src/router frontend/src/main.ts frontend/src/views
git commit -m "feat(frontend): add api client, pinia store, and router skeleton"
```

---

## Task 12: フェーズ一覧画面とPhaseCard

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/components/PhaseCard.vue`
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/views/HomeView.vue`

- [ ] **Step 1: `src/components/PhaseCard.vue` を作成**

```vue
<script setup lang="ts">
import type { PhaseSummary } from '@/types/curriculum';

defineProps<{ phase: PhaseSummary }>();
</script>

<template>
  <article class="phase-card">
    <header>
      <span class="phase-no">Phase {{ phase.phase }}</span>
      <h2>{{ phase.title }}</h2>
      <p class="duration">{{ phase.duration }}</p>
    </header>

    <p class="goal">{{ phase.goal }}</p>

    <section>
      <h3>学習スキル</h3>
      <ul>
        <li v-for="s in phase.skills" :key="s">{{ s }}</li>
      </ul>
    </section>

    <section>
      <h3>課題</h3>
      <ol>
        <li v-for="t in phase.tasks" :key="t">{{ t }}</li>
      </ol>
    </section>

    <RouterLink :to="{ name: 'phase', params: { phase: phase.phase } }" class="cta">
      AIチューターと対話する →
    </RouterLink>
  </article>
</template>

<style scoped>
.phase-card {
  background: var(--color-surface);
  border-radius: var(--radius);
  padding: 1.5rem;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.phase-no {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-accent);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.phase-card h2 { margin: 0.25rem 0 0; font-size: 1.15rem; }
.duration { margin: 0; color: #6b7280; font-size: 0.85rem; }
.goal { margin: 0; font-size: 0.95rem; }
section h3 {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6b7280;
}
section ul, section ol { margin: 0; padding-left: 1.25rem; font-size: 0.9rem; }
.cta {
  margin-top: auto;
  align-self: flex-start;
  color: var(--color-accent);
  font-weight: 600;
  text-decoration: none;
}
.cta:hover { text-decoration: underline; }
</style>
```

- [ ] **Step 2: `src/views/HomeView.vue` を書き換える（仮実装を置き換え）**

```vue
<script setup lang="ts">
import { onMounted } from 'vue';
import { useCurriculumStore } from '@/stores/curriculum';
import PhaseCard from '@/components/PhaseCard.vue';

const store = useCurriculumStore();

onMounted(() => {
  if (store.phases.length === 0) {
    void store.fetchPhases();
  }
});
</script>

<template>
  <section v-if="store.loading">読み込み中…</section>
  <section v-else-if="store.error" class="error">
    エラー: {{ store.error }}
  </section>
  <section v-else class="phase-grid">
    <PhaseCard v-for="p in store.phases" :key="p.phase" :phase="p" />
  </section>
</template>

<style scoped>
.phase-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.25rem;
}
.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 1rem;
  border-radius: 12px;
}
</style>
```

- [ ] **Step 3: ビルド確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend
npm run build
```

期待: ビルド成功。

- [ ] **Step 4: コミット**

```bash
git add frontend/src/components/PhaseCard.vue frontend/src/views/HomeView.vue
git commit -m "feat(frontend): list four phases with PhaseCard grid"
```

---

## Task 13: チャット画面とコンポーネント

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/components/ChatMessage.vue`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/components/ChatLog.vue`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/components/ChatInput.vue`
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/views/PhaseChatView.vue`

- [ ] **Step 1: `src/components/ChatMessage.vue` を作成**

```vue
<script setup lang="ts">
import type { ChatMessage } from '@/types/curriculum';

defineProps<{ message: ChatMessage }>();
</script>

<template>
  <div :class="['chat-message', message.role]">
    <span class="role">{{ message.role === 'user' ? 'あなた' : 'AIチューター' }}</span>
    <p>{{ message.content }}</p>
  </div>
</template>

<style scoped>
.chat-message {
  padding: 0.85rem 1rem;
  border-radius: 12px;
  max-width: 78%;
  white-space: pre-wrap;
}
.chat-message.user {
  background: var(--color-accent);
  color: white;
  align-self: flex-end;
}
.chat-message.assistant {
  background: #eef2ff;
  color: #1e1b4b;
  align-self: flex-start;
}
.role {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.7;
  display: block;
  margin-bottom: 0.25rem;
}
.chat-message p { margin: 0; }
</style>
```

- [ ] **Step 2: `src/components/ChatLog.vue` を作成**

```vue
<script setup lang="ts">
import type { ChatMessage } from '@/types/curriculum';
import ChatMessageComponent from '@/components/ChatMessage.vue';

defineProps<{ messages: ChatMessage[] }>();
</script>

<template>
  <div class="chat-log">
    <p v-if="messages.length === 0" class="empty">
      まだ会話がありません。下の入力欄から質問してみましょう。
    </p>
    <ChatMessageComponent
      v-for="(m, i) in messages"
      :key="i"
      :message="m"
    />
  </div>
</template>

<style scoped>
.chat-log {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  background: var(--color-surface);
  padding: 1.25rem;
  border-radius: var(--radius);
  min-height: 340px;
}
.empty {
  color: #6b7280;
  font-size: 0.9rem;
  text-align: center;
  padding: 1.5rem 0;
}
</style>
```

- [ ] **Step 3: `src/components/ChatInput.vue` を作成**

```vue
<script setup lang="ts">
import { ref } from 'vue';

const props = defineProps<{ disabled?: boolean }>();
const emit = defineEmits<{ submit: [text: string] }>();

const text = ref('');

const send = () => {
  const value = text.value.trim();
  if (!value || props.disabled) return;
  emit('submit', value);
  text.value = '';
};

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    send();
  }
};
</script>

<template>
  <form class="chat-input" @submit.prevent="send">
    <textarea
      v-model="text"
      :disabled="disabled"
      rows="3"
      placeholder="質問を入力（Cmd/Ctrl+Enter で送信）"
      @keydown="onKeydown"
    />
    <button type="submit" :disabled="disabled || !text.trim()">
      送信
    </button>
  </form>
</template>

<style scoped>
.chat-input {
  display: flex;
  gap: 0.65rem;
  margin-top: 0.85rem;
}
textarea {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  font: inherit;
  resize: vertical;
}
textarea:focus {
  outline: 2px solid var(--color-accent);
  outline-offset: 1px;
}
button {
  background: var(--color-accent);
  color: white;
  border: 0;
  padding: 0 1.25rem;
  border-radius: 10px;
  font-weight: 600;
  cursor: pointer;
}
button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
```

- [ ] **Step 4: `src/views/PhaseChatView.vue` を書き換える**

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useCurriculumStore } from '@/stores/curriculum';
import ChatLog from '@/components/ChatLog.vue';
import ChatInput from '@/components/ChatInput.vue';

const props = defineProps<{ phase: number }>();
const store = useCurriculumStore();
const sending = ref(false);
const sendError = ref<string | null>(null);

const phaseData = computed(() => store.getPhase(props.phase));
const messages = computed(() => store.chatLogs[props.phase] ?? []);
const quickQuestions = computed(() => phaseData.value?.tasks.slice(0, 3) ?? []);

onMounted(async () => {
  if (store.phases.length === 0) {
    await store.fetchPhases();
  }
});

const submit = async (text: string) => {
  sending.value = true;
  sendError.value = null;
  try {
    await store.sendChat(props.phase, text);
  } catch (e) {
    sendError.value = e instanceof Error ? e.message : 'unknown error';
  } finally {
    sending.value = false;
  }
};
</script>

<template>
  <section v-if="!phaseData" class="loading">フェーズ情報を読み込み中…</section>
  <section v-else class="phase-chat">
    <header>
      <RouterLink to="/">← 一覧に戻る</RouterLink>
      <h2>Phase {{ phaseData.phase }} — {{ phaseData.title }}</h2>
      <p>{{ phaseData.goal }}</p>
    </header>

    <aside class="quick" v-if="quickQuestions.length > 0">
      <h3>クイック質問</h3>
      <button
        v-for="q in quickQuestions"
        :key="q"
        type="button"
        :disabled="sending"
        @click="submit(`課題について教えてください: ${q}`)"
      >
        {{ q }}
      </button>
    </aside>

    <ChatLog :messages="messages" />
    <p v-if="sendError" class="error">エラー: {{ sendError }}</p>
    <ChatInput :disabled="sending" @submit="submit" />
  </section>
</template>

<style scoped>
.phase-chat {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.phase-chat header h2 { margin: 0.5rem 0 0.25rem; font-size: 1.2rem; }
.phase-chat header a { color: var(--color-accent); text-decoration: none; font-size: 0.9rem; }
.quick {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.quick h3 {
  margin: 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6b7280;
}
.quick button {
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.6rem 0.9rem;
  text-align: left;
  cursor: pointer;
  font: inherit;
}
.quick button:hover { border-color: var(--color-accent); }
.quick button:disabled { opacity: 0.5; cursor: not-allowed; }
.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 0.6rem 0.9rem;
  border-radius: 10px;
  margin: 0;
}
.loading { color: #6b7280; }
</style>
```

- [ ] **Step 5: 型ビルドを通す**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend
npm run build
```

期待: ビルド成功。

- [ ] **Step 6: コミット**

```bash
git add frontend/src/components/ChatMessage.vue frontend/src/components/ChatLog.vue frontend/src/components/ChatInput.vue frontend/src/views/PhaseChatView.vue
git commit -m "feat(frontend): add chat view with log, input, and quick questions"
```

---

## Task 14: フロントエンドDockerfile

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/Dockerfile`

- [ ] **Step 1: `frontend/Dockerfile` を作成（開発用）**

```dockerfile
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

- [ ] **Step 2: コミット**

```bash
git add frontend/Dockerfile
git commit -m "feat(frontend): add dev Dockerfile"
```

---

## Task 15: Docker Compose統合と動作確認

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/docker-compose.yml`

- [ ] **Step 1: `docker-compose.yml` を作成**

```yaml
services:
  backend:
    build: ./backend
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/app/app
    command: ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

  frontend:
    build: ./frontend
    environment:
      - VITE_API_BASE_URL=http://localhost:8000
    ports:
      - "5173:5173"
    volumes:
      - ./frontend/src:/app/src
      - ./frontend/index.html:/app/index.html
    depends_on:
      - backend
```

- [ ] **Step 2: 起動確認**

```bash
cd /Volumes/Seagate3TB/projects/edu
cp .env.example .env
# .env を編集して ANTHROPIC_API_KEY に実キーを入れる
docker compose up --build
```

期待:
- backend が `Uvicorn running on http://0.0.0.0:8000` を表示
- frontend が `Local: http://localhost:5173/` を表示
- ブラウザで http://localhost:5173 を開くと4フェーズが表示
- フェーズカードのリンクをクリック→チャット画面が表示
- 質問送信で実際にClaudeから日本語応答が返る

- [ ] **Step 3: 手動E2E確認チェックリスト**

以下を実機で確認し、本ステップにチェック：
- [ ] http://localhost:5173 でフェーズ4件表示
- [ ] http://localhost:8000/docs でSwagger UI閲覧可
- [ ] http://localhost:8000/api/curriculum/phases が4件返す
- [ ] Phase 1 のチャット画面で「Gitとは何ですか？」を送信→AI応答取得
- [ ] 同セッション内で2回目の質問をすると、AIが文脈を踏まえた応答をする
- [ ] Phase 2に移動後、フェーズ別のシステムプロンプトが効いた応答になる

- [ ] **Step 4: コミット**

```bash
git add docker-compose.yml
git commit -m "feat: wire backend and frontend with docker-compose"
```

---

## Task 16: 完了確認と最終クリーンアップ

- [ ] **Step 1: 全テスト実行**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
uv run pytest -v
```

期待: 全テスト PASS（合計 18件前後）。

- [ ] **Step 2: lintチェック**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
uv run ruff check app tests
```

期待: エラー 0。

- [ ] **Step 3: フロントエンドビルド**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend
npm run build
```

期待: 型エラーなしでビルド成功。

- [ ] **Step 4: README に Sprint 0 完了の節を追加**

`README.md` の末尾に追加:

```markdown
## 実装進捗

- [x] Sprint 0: スケルトン + カリキュラム配信 + AIチューター対話MVP
- [ ] Sprint 1: PostgreSQL + 認証 + 進捗管理 + 会話履歴永続化
- [ ] Sprint 2: 課題提出 + AI採点
- [ ] Sprint 3: 管理者ダッシュボード

詳細は `docs/superpowers/plans/` を参照。
```

- [ ] **Step 5: 最終コミット**

```bash
git add README.md
git commit -m "docs: mark Sprint 0 as complete in README"
```

---

## ロードマップ（Sprint 1以降の見通し）

Sprint 0 完了後に着手する内容を、各Sprintごとに別プランとして起こす：

### Sprint 1: 認証・DB永続化・進捗管理
- PostgreSQL + pgvector + Alembic を Docker Compose に追加
- `users` / `progress` / `chat_history` テーブル作成
- JWT認証（`POST /api/auth/login`, `GET /api/users/me`）
- `InMemoryChatStore` を `PostgresChatStore` に差し替え
- `/api/progress` `/api/progress/{phase}` の実装
- フェーズ解放ロックロジック
- フロントエンドのログイン画面・進捗バッジ

### Sprint 2: 課題提出とAI採点
- `submissions` テーブル
- `POST /api/submissions/{phase}` / `GET /api/submissions/{phase}`
- ファイルアップロード対応（S3 or ローカル）
- Claude による採点（システムプロンプト＋ルーブリック）
- フロントエンドの提出フォーム・採点結果表示

### Sprint 3: 管理者ダッシュボード
- 管理者ロール（RBAC）
- `GET /api/admin/dashboard` 全受講者進捗一覧
- 受講者個別ビュー、提出物レビュー
- フロントエンドの管理者画面

各Sprintは「working, testable software」として独立して成立するように分割する。
