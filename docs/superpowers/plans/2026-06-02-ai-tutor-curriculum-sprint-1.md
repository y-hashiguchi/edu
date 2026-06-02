# AIチューターカリキュラム Sprint 1 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sprint 0 のメモリ実装の上に、PostgreSQL + JWT 認証 + 進捗管理 + 会話履歴永続化を導入し、複数受講者が個別の進捗と会話履歴を持てる状態に到達する。

**Architecture:** バックエンドを async SQLAlchemy 2.x + asyncpg に移行し、Alembic（async）でマイグレーション管理。FastAPI ルートは `Depends(get_current_user)` で保護。Claude SDK を `AsyncAnthropic` に切り替え、chat レイヤを async 化。`InMemoryChatStore` は削除し、同等インタフェースの `SqlChatStore` に置き換える。フロントエンドは Pinia auth ストア + ルーターガード + localStorage トークンでログインフローを最小実装し、ロック済みフェーズは表示のみ・チャット遷移不可とする。

**Tech Stack:**
- Backend 追加: SQLAlchemy 2.x (async) / asyncpg / Alembic / passlib[bcrypt] / python-jose[cryptography] / email-validator / pytest-asyncio（既存）
- AI SDK: `anthropic.AsyncAnthropic`（既存の sync `Anthropic` から差し替え）
- DB: PostgreSQL 16 + pgvector 拡張（pgvector は宣言のみ、利用は Sprint 2 以降）
- Frontend 追加: `pinia-plugin-persistedstate`（auth state 永続化）

---

## スコープ境界

**含む（Sprint 1）：**
- `pgvector/pgvector:pg16` を `docker-compose.yml` に追加
- SQLAlchemy 2.x async + asyncpg + Alembic で `users` / `progress` / `chat_history` を作成
- `POST /api/auth/register` / `POST /api/auth/login` / `GET /api/auth/me`
- JWT (HS256, 60min) によるベアラ認証 + `get_current_user` 依存
- ユーザ作成時に `progress` 全フェーズを seed（Phase 1: `in_progress`、Phase 2-4: `locked`）
- `GET /api/progress` / `POST /api/progress/{phase}/complete`（フェーズ完了 → 次フェーズ自動解放）
- `GET /api/curriculum/phases` の応答に `locked: bool` を含める
- `POST /api/chat` を認証必須化（`ChatRequest.user_id` 削除、`current_user.id` 採用）+ ロックフェーズへの送信を 403 で拒否
- `GET /api/chat/history/{phase}` 追加
- 会話履歴を `chat_history` テーブルに永続化（`SqlChatStore`）
- フロントエンド：`/login`、ルーターガード、ロック表示、フェーズ完了ボタン、履歴自動ロード

**含まない（後続スプリント）：**
- 課題提出（テキスト/ファイル）と AI 採点 → Sprint 2
- 管理者ダッシュボード（全受講者の進捗一覧）→ Sprint 3
- リフレッシュトークン / HttpOnly Cookie / CSRF / レート制限 → 後続
- pgvector の実利用（RAG など）→ Sprint 2 以降
- CI（GitHub Actions） → 後続

---

## アーキテクチャ判断（明示）

| 判断 | 選択 | 理由 |
|---|---|---|
| ORM | SQLAlchemy 2.x async + asyncpg | FastAPI と相性が良く、Sprint 2 の pgvector 利用に直結 |
| マイグレーション | Alembic async (`run_migrations_online` を `asyncio.run`) | 公式ガイド準拠、`alembic revision --autogenerate` でモデル差分検出 |
| パスワードハッシュ | `passlib[bcrypt]`、`BCRYPT_ROUNDS=12`（テスト時 `4`） | デファクト、テスト速度を環境変数で調整可能 |
| JWT | `python-jose[cryptography]`、HS256、`exp=60min` | リフレッシュは Sprint 1 不要、社内デモ前提 |
| Postgres image | `pgvector/pgvector:pg16` | Sprint 2 で `CREATE EXTENSION vector` を素直に使える |
| Claude SDK | `AsyncAnthropic` に全面移行 | チャットルート async 化に合わせる |
| テスト DB 戦略 | 別 DB `ai_tutor_test` + `Base.metadata.create_all` + テスト毎 `TRUNCATE ... RESTART IDENTITY CASCADE` | Alembic を走らせず高速、Postgres セマンティクスは保つ |
| `ChatRequest.user_id` | **削除**（`current_user.id` を採用） | 認証必須化に伴う既存テストの書き換えは避けられないので、ここで決着 |
| Chat レイヤ async 化 | 同一スプリントで `InMemoryChatStore` を削除し `SqlChatStore` に置換 | 二段階の差し替えはコスト高、一度で切る |
| Auth state 永続化 | `pinia-plugin-persistedstate` で localStorage | XSS リスクは社内デモ前提で受容、Sprint 2+ で HttpOnly Cookie 検討 |

---

## ファイル構造（新規 + 変更）

```
edu/
├── docker-compose.yml                                 # Modify: postgres 追加
├── .env.example                                        # Modify: DATABASE_URL / JWT_SECRET_KEY 追加
├── Makefile                                            # Modify: migrate / db-shell ターゲット
├── README.md                                           # Modify: Sprint 1 完了マーク
├── backend/
│   ├── pyproject.toml                                  # Modify: 依存追加
│   ├── alembic.ini                                     # Create
│   ├── alembic/
│   │   ├── env.py                                      # Create
│   │   ├── script.py.mako                              # Create
│   │   └── versions/
│   │       └── 0001_initial.py                         # Create
│   ├── tests/conftest.py                               # Modify: async client / db_session / auth fixtures
│   ├── tests/test_api_chat.py                          # Modify: auth_client + AsyncMock
│   ├── tests/test_chat_store.py                        # Modify: SqlChatStore 用に書換
│   ├── tests/test_claude_client.py                     # Modify: AsyncMock + async test
│   ├── tests/test_security.py                          # Create
│   ├── tests/test_api_auth.py                          # Create
│   ├── tests/test_progress_service.py                  # Create
│   ├── tests/test_api_progress.py                      # Create
│   ├── tests/test_api_chat_history.py                  # Create
│   └── app/
│       ├── config.py                                   # Modify: DB / JWT / bcrypt 設定
│       ├── main.py                                     # Modify: auth/progress ルーター登録
│       ├── core/
│       │   ├── claude_client.py                        # Modify: AsyncAnthropic に移行
│       │   ├── security.py                             # Create
│       │   └── deps.py                                 # Create
│       ├── db/
│       │   ├── __init__.py                             # Create
│       │   ├── base.py                                 # Create
│       │   └── session.py                              # Create
│       ├── models/
│       │   ├── __init__.py                             # Create
│       │   ├── user.py                                 # Create
│       │   ├── progress.py                             # Create
│       │   └── chat_history.py                         # Create
│       ├── memory/
│       │   └── chat_store.py                           # Modify: SqlChatStore に置換
│       ├── services/
│       │   ├── __init__.py                             # Create
│       │   └── progress.py                             # Create
│       ├── schemas/
│       │   ├── auth.py                                 # Create
│       │   ├── progress.py                             # Create
│       │   ├── chat.py                                 # Modify: user_id 削除
│       │   └── curriculum.py                           # Modify: locked フィールド追加
│       └── api/
│           ├── auth.py                                 # Create
│           ├── progress.py                             # Create
│           ├── chat.py                                 # Modify: 認証統合 + async + history GET
│           └── curriculum.py                           # Modify: 認証時のみ locked を返す
└── frontend/
    ├── package.json                                    # Modify: pinia-plugin-persistedstate 追加
    ├── src/
    │   ├── main.ts                                     # Modify: persistedstate プラグイン登録
    │   ├── lib/api.ts                                  # Modify: トークン注入 + 401 ハンドリング
    │   ├── stores/
    │   │   ├── auth.ts                                 # Create
    │   │   └── curriculum.ts                           # Modify: progress / chat 永続化対応
    │   ├── router/index.ts                             # Modify: beforeEach ガード
    │   ├── types/curriculum.ts                         # Modify: locked / Progress 型追加
    │   ├── components/
    │   │   └── PhaseCard.vue                           # Modify: lock 表示
    │   └── views/
    │       ├── LoginView.vue                           # Create
    │       ├── HomeView.vue                            # Modify: progress フェッチ
    │       └── PhaseChatView.vue                       # Modify: 履歴ロード + 完了ボタン
```

---

## Task 1: Docker Compose に Postgres を追加

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/docker-compose.yml`
- Modify: `/Volumes/Seagate3TB/projects/edu/.env.example`

- [ ] **Step 1: `docker-compose.yml` を書き換える**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-ai_tutor}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/db-init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-ai_tutor}"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    build: ./backend
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/app/app
      - ./backend/alembic:/app/alembic
      - ./backend/alembic.ini:/app/alembic.ini
    command: ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]

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

volumes:
  postgres_data:
```

- [ ] **Step 2: `backend/db-init/01-create-test-db.sql` を作成**

`pgvector` 拡張を有効化し、テスト用 DB も同時に作成する。

```sql
CREATE EXTENSION IF NOT EXISTS vector;

SELECT 'CREATE DATABASE ai_tutor_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ai_tutor_test')\gexec

\c ai_tutor_test
CREATE EXTENSION IF NOT EXISTS vector;
```

- [ ] **Step 3: `.env.example` を書き換える**

```dotenv
# Anthropic Claude API
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-sonnet-4-5

# Backend
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ALLOW_ORIGINS=http://localhost:5173

# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ai_tutor
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/ai_tutor
# ローカルテスト時はホスト名を localhost に置き換える:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor

# JWT
JWT_SECRET_KEY=change-me-in-production-please-use-openssl-rand-hex-32
JWT_ALGORITHM=HS256
JWT_EXPIRES_MIN=60
BCRYPT_ROUNDS=12

# Frontend
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 4: ローカル `.env` を更新（手動）**

```bash
cd /Volumes/Seagate3TB/projects/edu
# .env が無ければ
cp .env.example .env
# 既存の .env がある場合は、上記の Database/JWT セクションを追記
# JWT_SECRET_KEY は本物の値を入れる:
#   openssl rand -hex 32
```

- [ ] **Step 5: Postgres が単独で起動するか確認**

```bash
cd /Volumes/Seagate3TB/projects/edu
docker compose up -d postgres
docker compose exec postgres psql -U postgres -d ai_tutor -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```

期待: `vector` が1行返る。`ai_tutor_test` も存在することを確認:
```bash
docker compose exec postgres psql -U postgres -l | grep ai_tutor
```

期待: `ai_tutor` と `ai_tutor_test` の両方が表示される。

- [ ] **Step 6: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add docker-compose.yml .env.example backend/db-init/01-create-test-db.sql
git commit -m "feat(infra): add postgres with pgvector to docker-compose"
```

---

## Task 2: バックエンド依存追加 + Settings 拡張

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/pyproject.toml`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/config.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_security.py`（次タスクで使う設定値を先に検証）

- [ ] **Step 1: `backend/pyproject.toml` の `dependencies` を書き換える**

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
    "sqlalchemy[asyncio]>=2.0.35",
    "asyncpg>=0.30.0",
    "alembic>=1.13.0",
    "passlib[bcrypt]>=1.7.4",
    "python-jose[cryptography]>=3.3.0",
    "email-validator>=2.2.0",
    "python-multipart>=0.0.12",
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
ignore = ["B008"]  # FastAPI Depends() in argument defaults is idiomatic
```

- [ ] **Step 2: `backend/app/config.py` を書き換える**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-5"

    # HTTP
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_allow_origins: str = "http://localhost:5173"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor"

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expires_min: int = 60

    # Password hashing
    bcrypt_rounds: int = 12

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


settings = Settings()  # type: ignore[call-arg]
```

- [ ] **Step 3: 依存を解決**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
uv sync --extra dev
```

期待: 新規パッケージ（sqlalchemy / asyncpg / alembic / passlib / python-jose / email-validator）が `Installed`。

- [ ] **Step 4: Settings が新フィールドを読めることを確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
ANTHROPIC_API_KEY=test JWT_SECRET_KEY=secret uv run python -c "from app.config import settings; print(settings.database_url, settings.jwt_algorithm, settings.bcrypt_rounds)"
```

期待: `postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor HS256 12`。

- [ ] **Step 5: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/pyproject.toml backend/uv.lock backend/app/config.py
git commit -m "feat(backend): add async DB + auth dependencies and settings"
```

---

## Task 3: DB セッション基盤 + Alembic 設定

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/db/__init__.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/db/base.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/db/session.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/models/__init__.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/alembic.ini`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/alembic/env.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/alembic/script.py.mako`

- [ ] **Step 1: `backend/app/db/__init__.py` を作成**

```python
```

- [ ] **Step 2: `backend/app/db/base.py` を作成**

```python
"""SQLAlchemy declarative base. All models inherit from `Base`."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 3: `backend/app/db/session.py` を作成**

```python
"""Async engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, future=True, echo=False)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async DB session."""
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 4: `backend/app/models/__init__.py` を作成**

Alembic と `Base.metadata.create_all` が全モデルを認識するための集約 import。Sprint 1 終了時点では `user` / `progress` / `chat_history` の3つだが、現時点では空ファイル。Task 4 以降で随時追記する。

```python
"""Model registry. Import all models here so SQLAlchemy metadata sees them."""
```

- [ ] **Step 5: `backend/alembic.ini` を作成**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
file_template = %%(year)d%%(month).2d%%(day).2d_%%(rev)s_%%(slug)s
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 6: `backend/alembic/script.py.mako` を作成**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 7: `backend/alembic/env.py` を作成**

```python
"""Alembic env (async)."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.db.base import Base
from app import models  # noqa: F401  ensures all models register on Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 8: `backend/alembic/versions/` ディレクトリを作成**

```bash
mkdir -p /Volumes/Seagate3TB/projects/edu/backend/alembic/versions
touch /Volumes/Seagate3TB/projects/edu/backend/alembic/versions/.gitkeep
```

- [ ] **Step 9: Alembic がモデル無しでも `current` を実行できることを確認**

Postgres が稼働している前提（Task 1 のステップ5を済ませてあること）。

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
ANTHROPIC_API_KEY=test JWT_SECRET_KEY=test \
uv run alembic current
```

期待: 何も出力されない（リビジョン未適用）か、もしくはエラー無し。Tracebackなら env.py を見直す。

- [ ] **Step 10: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/db backend/app/models backend/alembic.ini backend/alembic
git commit -m "feat(backend): add async SQLAlchemy session and Alembic config"
```

---

## Task 4: SQLAlchemy モデル + security.py + 初回マイグレーション

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/models/user.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/models/progress.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/models/chat_history.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/models/__init__.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/core/security.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_security.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/alembic/versions/<auto>_initial.py`

設計根拠: `docs/design/02-detailed-design.md` §2.3–2.8、`docs/design/03-db-design.md` §3。

- [ ] **Step 1: `tests/test_security.py` を作成（テスト先行）**

```python
import pytest
from jose import JWTError

from app.core import security


def test_hash_then_verify_returns_true():
    hashed = security.hash_password("hunter2-strong")
    assert security.verify_password("hunter2-strong", hashed)


def test_verify_returns_false_for_wrong_password():
    hashed = security.hash_password("hunter2-strong")
    assert not security.verify_password("wrong-password", hashed)


def test_hash_outputs_differ_for_same_input():
    a = security.hash_password("same")
    b = security.hash_password("same")
    assert a != b  # bcrypt の salt で差分


def test_create_then_decode_returns_subject():
    token = security.create_access_token(subject="user-123")
    assert security.decode_access_token(token) == "user-123"


def test_decode_raises_on_invalid_signature():
    token = security.create_access_token(subject="user-123")
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(JWTError):
        security.decode_access_token(tampered)


def test_decode_raises_on_expired_token():
    token = security.create_access_token(subject="user-123", expires_min=-1)
    with pytest.raises(JWTError):
        security.decode_access_token(token)


def test_decode_raises_on_missing_sub():
    from datetime import UTC, datetime, timedelta

    from jose import jwt

    from app.config import settings

    payload = {"exp": datetime.now(UTC) + timedelta(minutes=5)}
    bad_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(JWTError):
        security.decode_access_token(bad_token)
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
JWT_SECRET_KEY=test-secret BCRYPT_ROUNDS=4 uv run pytest tests/test_security.py -v
```

期待: `ModuleNotFoundError: No module named 'app.core.security'` または `ImportError`。

- [ ] **Step 3: `app/core/security.py` を作成**

```python
"""Password hashing (bcrypt) and JWT helpers."""

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_rounds,
)


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(*, subject: str, expires_min: int | None = None) -> str:
    delta = timedelta(minutes=expires_min if expires_min is not None else settings.jwt_expires_min)
    payload = {"sub": subject, "exp": datetime.now(UTC) + delta}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Return the subject (user id) or raise JWTError."""
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise JWTError("missing sub")
    return sub
```

- [ ] **Step 4: security テストが PASS することを確認**

```bash
JWT_SECRET_KEY=test-secret BCRYPT_ROUNDS=4 uv run pytest tests/test_security.py -v
```

期待: 7 テストすべて PASS。

- [ ] **Step 5: `app/models/user.py` を作成**

```python
"""User ORM model."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
```

- [ ] **Step 6: `app/models/progress.py` を作成**

```python
"""Progress ORM model + status enum."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProgressStatus(str, Enum):
    LOCKED = "locked"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    COMPLETED = "completed"


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (
        UniqueConstraint("user_id", "phase", name="uq_progress_user_phase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    phase: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default=ProgressStatus.LOCKED.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 7: `app/models/chat_history.py` を作成**

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
        Index("ix_chat_history_user_phase_created", "user_id", "phase", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    phase: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
```

- [ ] **Step 8: `app/models/__init__.py` を書き換える**

```python
"""Model registry. Import all models here so SQLAlchemy metadata sees them."""

from app.models.chat_history import ChatHistory  # noqa: F401
from app.models.progress import Progress, ProgressStatus  # noqa: F401
from app.models.user import User  # noqa: F401
```

- [ ] **Step 9: Alembic マイグレーションを生成**

Postgres が稼働している前提（`docker compose up -d postgres`）。

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
ANTHROPIC_API_KEY=test JWT_SECRET_KEY=test \
uv run alembic revision --autogenerate -m "initial"
```

期待: `backend/alembic/versions/<YYYYMMDD>_<rev>_initial.py` が生成される。

- [ ] **Step 10: 生成されたマイグレーションを確認・整形**

生成ファイル先頭の `upgrade()` の最初の行に pgvector 拡張作成を追加する（既に Postgres 側で作成済だがマイグレーションでも宣言する）。

```python
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")  # この1行を追加

    # ↓ Alembic 自動生成
    op.create_table(
        "users",
        ...
    )
```

`downgrade()` で `DROP EXTENSION` はしない（他のテーブルが pgvector を使う可能性があるため）。

- [ ] **Step 11: マイグレーション適用**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
ANTHROPIC_API_KEY=test JWT_SECRET_KEY=test \
uv run alembic upgrade head
```

期待: `INFO  [alembic.runtime.migration] Running upgrade  -> <rev>, initial`。

- [ ] **Step 12: テーブル作成を確認**

```bash
docker compose exec postgres psql -U postgres -d ai_tutor -c "\dt"
```

期待: `users`、`progress`、`chat_history`、`alembic_version` の 4 テーブル。

- [ ] **Step 13: テスト DB にも適用**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor_test \
ANTHROPIC_API_KEY=test JWT_SECRET_KEY=test \
uv run alembic upgrade head
```

- [ ] **Step 14: 既存テストが壊れていないことを確認**

```bash
JWT_SECRET_KEY=test-secret BCRYPT_ROUNDS=4 uv run pytest -v
```

期待: Sprint 0 のテスト + 新規 security 7 件 すべて PASS。

- [ ] **Step 15: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/models backend/app/core/security.py backend/tests/test_security.py backend/alembic/versions
git commit -m "feat(backend): add ORM models, security helpers, and initial migration"
```

---

## Task 5: チャット層の async 移行

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/core/claude_client.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/memory/chat_store.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/api/chat.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_claude_client.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_chat_store.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_api_chat.py`

設計根拠: `docs/design/02-detailed-design.md` §2.5、§2.10。

このタスクの目的は DB 接続を入れる前に SDK・ストア・ルートを async に揃えること。`InMemoryChatStore` は本タスクではまだ削除しない（Task 8 で `SqlChatStore` に置き換え）。

- [ ] **Step 1: `tests/test_claude_client.py` を書き換える（テスト先行）**

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.claude_client import ClaudeClient


@pytest.mark.asyncio
async def test_complete_returns_assistant_text():
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text="こんにちは、研修生さん")])
    )

    client = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")
    reply = await client.complete(
        system_prompt="あなたはAIチューターです",
        history=[{"role": "user", "content": "Gitとは？"}],
    )

    assert reply == "こんにちは、研修生さん"
    fake_sdk.messages.create.assert_awaited_once()
    kwargs = fake_sdk.messages.create.await_args.kwargs
    assert kwargs["model"] == "claude-sonnet-4-5"
    assert kwargs["system"] == "あなたはAIチューターです"
    assert kwargs["messages"] == [{"role": "user", "content": "Gitとは？"}]


@pytest.mark.asyncio
async def test_complete_propagates_sdk_errors():
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(side_effect=RuntimeError("rate limited"))

    client = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")

    with pytest.raises(RuntimeError, match="rate limited"):
        await client.complete(system_prompt="", history=[])
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
JWT_SECRET_KEY=test-secret uv run pytest tests/test_claude_client.py -v
```

期待: 旧 sync API のため `TypeError: object MagicMock is not iterable` 等で FAIL（または旧テスト残骸でエラー）。

- [ ] **Step 3: `app/core/claude_client.py` を書き換える**

```python
"""Anthropic Claude SDK の async ラッパー。テスト時はSDKをモック注入する。"""

from typing import Protocol

from anthropic import AsyncAnthropic

from app.config import settings


class _SDKLike(Protocol):
    messages: object


class ClaudeClient:
    def __init__(self, sdk: _SDKLike, model: str) -> None:
        self._sdk = sdk
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        max_tokens: int = 1024,
    ) -> str:
        response = await self._sdk.messages.create(  # type: ignore[attr-defined]
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=history,
        )
        return response.content[0].text


def get_claude_client() -> ClaudeClient:
    """FastAPI Dependsから利用するファクトリ。"""
    sdk = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return ClaudeClient(sdk=sdk, model=settings.anthropic_model)
```

- [ ] **Step 4: テストが PASS することを確認**

```bash
uv run pytest tests/test_claude_client.py -v
```

期待: 2 テスト PASS。

- [ ] **Step 5: `tests/test_chat_store.py` を書き換える（async）**

```python
import pytest

from app.memory.chat_store import InMemoryChatStore


@pytest.mark.asyncio
async def test_new_store_returns_empty_history():
    store = InMemoryChatStore()
    assert await store.get_history(user_id="u1", phase=1) == []


@pytest.mark.asyncio
async def test_append_then_get_returns_messages_in_order():
    store = InMemoryChatStore()
    await store.append(user_id="u1", phase=1, role="user", content="Git とは？")
    await store.append(user_id="u1", phase=1, role="assistant", content="バージョン管理…")

    history = await store.get_history(user_id="u1", phase=1)
    assert history == [
        {"role": "user", "content": "Git とは？"},
        {"role": "assistant", "content": "バージョン管理…"},
    ]


@pytest.mark.asyncio
async def test_history_is_scoped_per_user_and_phase():
    store = InMemoryChatStore()
    await store.append(user_id="u1", phase=1, role="user", content="A")
    await store.append(user_id="u1", phase=2, role="user", content="B")
    await store.append(user_id="u2", phase=1, role="user", content="C")

    assert await store.get_history("u1", 1) == [{"role": "user", "content": "A"}]
    assert await store.get_history("u1", 2) == [{"role": "user", "content": "B"}]
    assert await store.get_history("u2", 1) == [{"role": "user", "content": "C"}]


@pytest.mark.asyncio
async def test_clear_removes_only_targeted_thread():
    store = InMemoryChatStore()
    await store.append("u1", 1, "user", "A")
    await store.append("u1", 2, "user", "B")

    await store.clear("u1", 1)

    assert await store.get_history("u1", 1) == []
    assert await store.get_history("u1", 2) == [{"role": "user", "content": "B"}]
```

- [ ] **Step 6: `app/memory/chat_store.py` を async 化**

```python
"""Sprint 0 用のプロセス内会話履歴ストア（async 版）。Task 8 で SqlChatStore に置換。"""

from asyncio import Lock


class InMemoryChatStore:
    """In-process async chat history store (transitional)."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, int], list[dict[str, str]]] = {}
        self._lock = Lock()

    async def get_history(self, user_id: str, phase: int) -> list[dict[str, str]]:
        async with self._lock:
            return list(self._data.get((user_id, phase), []))

    async def append(self, user_id: str, phase: int, role: str, content: str) -> None:
        async with self._lock:
            self._data.setdefault((user_id, phase), []).append(
                {"role": role, "content": content}
            )

    async def clear(self, user_id: str, phase: int) -> None:
        async with self._lock:
            self._data.pop((user_id, phase), None)


_store_singleton = InMemoryChatStore()


def get_chat_store() -> InMemoryChatStore:
    return _store_singleton
```

- [ ] **Step 7: テストが PASS することを確認**

```bash
uv run pytest tests/test_chat_store.py -v
```

期待: 4 テスト PASS。

- [ ] **Step 8: `app/api/chat.py` を async 化**

```python
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.claude_client import ClaudeClient, get_claude_client
from app.data.curriculum import CURRICULUM
from app.memory.chat_store import InMemoryChatStore, get_chat_store
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    claude: ClaudeClient = Depends(get_claude_client),
    store: InMemoryChatStore = Depends(get_chat_store),
) -> ChatResponse:
    if request.phase not in CURRICULUM:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"phase {request.phase} not found",
        )

    history = await store.get_history(request.user_id, request.phase)
    next_history = history + [{"role": "user", "content": request.message}]

    reply = await claude.complete(
        system_prompt=CURRICULUM[request.phase]["system_prompt"],
        history=next_history,
    )

    await store.append(request.user_id, request.phase, "user", request.message)
    await store.append(request.user_id, request.phase, "assistant", reply)

    full_history = await store.get_history(request.user_id, request.phase)
    return ChatResponse(
        reply=reply,
        history=[ChatMessage(**m) for m in full_history],
    )
```

- [ ] **Step 9: `tests/test_api_chat.py` を async モックで書き換える**

```python
from unittest.mock import AsyncMock, MagicMock

from app.core.claude_client import ClaudeClient, get_claude_client
from app.memory.chat_store import InMemoryChatStore, get_chat_store


def _fake_client(*replies: str) -> tuple[ClaudeClient, MagicMock]:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        side_effect=[MagicMock(content=[MagicMock(text=r)]) for r in replies]
    )
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

        second_call = fake_sdk.messages.create.await_args_list[1]
        roles = [m["role"] for m in second_call.kwargs["messages"]]
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

`TestClient` は async ルートを内部で実行できるため、本タスク時点では sync 形式のままで良い。Task 7 で auth 統合する際に async client へ移行する。

- [ ] **Step 10: 全テストを通す**

```bash
JWT_SECRET_KEY=test-secret BCRYPT_ROUNDS=4 uv run pytest -v
```

期待: 全 PASS（既存 + 今回の async 化分）。

- [ ] **Step 11: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/core/claude_client.py backend/app/memory/chat_store.py backend/app/api/chat.py backend/tests/test_claude_client.py backend/tests/test_chat_store.py backend/tests/test_api_chat.py
git commit -m "refactor(backend): migrate chat pipeline to async (sync InMemoryChatStore -> async)"
```

---

## Task 6: Progress サービス + 非同期 conftest + テスト

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/services/__init__.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/services/progress.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/backend/tests/conftest.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_progress_service.py`

設計根拠: `docs/design/02-detailed-design.md` §2.9、`docs/design/06-test-design.md` §2.3。

- [ ] **Step 1: `app/services/__init__.py` を作成**

```python
```

- [ ] **Step 2: `app/services/progress.py` を作成（先に実装、後でテストでカバー）**

```python
"""Progress domain service."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.curriculum import CURRICULUM
from app.models.progress import Progress, ProgressStatus


class PhaseLockedError(Exception):
    def __init__(self, phase: int) -> None:
        super().__init__(f"phase {phase} is locked")
        self.phase = phase


class PhaseNotFoundError(Exception):
    def __init__(self, phase: int) -> None:
        super().__init__(f"progress for phase {phase} not found")
        self.phase = phase


async def initialize_progress(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Seed progress rows for a freshly-created user."""
    now = datetime.now(UTC)
    for phase_no in sorted(CURRICULUM.keys()):
        is_first = phase_no == 1
        db.add(
            Progress(
                user_id=user_id,
                phase=phase_no,
                status=(
                    ProgressStatus.IN_PROGRESS.value if is_first else ProgressStatus.LOCKED.value
                ),
                started_at=now if is_first else None,
            )
        )
    await db.flush()


async def list_progress(db: AsyncSession, user_id: uuid.UUID) -> list[Progress]:
    result = await db.execute(
        select(Progress).where(Progress.user_id == user_id).order_by(Progress.phase)
    )
    return list(result.scalars().all())


async def _get(db: AsyncSession, user_id: uuid.UUID, phase: int) -> Progress | None:
    result = await db.execute(
        select(Progress).where(Progress.user_id == user_id, Progress.phase == phase)
    )
    return result.scalar_one_or_none()


async def is_phase_unlocked(db: AsyncSession, user_id: uuid.UUID, phase: int) -> bool:
    p = await _get(db, user_id, phase)
    return p is not None and p.status != ProgressStatus.LOCKED.value


async def complete_phase(
    db: AsyncSession, user_id: uuid.UUID, phase: int
) -> tuple[Progress, Progress | None]:
    """Mark phase completed; if next phase is locked, unlock it.

    Returns (current, next_unlocked_or_None). Idempotent: re-calling on an
    already-completed phase succeeds with next_unlocked=None.
    """
    current = await _get(db, user_id, phase)
    if current is None:
        raise PhaseNotFoundError(phase)
    if current.status == ProgressStatus.LOCKED.value:
        raise PhaseLockedError(phase)

    now = datetime.now(UTC)
    if current.status != ProgressStatus.COMPLETED.value:
        current.status = ProgressStatus.COMPLETED.value
        current.completed_at = now

    next_unlocked: Progress | None = None
    next_phase = phase + 1
    if next_phase in CURRICULUM:
        nxt = await _get(db, user_id, next_phase)
        if nxt is not None and nxt.status == ProgressStatus.LOCKED.value:
            nxt.status = ProgressStatus.IN_PROGRESS.value
            nxt.started_at = now
            next_unlocked = nxt

    await db.commit()
    return current, next_unlocked
```

- [ ] **Step 3: `tests/conftest.py` を書き換える（async DB fixtures 追加）**

```python
import os

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_MODEL", "claude-sonnet-4-5")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor_test",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("BCRYPT_ROUNDS", "4")


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_db():
    """Create all tables once at session start, drop at end."""
    from app import models  # noqa: F401  ensures metadata registration
    from app.db.base import Base
    from app.db.session import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(_setup_db):
    """Truncate all tables before each test, then yield an AsyncSession."""
    from app.db.base import Base
    from app.db.session import SessionLocal, engine

    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(
                text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
            )

    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 4: `tests/test_progress_service.py` を作成**

```python
import uuid

import pytest

from app.core.security import hash_password
from app.models.progress import ProgressStatus
from app.models.user import User
from app.services.progress import (
    PhaseLockedError,
    PhaseNotFoundError,
    complete_phase,
    initialize_progress,
    is_phase_unlocked,
    list_progress,
)


async def _make_user(db, email: str = "alice@example.com") -> User:
    user = User(email=email, name="Alice", password_hash=hash_password("password123"))
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_initialize_progress_seeds_four_rows(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    await db_session.commit()
    rows = await list_progress(db_session, user.id)
    assert [r.phase for r in rows] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_initialize_phase1_in_progress_others_locked(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    await db_session.commit()
    rows = await list_progress(db_session, user.id)
    statuses = [r.status for r in rows]
    assert statuses == [
        ProgressStatus.IN_PROGRESS.value,
        ProgressStatus.LOCKED.value,
        ProgressStatus.LOCKED.value,
        ProgressStatus.LOCKED.value,
    ]
    assert rows[0].started_at is not None
    assert all(r.started_at is None for r in rows[1:])


@pytest.mark.asyncio
async def test_is_phase_unlocked(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    await db_session.commit()
    assert await is_phase_unlocked(db_session, user.id, 1) is True
    assert await is_phase_unlocked(db_session, user.id, 2) is False


@pytest.mark.asyncio
async def test_complete_phase_unlocks_next(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    await db_session.commit()

    current, nxt = await complete_phase(db_session, user.id, 1)
    assert current.status == ProgressStatus.COMPLETED.value
    assert current.completed_at is not None
    assert nxt is not None
    assert nxt.phase == 2
    assert nxt.status == ProgressStatus.IN_PROGRESS.value
    assert nxt.started_at is not None


@pytest.mark.asyncio
async def test_complete_last_phase_returns_no_next(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    # フェーズを順に解放
    for ph in [1, 2, 3]:
        await complete_phase(db_session, user.id, ph)

    current, nxt = await complete_phase(db_session, user.id, 4)
    assert current.phase == 4
    assert current.status == ProgressStatus.COMPLETED.value
    assert nxt is None


@pytest.mark.asyncio
async def test_complete_already_completed_is_idempotent(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    await db_session.commit()

    await complete_phase(db_session, user.id, 1)
    current, nxt = await complete_phase(db_session, user.id, 1)
    assert current.status == ProgressStatus.COMPLETED.value
    # next は既に in_progress 済なので unlock 対象外
    assert nxt is None


@pytest.mark.asyncio
async def test_complete_locked_phase_raises(db_session):
    user = await _make_user(db_session)
    await initialize_progress(db_session, user.id)
    await db_session.commit()
    with pytest.raises(PhaseLockedError):
        await complete_phase(db_session, user.id, 2)


@pytest.mark.asyncio
async def test_complete_missing_progress_raises(db_session):
    user = await _make_user(db_session)
    # initialize_progress を呼ばない
    await db_session.commit()
    with pytest.raises(PhaseNotFoundError):
        await complete_phase(db_session, user.id, 1)


@pytest.mark.asyncio
async def test_progress_isolated_per_user(db_session):
    alice = await _make_user(db_session, "alice@example.com")
    bob = await _make_user(db_session, "bob@example.com")
    await initialize_progress(db_session, alice.id)
    await initialize_progress(db_session, bob.id)
    await db_session.commit()

    await complete_phase(db_session, alice.id, 1)

    bob_rows = await list_progress(db_session, bob.id)
    assert bob_rows[0].status == ProgressStatus.IN_PROGRESS.value  # 未完了
    assert bob_rows[1].status == ProgressStatus.LOCKED.value
```

- [ ] **Step 5: テストが PASS することを確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
docker compose -f ../docker-compose.yml up -d postgres
uv run pytest tests/test_progress_service.py -v
```

期待: 9 テスト PASS。

- [ ] **Step 6: 既存テストも壊れていないことを確認**

```bash
uv run pytest -v
```

期待: 全 PASS。

- [ ] **Step 7: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/services backend/tests/conftest.py backend/tests/test_progress_service.py
git commit -m "feat(backend): add progress service with unlock logic and async DB fixtures"
```

---

## Task 7: 認証 API + deps + auth スキーマ + tests

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/schemas/auth.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/core/deps.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/api/auth.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/main.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/tests/conftest.py`（auth fixtures 追加）
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_api_auth.py`

設計根拠: `docs/design/02-detailed-design.md` §2.4、§2.11、`docs/design/04-interface-design.md` §3.2–3.4、`docs/design/06-test-design.md` §2.2。

- [ ] **Step 1: `app/schemas/auth.py` を作成**

```python
"""Auth DTOs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: `app/core/deps.py` を作成**

```python
"""FastAPI dependencies: DB session and current user."""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        sub = decode_access_token(token)
        uid = uuid.UUID(sub)
    except (JWTError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from e

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user
```

- [ ] **Step 3: `app/api/auth.py` を作成**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.progress import initialize_progress

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> UserOut:
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
    await initialize_progress(db, user.id)
    await db.commit()
    await db.refresh(user)

    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
```

- [ ] **Step 4: `app/main.py` に auth ルーターを追加**

`app.include_router(health.router)` の前に auth を追加。

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat as chat_router, curriculum, health
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
    app.include_router(auth.router)
    app.include_router(curriculum.router)
    app.include_router(chat_router.router)
    return app


app = create_app()
```

- [ ] **Step 5: `tests/conftest.py` に auth fixtures を追加**

ファイル末尾に追記する（既存の `db_session` の下）。

```python
@pytest_asyncio.fixture
async def auth_user(db_session):
    from app.core.security import hash_password
    from app.models.user import User
    from app.services.progress import initialize_progress

    user = User(
        email="alice@example.com",
        name="アリス",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.flush()
    await initialize_progress(db_session, user.id)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_token(auth_user) -> str:
    from app.core.security import create_access_token

    return create_access_token(subject=str(auth_user.id))


@pytest_asyncio.fixture
async def auth_client(client, auth_token):
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return client
```

- [ ] **Step 6: `tests/test_api_auth.py` を作成**

```python
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt
from sqlalchemy import select

from app.config import settings


def test_register_creates_user_and_progress(client, db_session):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "alice@example.com",
            "name": "アリス",
            "password": "password123",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["name"] == "アリス"
    assert "id" in body and "created_at" in body


def test_register_password_is_hashed(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "alice@example.com",
            "name": "アリス",
            "password": "password123",
        },
    )
    # 別途 DB セッションを開いて password_hash を確認
    import asyncio

    async def fetch():
        from app.db.session import SessionLocal
        from app.models.user import User

        async with SessionLocal() as session:
            row = (await session.execute(select(User))).scalar_one()
            return row.password_hash

    hashed = asyncio.run(fetch())
    assert hashed != "password123"
    assert hashed.startswith("$2")  # bcrypt prefix


def test_register_progress_rows_are_seeded(client):
    client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "name": "A", "password": "password123"},
    )
    import asyncio

    async def fetch():
        from app.db.session import SessionLocal
        from app.models.progress import Progress

        async with SessionLocal() as session:
            rows = (
                await session.execute(select(Progress).order_by(Progress.phase))
            ).scalars().all()
            return [(r.phase, r.status) for r in rows]

    rows = asyncio.run(fetch())
    assert rows == [
        (1, "in_progress"),
        (2, "locked"),
        (3, "locked"),
        (4, "locked"),
    ]


def test_register_returns_409_on_duplicate_email(client):
    payload = {"email": "alice@example.com", "name": "A", "password": "password123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_register_returns_422_on_short_password(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "name": "A", "password": "abc"},
    )
    assert response.status_code == 422


def test_register_returns_422_on_invalid_email(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "name": "A", "password": "password123"},
    )
    assert response.status_code == 422


def test_login_returns_token_on_valid_credentials(client):
    client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "name": "A", "password": "password123"},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_login_returns_401_on_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "name": "A", "password": "password123"},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "WRONG"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_returns_401_on_unknown_email(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "password123"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_me_returns_current_user(auth_client, auth_user):
    response = auth_client.get("/api/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == auth_user.email
    assert body["name"] == auth_user.name


def test_me_returns_401_without_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_returns_401_with_invalid_signature(client, auth_token):
    tampered = auth_token[:-2] + ("aa" if not auth_token.endswith("aa") else "bb")
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {tampered}"}
    )
    assert response.status_code == 401


def test_me_returns_401_with_expired_token(client, auth_user):
    payload = {
        "sub": str(auth_user.id),
        "exp": datetime.now(UTC) - timedelta(minutes=1),
    }
    expired = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401
```

- [ ] **Step 7: テスト実行**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
uv run pytest tests/test_api_auth.py -v
```

期待: 12 テスト PASS。

- [ ] **Step 8: 全テスト実行**

```bash
uv run pytest -v
```

期待: 全 PASS。Sprint 0 由来 + Task 4-6 + Task 7 で約 40 件以上。

- [ ] **Step 9: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/schemas/auth.py backend/app/core/deps.py backend/app/api/auth.py backend/app/main.py backend/tests/conftest.py backend/tests/test_api_auth.py
git commit -m "feat(backend): add JWT auth (register/login/me) with progress seed"
```

---

## Task 8: SqlChatStore（DB 永続化）+ テスト書換

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/memory/chat_store.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_chat_store.py`

設計根拠: `docs/design/02-detailed-design.md` §2.10、`docs/design/03-db-design.md` §3.3、`docs/design/06-test-design.md` §2.6。

`InMemoryChatStore` は削除し、`SqlChatStore` に置換する。`get_chat_store` の依存解決方法を `Depends(get_db)` 経由に切り替える。

- [ ] **Step 1: `tests/test_chat_store.py` を SqlChatStore 用に書き換える（テスト先行）**

```python
import uuid

import pytest

from app.core.security import hash_password
from app.memory.chat_store import SqlChatStore
from app.models.user import User


async def _make_user(db, email: str = "alice@example.com") -> User:
    user = User(email=email, name="A", password_hash=hash_password("password123"))
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_get_history_returns_empty_initially(db_session):
    user = await _make_user(db_session)
    store = SqlChatStore(db_session)
    assert await store.get_history(user.id, 1) == []


@pytest.mark.asyncio
async def test_append_then_get_returns_messages_in_order(db_session):
    user = await _make_user(db_session)
    store = SqlChatStore(db_session)

    await store.append(user.id, 1, "user", "Gitとは？")
    await store.append(user.id, 1, "assistant", "バージョン管理…")
    await db_session.commit()

    history = await store.get_history(user.id, 1)
    assert history == [
        {"role": "user", "content": "Gitとは？"},
        {"role": "assistant", "content": "バージョン管理…"},
    ]


@pytest.mark.asyncio
async def test_history_isolated_per_user(db_session):
    alice = await _make_user(db_session, "alice@example.com")
    bob = await _make_user(db_session, "bob@example.com")
    store = SqlChatStore(db_session)

    await store.append(alice.id, 1, "user", "A")
    await store.append(bob.id, 1, "user", "B")
    await db_session.commit()

    assert await store.get_history(alice.id, 1) == [{"role": "user", "content": "A"}]
    assert await store.get_history(bob.id, 1) == [{"role": "user", "content": "B"}]


@pytest.mark.asyncio
async def test_history_isolated_per_phase(db_session):
    user = await _make_user(db_session)
    store = SqlChatStore(db_session)

    await store.append(user.id, 1, "user", "P1")
    await store.append(user.id, 2, "user", "P2")
    await db_session.commit()

    assert await store.get_history(user.id, 1) == [{"role": "user", "content": "P1"}]
    assert await store.get_history(user.id, 2) == [{"role": "user", "content": "P2"}]


@pytest.mark.asyncio
async def test_history_persists_across_sessions(db_session):
    """ストアを使い回さず、別セッションで読み直しても見える。"""
    from app.db.session import SessionLocal

    user = await _make_user(db_session)
    SqlChatStore(db_session)
    store = SqlChatStore(db_session)
    await store.append(user.id, 1, "user", "永続")
    await db_session.commit()
    user_id = user.id

    async with SessionLocal() as another:
        other = SqlChatStore(another)
        history = await other.get_history(user_id, 1)
        assert history == [{"role": "user", "content": "永続"}]
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
uv run pytest tests/test_chat_store.py -v
```

期待: `ImportError: cannot import name 'SqlChatStore'`。

- [ ] **Step 3: `app/memory/chat_store.py` を SqlChatStore に書き換える**

```python
"""SQL-backed chat history store (Sprint 1)."""

import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.chat_history import ChatHistory


class SqlChatStore:
    """Async chat history store backed by `chat_history` table."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_history(
        self, user_id: uuid.UUID, phase: int
    ) -> list[dict[str, str]]:
        result = await self._db.execute(
            select(ChatHistory)
            .where(
                ChatHistory.user_id == user_id,
                ChatHistory.phase == phase,
            )
            .order_by(ChatHistory.created_at)
        )
        return [{"role": m.role, "content": m.content} for m in result.scalars().all()]

    async def append(
        self, user_id: uuid.UUID, phase: int, role: str, content: str
    ) -> None:
        self._db.add(
            ChatHistory(user_id=user_id, phase=phase, role=role, content=content)
        )
        await self._db.flush()


async def get_chat_store(db: AsyncSession = Depends(get_db)) -> SqlChatStore:
    return SqlChatStore(db)
```

`InMemoryChatStore` は削除（クラスごと消す）。`get_chat_store` のシグネチャが変わるので、後続タスクで `dependency_overrides` を見直す。

- [ ] **Step 4: テスト実行**

```bash
uv run pytest tests/test_chat_store.py -v
```

期待: 5 テスト PASS。

- [ ] **Step 5: 既存 test_api_chat.py が壊れているのを確認（次タスクで修正）**

```bash
uv run pytest tests/test_api_chat.py -v
```

期待: `ImportError: cannot import name 'InMemoryChatStore'` で FAIL。これは Task 9 で修正するため OK。

- [ ] **Step 6: 残りのテストが PASS することを確認**

```bash
uv run pytest --ignore=tests/test_api_chat.py -v
```

期待: 全 PASS。

- [ ] **Step 7: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/memory/chat_store.py backend/tests/test_chat_store.py
git commit -m "feat(backend): replace InMemoryChatStore with SqlChatStore (DB-backed)"
```

---

## Task 9: chat API 認証統合 + 履歴 GET エンドポイント

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/schemas/chat.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/api/chat.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_api_chat.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_api_chat_history.py`

設計根拠: `docs/design/02-detailed-design.md` §2.14、`docs/design/04-interface-design.md` §3.8–3.9、`docs/design/06-test-design.md` §2.8–2.9。

- [ ] **Step 1: `app/schemas/chat.py` から `user_id` を削除**

```python
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    phase: int = Field(ge=1, le=4)
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    reply: str
    history: list[ChatMessage]
```

- [ ] **Step 2: `tests/test_api_chat.py` を書き換える（テスト先行）**

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.claude_client import ClaudeClient, get_claude_client


def _fake_client(*replies: str) -> tuple[ClaudeClient, MagicMock]:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        side_effect=[MagicMock(content=[MagicMock(text=r)]) for r in replies]
    )
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5"), fake_sdk


def test_chat_requires_auth(client):
    response = client.post("/api/chat", json={"phase": 1, "message": "hi"})
    assert response.status_code == 401


def test_chat_returns_reply_and_persists_history(auth_client):
    from app.main import app

    fake, _ = _fake_client("Gitはバージョン管理ツールです")
    app.dependency_overrides[get_claude_client] = lambda: fake

    try:
        response = auth_client.post(
            "/api/chat", json={"phase": 1, "message": "Gitとは？"}
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


def test_chat_carries_history_across_calls(auth_client):
    from app.main import app

    fake, fake_sdk = _fake_client("一つ目", "二つ目")
    app.dependency_overrides[get_claude_client] = lambda: fake

    try:
        auth_client.post("/api/chat", json={"phase": 1, "message": "Q1"})
        auth_client.post("/api/chat", json={"phase": 1, "message": "Q2"})

        second_call = fake_sdk.messages.create.await_args_list[1]
        roles = [m["role"] for m in second_call.kwargs["messages"]]
        assert roles == ["user", "assistant", "user"]
    finally:
        app.dependency_overrides.clear()


def test_chat_rejects_invalid_phase_via_validation(auth_client):
    response = auth_client.post("/api/chat", json={"phase": 99, "message": "hi"})
    assert response.status_code == 422


def test_chat_rejects_locked_phase_with_403(auth_client):
    from app.main import app

    fake, _ = _fake_client("never reached")
    app.dependency_overrides[get_claude_client] = lambda: fake
    try:
        response = auth_client.post("/api/chat", json={"phase": 2, "message": "hi"})
        assert response.status_code == 403
        assert response.json()["detail"] == "phase 2 is locked"
    finally:
        app.dependency_overrides.clear()


def test_chat_propagates_502_on_claude_error(auth_client):
    from app.main import app

    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(side_effect=RuntimeError("upstream down"))
    fake = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")
    app.dependency_overrides[get_claude_client] = lambda: fake

    try:
        response = auth_client.post("/api/chat", json={"phase": 1, "message": "hi"})
        assert response.status_code == 502
    finally:
        app.dependency_overrides.clear()


def test_chat_does_not_accept_extra_user_id_field(auth_client):
    """旧 user_id フィールドを送っても無視される（pydantic extra='ignore' のデフォルト）。"""
    from app.main import app

    fake, _ = _fake_client("ok")
    app.dependency_overrides[get_claude_client] = lambda: fake
    try:
        response = auth_client.post(
            "/api/chat",
            json={"phase": 1, "message": "hi", "user_id": "spoof"},
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 3: `tests/test_api_chat_history.py` を新規作成**

```python
from unittest.mock import AsyncMock, MagicMock

from app.core.claude_client import ClaudeClient, get_claude_client


def _fake_client(*replies: str) -> ClaudeClient:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        side_effect=[MagicMock(content=[MagicMock(text=r)]) for r in replies]
    )
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")


def test_get_history_returns_empty_array_initially(auth_client):
    response = auth_client.get("/api/chat/history/1")
    assert response.status_code == 200
    assert response.json() == []


def test_get_history_returns_ordered_messages(auth_client):
    from app.main import app

    fake = _fake_client("A1", "A2")
    app.dependency_overrides[get_claude_client] = lambda: fake
    try:
        auth_client.post("/api/chat", json={"phase": 1, "message": "Q1"})
        auth_client.post("/api/chat", json={"phase": 1, "message": "Q2"})
    finally:
        app.dependency_overrides.clear()

    response = auth_client.get("/api/chat/history/1")
    assert response.status_code == 200
    history = response.json()
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    assert [m["content"] for m in history] == ["Q1", "A1", "Q2", "A2"]


def test_get_history_requires_auth(client):
    response = client.get("/api/chat/history/1")
    assert response.status_code == 401


def test_get_history_returns_403_for_locked_phase(auth_client):
    response = auth_client.get("/api/chat/history/2")
    assert response.status_code == 403
    assert response.json()["detail"] == "phase 2 is locked"


def test_get_history_rejects_invalid_phase(auth_client):
    response = auth_client.get("/api/chat/history/99")
    # FastAPI が path param のバリデーションエラーで 422
    assert response.status_code == 422
```

- [ ] **Step 4: テスト実行して失敗を確認**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
uv run pytest tests/test_api_chat.py tests/test_api_chat_history.py -v
```

期待: ルート定義側未対応のため複数 FAIL。

- [ ] **Step 5: `app/api/chat.py` を書き換える**

```python
from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.core.claude_client import ClaudeClient, get_claude_client
from app.core.deps import get_current_user
from app.data.curriculum import CURRICULUM
from app.memory.chat_store import SqlChatStore, get_chat_store
from app.models.user import User
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse
from app.services.progress import is_phase_unlocked

router = APIRouter(prefix="/api", tags=["chat"])


async def _ensure_phase_accessible(
    db_user: User, phase: int, store: SqlChatStore
) -> None:
    if phase not in CURRICULUM:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"phase {phase} not found"
        )
    unlocked = await is_phase_unlocked(store._db, db_user.id, phase)  # noqa: SLF001
    if not unlocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"phase {phase} is locked",
        )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    claude: ClaudeClient = Depends(get_claude_client),
    store: SqlChatStore = Depends(get_chat_store),
) -> ChatResponse:
    await _ensure_phase_accessible(current_user, request.phase, store)

    history = await store.get_history(current_user.id, request.phase)
    next_history = history + [{"role": "user", "content": request.message}]

    try:
        reply = await claude.complete(
            system_prompt=CURRICULUM[request.phase]["system_prompt"],
            history=next_history,
        )
    except Exception as e:  # noqa: BLE001  上流 SDK の例外は 502 に丸める
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="upstream LLM error"
        ) from e

    await store.append(current_user.id, request.phase, "user", request.message)
    await store.append(current_user.id, request.phase, "assistant", reply)
    await store._db.commit()  # noqa: SLF001  ハンドラがセッションのオーナー

    full_history = await store.get_history(current_user.id, request.phase)
    return ChatResponse(
        reply=reply,
        history=[ChatMessage(**m) for m in full_history],
    )


@router.get("/chat/history/{phase}", response_model=list[ChatMessage])
async def get_chat_history(
    phase: int = Path(ge=1, le=4),
    current_user: User = Depends(get_current_user),
    store: SqlChatStore = Depends(get_chat_store),
) -> list[ChatMessage]:
    await _ensure_phase_accessible(current_user, phase, store)
    history = await store.get_history(current_user.id, phase)
    return [ChatMessage(**m) for m in history]
```

NOTE: `store._db` への直接アクセスは「Sprint 1 では SqlChatStore が DB ハンドルを保持し、ハンドラはトランザクション境界の責務を持つ」設計の妥協。Sprint 2 で `services/chat.py` を切り出してリファクタする想定。

- [ ] **Step 6: テスト実行**

```bash
uv run pytest tests/test_api_chat.py tests/test_api_chat_history.py -v
```

期待: それぞれ 7 / 5 テスト PASS。

- [ ] **Step 7: 全テスト実行**

```bash
uv run pytest -v
```

期待: 全 PASS。

- [ ] **Step 8: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/schemas/chat.py backend/app/api/chat.py backend/tests/test_api_chat.py backend/tests/test_api_chat_history.py
git commit -m "feat(backend): require auth for chat, add history GET, enforce phase lock"
```

---

## Task 10: 進捗 API + curriculum 応答に locked を追加

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/schemas/progress.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/api/progress.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/schemas/curriculum.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/api/curriculum.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/main.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_api_curriculum.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_api_progress.py`

設計根拠: `docs/design/02-detailed-design.md` §2.12–2.13、`docs/design/04-interface-design.md` §3.5–3.7、`docs/design/06-test-design.md` §2.4–2.5。

- [ ] **Step 1: `app/schemas/progress.py` を作成**

```python
"""Progress DTOs."""

from datetime import datetime

from pydantic import BaseModel


class ProgressOut(BaseModel):
    phase: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ProgressCompleteResponse(BaseModel):
    phase: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    next_unlocked: ProgressOut | None
```

- [ ] **Step 2: `app/schemas/curriculum.py` に `locked` / `status` を追加**

```python
from pydantic import BaseModel


class PhaseSummary(BaseModel):
    phase: int
    title: str
    goal: str
    duration: str
    skills: list[str]
    tasks: list[str]
    locked: bool
    status: str
```

- [ ] **Step 3: `app/api/progress.py` を作成**

```python
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.progress import ProgressCompleteResponse, ProgressOut
from app.services.progress import (
    PhaseLockedError,
    PhaseNotFoundError,
    complete_phase,
    list_progress,
)

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("", response_model=list[ProgressOut])
async def list_my_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProgressOut]:
    rows = await list_progress(db, current_user.id)
    return [ProgressOut.model_validate(r) for r in rows]


@router.post("/{phase}/complete", response_model=ProgressCompleteResponse)
async def complete(
    phase: int = Path(ge=1, le=4),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgressCompleteResponse:
    try:
        current, next_unlocked = await complete_phase(db, current_user.id, phase)
    except PhaseLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"phase {e.phase} is locked"
        ) from e
    except PhaseNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"progress for phase {e.phase} not found",
        ) from e

    return ProgressCompleteResponse(
        phase=current.phase,
        status=current.status,
        started_at=current.started_at,
        completed_at=current.completed_at,
        next_unlocked=(
            ProgressOut.model_validate(next_unlocked) if next_unlocked else None
        ),
    )
```

- [ ] **Step 4: `app/api/curriculum.py` を書き換える（認証必須 + locked/status）**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.data.curriculum import CURRICULUM
from app.db.session import get_db
from app.models.progress import ProgressStatus
from app.models.user import User
from app.schemas.curriculum import PhaseSummary
from app.services.progress import list_progress

router = APIRouter(prefix="/api/curriculum", tags=["curriculum"])


@router.get("/phases", response_model=list[PhaseSummary])
async def list_phases(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PhaseSummary]:
    rows = await list_progress(db, current_user.id)
    status_by_phase = {r.phase: r.status for r in rows}

    return [
        PhaseSummary(
            phase=phase_no,
            title=phase["title"],
            goal=phase["goal"],
            duration=phase["duration"],
            skills=phase["skills"],
            tasks=phase["tasks"],
            locked=(
                status_by_phase.get(phase_no, ProgressStatus.LOCKED.value)
                == ProgressStatus.LOCKED.value
            ),
            status=status_by_phase.get(phase_no, ProgressStatus.LOCKED.value),
        )
        for phase_no, phase in sorted(CURRICULUM.items())
    ]
```

- [ ] **Step 5: `app/main.py` に progress ルーターを登録**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat as chat_router, curriculum, health, progress
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
    app.include_router(auth.router)
    app.include_router(curriculum.router)
    app.include_router(progress.router)
    app.include_router(chat_router.router)
    return app


app = create_app()
```

- [ ] **Step 6: `tests/test_api_curriculum.py` を書き換える**

```python
def test_list_phases_requires_auth(client):
    response = client.get("/api/curriculum/phases")
    assert response.status_code == 401


def test_list_phases_returns_four_with_locked_flags(auth_client):
    response = auth_client.get("/api/curriculum/phases")
    assert response.status_code == 200

    data = response.json()
    assert [item["phase"] for item in data] == [1, 2, 3, 4]
    assert [item["locked"] for item in data] == [False, True, True, True]
    assert data[0]["status"] == "in_progress"
    assert data[1]["status"] == "locked"


def test_list_phases_reflects_completion(auth_client):
    auth_client.post("/api/progress/1/complete")

    response = auth_client.get("/api/curriculum/phases")
    data = response.json()
    assert data[0]["status"] == "completed"
    assert data[0]["locked"] is False
    assert data[1]["status"] == "in_progress"
    assert data[1]["locked"] is False
```

- [ ] **Step 7: `tests/test_api_progress.py` を作成**

```python
def test_list_returns_four_phases(auth_client):
    response = auth_client.get("/api/progress")
    assert response.status_code == 200

    data = response.json()
    assert [item["phase"] for item in data] == [1, 2, 3, 4]
    assert [item["status"] for item in data] == [
        "in_progress",
        "locked",
        "locked",
        "locked",
    ]


def test_list_requires_auth(client):
    response = client.get("/api/progress")
    assert response.status_code == 401


def test_complete_phase_unlocks_next(auth_client):
    response = auth_client.post("/api/progress/1/complete")
    assert response.status_code == 200

    body = response.json()
    assert body["phase"] == 1
    assert body["status"] == "completed"
    assert body["next_unlocked"] is not None
    assert body["next_unlocked"]["phase"] == 2
    assert body["next_unlocked"]["status"] == "in_progress"


def test_complete_last_phase_no_next_unlocked(auth_client):
    auth_client.post("/api/progress/1/complete")
    auth_client.post("/api/progress/2/complete")
    auth_client.post("/api/progress/3/complete")

    response = auth_client.post("/api/progress/4/complete")
    assert response.status_code == 200
    assert response.json()["next_unlocked"] is None


def test_complete_locked_phase_returns_403(auth_client):
    response = auth_client.post("/api/progress/2/complete")
    assert response.status_code == 403
    assert response.json()["detail"] == "phase 2 is locked"


def test_complete_phase_out_of_range_returns_422(auth_client):
    response = auth_client.post("/api/progress/99/complete")
    assert response.status_code == 422


def test_complete_requires_auth(client):
    response = client.post("/api/progress/1/complete")
    assert response.status_code == 401


def test_complete_is_idempotent(auth_client):
    auth_client.post("/api/progress/1/complete")
    response = auth_client.post("/api/progress/1/complete")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    # 2 回目では next は既に解放済なので unlock 対象外
    assert body["next_unlocked"] is None
```

- [ ] **Step 8: テスト実行**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
uv run pytest tests/test_api_progress.py tests/test_api_curriculum.py -v
```

期待: それぞれ全 PASS。

- [ ] **Step 9: 全テスト実行 + カバレッジ確認**

```bash
uv run pytest --cov=app --cov-report=term-missing -v
```

期待: 全 PASS、`app/` のカバレッジが 80% 以上。

- [ ] **Step 10: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/app/schemas/progress.py backend/app/api/progress.py backend/app/schemas/curriculum.py backend/app/api/curriculum.py backend/app/main.py backend/tests/test_api_curriculum.py backend/tests/test_api_progress.py
git commit -m "feat(backend): add progress API and add locked flag to curriculum"
```

---

## Task 11: フロントエンド — 認証ストア + ログイン画面 + ルーターガード

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/package.json`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/stores/auth.ts`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/views/LoginView.vue`
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/lib/api.ts`
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/router/index.ts`
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/main.ts`
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/App.vue`
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/types/curriculum.ts`

設計根拠: `docs/design/02-detailed-design.md` §6、`docs/design/05-screen-design.md` §3。

- [ ] **Step 1: `frontend/package.json` に persistedstate を追加**

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
    "pinia-plugin-persistedstate": "^4.0.0",
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

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend
npm install
```

- [ ] **Step 2: `src/types/curriculum.ts` を拡張**

```ts
export interface PhaseSummary {
  phase: number;
  title: string;
  goal: string;
  duration: string;
  skills: string[];
  tasks: string[];
  locked: boolean;
  status: 'locked' | 'in_progress' | 'submitted' | 'completed';
}

export interface ProgressOut {
  phase: number;
  status: 'locked' | 'in_progress' | 'submitted' | 'completed';
  started_at: string | null;
  completed_at: string | null;
}

export interface ProgressCompleteResponse extends ProgressOut {
  next_unlocked: ProgressOut | null;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  reply: string;
  history: ChatMessage[];
}

export interface UserOut {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
```

- [ ] **Step 3: `src/stores/auth.ts` を作成**

```ts
import { defineStore } from 'pinia';
import type { TokenResponse, UserOut } from '@/types/curriculum';
import { rawRequest } from '@/lib/api';

interface State {
  token: string | null;
  user: UserOut | null;
}

export const useAuthStore = defineStore('auth', {
  state: (): State => ({ token: null, user: null }),
  getters: {
    isAuthenticated: (s) => s.token !== null,
  },
  actions: {
    async login(email: string, password: string) {
      const t = await rawRequest<TokenResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      this.token = t.access_token;
      await this.fetchMe();
    },

    async register(email: string, name: string, password: string) {
      await rawRequest<UserOut>('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, name, password }),
      });
    },

    async fetchMe() {
      if (!this.token) return;
      this.user = await rawRequest<UserOut>('/api/auth/me', { method: 'GET' });
    },

    logout() {
      this.token = null;
      this.user = null;
    },
  },
  persist: {
    paths: ['token'],
  },
});
```

- [ ] **Step 4: `src/lib/api.ts` をトークン注入 + 401 ハンドラ付きに書き換える**

```ts
import type {
  ChatResponse,
  PhaseSummary,
  ProgressCompleteResponse,
  ProgressOut,
} from '@/types/curriculum';

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

let _onUnauthorized: (() => void) | null = null;

export function registerUnauthorizedHandler(cb: () => void) {
  _onUnauthorized = cb;
}

function getToken(): string | null {
  try {
    const persisted = localStorage.getItem('auth');
    if (!persisted) return null;
    return (JSON.parse(persisted) as { token: string | null }).token;
  } catch {
    return null;
  }
}

export async function rawRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${baseUrl}${path}`, { ...init, headers });

  if (response.status === 401) {
    if (_onUnauthorized) _onUnauthorized();
    throw new Error('Unauthorized');
  }
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listPhases: () => rawRequest<PhaseSummary[]>('/api/curriculum/phases'),

  listProgress: () => rawRequest<ProgressOut[]>('/api/progress'),

  completePhase: (phase: number) =>
    rawRequest<ProgressCompleteResponse>(`/api/progress/${phase}/complete`, {
      method: 'POST',
    }),

  getChatHistory: (phase: number) =>
    rawRequest<{ role: 'user' | 'assistant'; content: string }[]>(
      `/api/chat/history/${phase}`,
    ),

  sendChat: (payload: { phase: number; message: string }) =>
    rawRequest<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
```

NOTE: pinia-plugin-persistedstate v4 のデフォルト key は store id（`auth`）。`localStorage.getItem('auth')` で取り出せる。

- [ ] **Step 5: `src/views/LoginView.vue` を作成**

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const mode = ref<'login' | 'register'>('login');
const email = ref('');
const password = ref('');
const name = ref('');
const error = ref<string | null>(null);
const notice = ref<string | null>(null);
const submitting = ref(false);

const auth = useAuthStore();
const router = useRouter();

const submit = async () => {
  error.value = null;
  notice.value = null;
  submitting.value = true;
  try {
    if (mode.value === 'login') {
      await auth.login(email.value, password.value);
      await router.push('/');
    } else {
      await auth.register(email.value, name.value, password.value);
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

<template>
  <section class="login">
    <nav class="tabs" role="tablist">
      <button
        :class="{ active: mode === 'login' }"
        role="tab"
        :aria-selected="mode === 'login'"
        @click="mode = 'login'"
      >
        ログイン
      </button>
      <button
        :class="{ active: mode === 'register' }"
        role="tab"
        :aria-selected="mode === 'register'"
        @click="mode = 'register'"
      >
        新規登録
      </button>
    </nav>

    <form class="form" @submit.prevent="submit">
      <label>
        メールアドレス
        <input v-model="email" type="email" autocomplete="email" required />
      </label>

      <label v-if="mode === 'register'">
        お名前
        <input v-model="name" type="text" maxlength="100" required />
      </label>

      <label>
        パスワード
        <input
          v-model="password"
          type="password"
          minlength="8"
          maxlength="128"
          autocomplete="current-password"
          required
        />
      </label>

      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="notice" class="notice" role="status">{{ notice }}</p>

      <button type="submit" :disabled="submitting">
        {{ mode === 'login' ? 'ログイン' : '登録する' }}
      </button>
    </form>
  </section>
</template>

<style scoped>
.login {
  max-width: 420px;
  margin: 2rem auto;
  background: var(--color-surface, white);
  border-radius: var(--radius, 14px);
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  padding: 1.5rem;
}
.tabs {
  display: flex;
  gap: 0.5rem;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 0.5rem;
  margin-bottom: 1rem;
}
.tabs button {
  background: none;
  border: 0;
  padding: 0.5rem 1rem;
  cursor: pointer;
  font: inherit;
  color: #6b7280;
}
.tabs button.active {
  color: var(--color-accent, #2f6df6);
  border-bottom: 2px solid var(--color-accent, #2f6df6);
}
.form { display: flex; flex-direction: column; gap: 1rem; }
.form label { display: flex; flex-direction: column; font-size: 0.9rem; gap: 0.35rem; }
.form input {
  padding: 0.6rem 0.8rem;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  font: inherit;
}
.form button[type='submit'] {
  background: var(--color-accent, #2f6df6);
  color: white;
  border: 0;
  border-radius: 10px;
  padding: 0.7rem;
  font-weight: 600;
  cursor: pointer;
}
.form button[type='submit']:disabled { opacity: 0.5; cursor: not-allowed; }
.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 0.6rem 0.8rem;
  border-radius: 10px;
  margin: 0;
}
.notice {
  background: #dcfce7;
  color: #166534;
  padding: 0.6rem 0.8rem;
  border-radius: 10px;
  margin: 0;
}
</style>
```

- [ ] **Step 6: `src/router/index.ts` にガードを追加**

```ts
import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '@/views/HomeView.vue';
import PhaseChatView from '@/views/PhaseChatView.vue';
import LoginView from '@/views/LoginView.vue';
import { useAuthStore } from '@/stores/auth';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', name: 'home', component: HomeView },
    {
      path: '/phases/:phase',
      name: 'phase',
      component: PhaseChatView,
      props: (route) => ({ phase: Number(route.params.phase) }),
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.public !== true && !auth.isAuthenticated) {
    return { name: 'login' };
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'home' };
  }
  return true;
});
```

- [ ] **Step 7: `src/main.ts` を更新（persistedstate + 401 ハンドラ）**

```ts
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate';
import App from '@/App.vue';
import { router } from '@/router';
import { useAuthStore } from '@/stores/auth';
import { registerUnauthorizedHandler } from '@/lib/api';

const pinia = createPinia();
pinia.use(piniaPluginPersistedstate);

const app = createApp(App);
app.use(pinia);
app.use(router);

const auth = useAuthStore();
registerUnauthorizedHandler(() => {
  auth.logout();
  router.push('/login');
});

// 復帰時に /me を取り直して user state を埋める
if (auth.isAuthenticated) {
  auth.fetchMe().catch(() => {
    auth.logout();
  });
}

app.mount('#app');
```

- [ ] **Step 8: `src/App.vue` にユーザ情報 + ログアウトを追加**

```vue
<script setup lang="ts">
import { RouterView, useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const logout = async () => {
  auth.logout();
  await router.push('/login');
};
</script>

<template>
  <header class="app-header">
    <div class="left">
      <h1>AI駆動型開発 補足カリキュラム</h1>
      <p>AIチューター — 学習サポートシステム</p>
    </div>
    <div class="right" v-if="auth.user && route.name !== 'login'">
      <span class="who">{{ auth.user.name }} さん</span>
      <button type="button" @click="logout">ログアウト</button>
    </div>
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
  --color-danger: #ef4444;
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}
.app-header h1 { margin: 0; font-size: 1.25rem; }
.app-header p { margin: 0.25rem 0 0; color: #6b7280; font-size: 0.875rem; }
.right { display: flex; align-items: center; gap: 1rem; }
.who { color: #374151; font-size: 0.9rem; }
.right button {
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.4rem 0.8rem;
  cursor: pointer;
  font: inherit;
}
.right button:hover { border-color: var(--color-accent); }

.app-main { padding: 2rem; max-width: 960px; margin: 0 auto; }
</style>
```

- [ ] **Step 9: 型ビルドを通す**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend
npm run build
```

期待: 型エラーなしでビルド成功。

- [ ] **Step 10: 手動動作確認**

```bash
cd /Volumes/Seagate3TB/projects/edu
docker compose up
```

ブラウザで `http://localhost:5173`:
- 未ログインで `/` を開く → `/login` にリダイレクト
- 新規登録 → ログイン → `/` 遷移
- リロード → `/` が維持される（localStorage トークン復元）
- ログアウト → `/login` に戻る

- [ ] **Step 11: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/package.json frontend/package-lock.json frontend/src/stores/auth.ts frontend/src/views/LoginView.vue frontend/src/lib/api.ts frontend/src/router/index.ts frontend/src/main.ts frontend/src/App.vue frontend/src/types/curriculum.ts
git commit -m "feat(frontend): add auth store, login view, router guard, and 401 handler"
```

---

## Task 12: フロントエンド — フェーズ一覧にロック / 進捗バッジを反映

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/stores/curriculum.ts`
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/components/PhaseCard.vue`
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/views/HomeView.vue`

設計根拠: `docs/design/05-screen-design.md` §4。

- [ ] **Step 1: `src/stores/curriculum.ts` を書き換える**

```ts
import { defineStore } from 'pinia';
import { api } from '@/lib/api';
import type {
  ChatMessage,
  PhaseSummary,
  ProgressCompleteResponse,
  ProgressOut,
} from '@/types/curriculum';

interface State {
  phases: PhaseSummary[];
  progress: Record<number, ProgressOut>;
  chatLogs: Record<number, ChatMessage[]>;
  loading: boolean;
  error: string | null;
}

export const useCurriculumStore = defineStore('curriculum', {
  state: (): State => ({
    phases: [],
    progress: {},
    chatLogs: {},
    loading: false,
    error: null,
  }),
  getters: {
    completedCount: (s) =>
      Object.values(s.progress).filter((p) => p.status === 'completed').length,
  },
  actions: {
    async fetchPhasesWithProgress() {
      this.loading = true;
      this.error = null;
      try {
        const [phases, progress] = await Promise.all([
          api.listPhases(),
          api.listProgress(),
        ]);
        this.phases = phases;
        this.progress = Object.fromEntries(progress.map((p) => [p.phase, p]));
      } catch (e) {
        this.error = e instanceof Error ? e.message : 'unknown error';
      } finally {
        this.loading = false;
      }
    },

    async completePhase(phase: number): Promise<ProgressCompleteResponse> {
      const result = await api.completePhase(phase);

      this.progress[phase] = {
        phase: result.phase,
        status: result.status,
        started_at: result.started_at,
        completed_at: result.completed_at,
      };
      if (result.next_unlocked) {
        const n = result.next_unlocked;
        this.progress[n.phase] = n;
      }

      // PhaseSummary 内の locked / status も同期
      this.phases = this.phases.map((p) => {
        const prog = this.progress[p.phase];
        if (!prog) return p;
        return { ...p, locked: prog.status === 'locked', status: prog.status };
      });
      return result;
    },

    async loadHistory(phase: number) {
      const history = await api.getChatHistory(phase);
      this.chatLogs[phase] = history.map((m) => ({
        role: m.role,
        content: m.content,
      }));
    },

    async sendChat(phase: number, message: string) {
      const result = await api.sendChat({ phase, message });
      this.chatLogs[phase] = result.history;
      return result.reply;
    },

    getPhase(phaseNo: number): PhaseSummary | undefined {
      return this.phases.find((p) => p.phase === phaseNo);
    },
  },
});
```

- [ ] **Step 2: `src/components/PhaseCard.vue` をロック対応に書き換える**

```vue
<script setup lang="ts">
import { computed } from 'vue';
import type { PhaseSummary } from '@/types/curriculum';

const props = defineProps<{ phase: PhaseSummary }>();

const badgeLabel = computed(() => {
  switch (props.phase.status) {
    case 'in_progress':
      return '進行中';
    case 'submitted':
      return '提出済み';
    case 'completed':
      return '完了';
    default:
      return 'ロック';
  }
});

const lockReason = computed(() => {
  if (!props.phase.locked) return '';
  if (props.phase.phase === 1) return '';
  return `Phase ${props.phase.phase - 1} を完了すると解放されます`;
});
</script>

<template>
  <article class="phase-card" :class="{ locked: phase.locked }">
    <header>
      <span class="phase-no">Phase {{ phase.phase }}</span>
      <span class="badge" :data-status="phase.status">{{ badgeLabel }}</span>
      <h2>{{ phase.title }}</h2>
      <p class="duration">{{ phase.duration }}</p>
    </header>

    <p class="goal">{{ phase.goal }}</p>

    <template v-if="!phase.locked">
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

      <RouterLink
        :to="{ name: 'phase', params: { phase: phase.phase } }"
        class="cta"
      >
        AIチューターと対話する →
      </RouterLink>
    </template>

    <template v-else>
      <p class="lock-msg" aria-live="polite">🔒 {{ lockReason }}</p>
    </template>
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
  position: relative;
}
.phase-card.locked { filter: grayscale(0.4); opacity: 0.78; }

.phase-no {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-accent);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.badge {
  display: inline-block;
  margin-left: 0.5rem;
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
  background: #e5e7eb;
  color: #374151;
}
.badge[data-status='in_progress'] { background: #dbeafe; color: #1d4ed8; }
.badge[data-status='completed']   { background: #dcfce7; color: #166534; }
.badge[data-status='submitted']   { background: #fef3c7; color: #92400e; }
.badge[data-status='locked']      { background: #f3f4f6; color: #6b7280; }

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
.lock-msg { color: #6b7280; font-size: 0.9rem; margin: 0; }
</style>
```

- [ ] **Step 3: `src/views/HomeView.vue` を書き換える**

```vue
<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useCurriculumStore } from '@/stores/curriculum';
import PhaseCard from '@/components/PhaseCard.vue';

const store = useCurriculumStore();
const completed = computed(() => store.completedCount);

onMounted(() => {
  if (store.phases.length === 0) {
    void store.fetchPhasesWithProgress();
  }
});

const reload = () => store.fetchPhasesWithProgress();
</script>

<template>
  <section v-if="store.loading">読み込み中…</section>
  <section v-else-if="store.error" class="error">
    <p>エラー: {{ store.error }}</p>
    <button type="button" @click="reload">再読み込み</button>
  </section>
  <template v-else>
    <p class="progress-summary">
      あなたの進捗: <strong>{{ completed }} / 4</strong> フェーズ完了
    </p>
    <section class="phase-grid">
      <PhaseCard v-for="p in store.phases" :key="p.phase" :phase="p" />
    </section>
  </template>
</template>

<style scoped>
.progress-summary {
  color: #374151;
  font-size: 0.95rem;
  margin: 0 0 1rem;
}
.phase-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.25rem;
}
.error {
  background: #fee2e2;
  color: #991b1b;
  padding: 1rem;
  border-radius: 12px;
}
.error button {
  margin-top: 0.5rem;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.4rem 0.8rem;
  cursor: pointer;
}
</style>
```

- [ ] **Step 4: 型ビルド**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend
npm run build
```

期待: 型エラーなし。

- [ ] **Step 5: 手動確認**

`make dev` 起動状態で：
- 新規登録 → ログイン後 `/`
- Phase 1 のみカードが活性、Phase 2–4 はロック表示
- 進捗サマリ「0 / 4 フェーズ完了」

- [ ] **Step 6: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/stores/curriculum.ts frontend/src/components/PhaseCard.vue frontend/src/views/HomeView.vue
git commit -m "feat(frontend): reflect lock state and progress on phase list"
```

---

## Task 13: フロントエンド — チャット履歴ロード + 完了ボタン

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/views/PhaseChatView.vue`

設計根拠: `docs/design/05-screen-design.md` §5。

- [ ] **Step 1: `src/views/PhaseChatView.vue` を書き換える**

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useCurriculumStore } from '@/stores/curriculum';
import ChatLog from '@/components/ChatLog.vue';
import ChatInput from '@/components/ChatInput.vue';

const props = defineProps<{ phase: number }>();
const store = useCurriculumStore();
const router = useRouter();

const sending = ref(false);
const sendError = ref<string | null>(null);
const confirmingComplete = ref(false);
const completing = ref(false);

const phaseData = computed(() => store.getPhase(props.phase));
const messages = computed(() => store.chatLogs[props.phase] ?? []);
const quickQuestions = computed(() => phaseData.value?.tasks.slice(0, 3) ?? []);

const isLastPhase = computed(() => props.phase === 4);
const completionLabel = computed(() =>
  phaseData.value?.status === 'completed' ? '完了済み' : 'このフェーズを完了する',
);

onMounted(async () => {
  if (store.phases.length === 0) {
    await store.fetchPhasesWithProgress();
  }
  const data = store.getPhase(props.phase);
  if (!data) {
    return;
  }
  if (data.locked) {
    await router.push('/');
    return;
  }
  await store.loadHistory(props.phase);
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

const openConfirm = () => {
  confirmingComplete.value = true;
};

const cancelConfirm = () => {
  confirmingComplete.value = false;
};

const confirmComplete = async () => {
  completing.value = true;
  try {
    await store.completePhase(props.phase);
    confirmingComplete.value = false;
    await router.push('/');
  } catch (e) {
    sendError.value = e instanceof Error ? e.message : 'unknown error';
  } finally {
    completing.value = false;
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
    <p v-if="sending" class="thinking">AIが応答中…</p>
    <p v-if="sendError" class="error" role="alert">エラー: {{ sendError }}</p>
    <ChatInput :disabled="sending" @submit="submit" />

    <hr />

    <button
      type="button"
      class="complete-btn"
      :disabled="completing"
      @click="openConfirm"
    >
      {{ completionLabel }}
    </button>

    <div v-if="confirmingComplete" class="modal-backdrop" role="dialog" aria-modal="true">
      <div class="modal">
        <h3>Phase {{ phaseData.phase }} を完了しますか？</h3>
        <p v-if="!isLastPhase">完了すると Phase {{ phaseData.phase + 1 }} が解放されます。履歴は引き続き閲覧できます。</p>
        <p v-else>すべてのカリキュラムを終了します。履歴は引き続き閲覧できます。</p>
        <div class="actions">
          <button type="button" @click="cancelConfirm" :disabled="completing">キャンセル</button>
          <button type="button" class="primary" @click="confirmComplete" :disabled="completing">
            {{ completing ? '完了処理中…' : '完了する' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.phase-chat { display: flex; flex-direction: column; gap: 1rem; }
.phase-chat header h2 { margin: 0.5rem 0 0.25rem; font-size: 1.2rem; }
.phase-chat header a { color: var(--color-accent); text-decoration: none; font-size: 0.9rem; }
.quick { display: flex; flex-direction: column; gap: 0.4rem; }
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
.thinking { color: #6b7280; font-size: 0.9rem; margin: 0; }
hr { border: 0; border-top: 1px solid #e5e7eb; margin: 1rem 0; }
.complete-btn {
  align-self: flex-start;
  background: var(--color-accent);
  color: white;
  border: 0;
  border-radius: 10px;
  padding: 0.7rem 1.2rem;
  font-weight: 600;
  cursor: pointer;
}
.complete-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.modal {
  background: white;
  padding: 1.5rem;
  border-radius: 16px;
  max-width: 420px;
  width: calc(100% - 2rem);
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.18);
}
.modal h3 { margin: 0 0 0.5rem; font-size: 1.05rem; }
.modal p { margin: 0 0 1rem; color: #374151; }
.actions { display: flex; justify-content: flex-end; gap: 0.5rem; }
.actions button {
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.5rem 0.9rem;
  cursor: pointer;
}
.actions button.primary {
  background: var(--color-accent);
  color: white;
  border-color: var(--color-accent);
}
.actions button:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
```

- [ ] **Step 2: 型ビルド**

```bash
cd /Volumes/Seagate3TB/projects/edu/frontend
npm run build
```

期待: 型エラーなし。

- [ ] **Step 3: 手動 E2E 確認**

`make dev` の状態で：
1. 新規登録 → ログイン
2. Phase 1 を開く → 履歴空、入力可能
3. メッセージを 1 件送信 → 履歴に user / assistant
4. 「このフェーズを完了する」→ 確認ダイアログ → 「完了する」
5. `/` に戻り Phase 1 が「完了」バッジ、Phase 2 が「進行中」
6. ページリロード → 認証維持、進捗・履歴も復元

- [ ] **Step 4: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add frontend/src/views/PhaseChatView.vue
git commit -m "feat(frontend): load chat history and add phase completion modal"
```

---

## Task 14: Makefile / README / .env.example 整備 + Sprint 1 完了マーク

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/Makefile`
- Modify: `/Volumes/Seagate3TB/projects/edu/README.md`

- [ ] **Step 1: `Makefile` に migrate / db-shell ターゲットを追加**

```makefile
.PHONY: dev test test-backend test-frontend lint clean migrate revision db-shell

dev:
	docker compose up --build

migrate:
	cd backend && uv run alembic upgrade head

revision:
	@if [ -z "$(M)" ]; then echo "Usage: make revision M='message'"; exit 1; fi
	cd backend && uv run alembic revision --autogenerate -m "$(M)"

db-shell:
	docker compose exec postgres psql -U postgres -d ai_tutor

test: test-backend test-frontend

test-backend:
	docker compose up -d postgres
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

- [ ] **Step 2: `README.md` を更新**

```markdown
# AI駆動型開発 補足カリキュラム — AIチューター

FastAPI + Vue.js + PostgreSQL による AI駆動型開発カリキュラム学習支援ツールのリファレンス実装。

## セットアップ

```bash
cp .env.example .env
# .env を編集して以下を設定:
#   ANTHROPIC_API_KEY     Claude API キー
#   JWT_SECRET_KEY        openssl rand -hex 32 で生成した値
```

## 開発起動

### Docker Composeで起動（推奨）

```bash
make dev
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs
- Postgres: localhost:5432（user/password: postgres/postgres）

backend コンテナは起動時に `alembic upgrade head` を自動実行する。

### ローカル直接起動

```bash
# Postgres
docker compose up -d postgres

# Backend
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## マイグレーション

```bash
make migrate                   # alembic upgrade head
make revision M="add foo"      # autogenerate
make db-shell                  # psql に接続
```

## テスト

```bash
make test                      # backend + frontend
make test-backend              # pytest
make test-frontend             # vitest
```

## ディレクトリ構成

設計書: `docs/design/`
- 01 システム基本設計
- 02 詳細設計
- 03 DB設計
- 04 IF設計
- 05 画面設計
- 06 テスト設計

実装計画:
- Sprint 0: `docs/superpowers/plans/2026-06-01-ai-tutor-curriculum-sprint-0.md`
- Sprint 1: `docs/superpowers/plans/2026-06-02-ai-tutor-curriculum-sprint-1.md`

## 実装進捗

- [x] Sprint 0: スケルトン + カリキュラム配信 + AIチューター対話MVP
- [x] Sprint 1: PostgreSQL + JWT 認証 + 進捗管理 + 会話履歴永続化
- [ ] Sprint 2: 課題提出 + AI採点 + RAG (pgvector)
- [ ] Sprint 3: 管理者ダッシュボード
- [ ] Sprint 4: CI/CD + 本番デプロイ + 監視

詳細は `docs/superpowers/plans/` を参照。
```

- [ ] **Step 3: 最終チェック**

```bash
cd /Volumes/Seagate3TB/projects/edu
make clean
make dev &
sleep 30
make test
make lint
```

期待: 全テスト PASS / lint エラー無し。

- [ ] **Step 4: コミット**

```bash
git add Makefile README.md
git commit -m "docs: mark Sprint 1 complete and document migration workflow"
```

---

## 完了基準（Sprint 1 受入チェックリスト）

設計書 `docs/design/06-test-design.md` §5 と同等。実装完了時に以下を確認すること。

### 機能

- [ ] `make test` で全テスト PASS（バックエンド + フロントエンド）
- [ ] `make dev` で 3 サービスが起動し、ブラウザから 登録 → ログイン → チャット → 完了 → 次フェーズ解放 まで一気通貫
- [ ] `docker compose down -v && make dev` でマイグレーションが自動適用される
- [ ] フェーズロック迂回（直接 POST）に 403
- [ ] 期限切れ JWT で 401 → フロントが `/login` に強制遷移
- [ ] リロード後に進捗・履歴・ログイン状態がすべて復元される

### 非機能

- [ ] バックエンドカバレッジ ≥ 80%
- [ ] `ruff check app tests` がエラー無し
- [ ] `vue-tsc` で型エラー無し
- [ ] OpenAPI（`/docs`）に Bearer auth が反映

### ドキュメント

- [ ] README の Sprint 1 を `[x]` 完了マーク
- [ ] 設計書 01〜06 と差分が無い（差分があれば版数 1.1 に更新）

---

## 後続スプリント（ロードマップ）

| Sprint | 主スコープ | 主な追加 |
|---|---|---|
| 2 | 課題提出 + AI 採点 + RAG | `submissions` テーブル、ファイルアップロード、pgvector 検索、Claude による評価 |
| 3 | 管理者ダッシュボード | ロール（`is_admin`）、全受講者進捗一覧、コメント、通知 |
| 4 | CI/CD + 本番 + 監視 | GitHub Actions、AWS デプロイ、Sentry / OpenTelemetry、Secrets Manager |

---

## 自己レビュー（Self-Review）

writing-plans スキルに従い、本書を仕上げた後にチェックしたメモ。

### スペック網羅性

| 設計書要件 | 対応タスク |
|---|---|
| Postgres + pgvector | Task 1 |
| 認証（register/login/me） | Task 7 |
| 進捗 seed + 解放ロジック | Task 6 + Task 7 register |
| 進捗 API | Task 10 |
| curriculum locked | Task 10 |
| チャット async 化 | Task 5 |
| SqlChatStore | Task 8 |
| chat 認証統合 + history GET | Task 9 |
| フロント認証 UI | Task 11 |
| フロント ロック表示 | Task 12 |
| フロント 履歴ロード + 完了ボタン | Task 13 |
| README / Makefile 更新 | Task 14 |
| security ユニットテスト | Task 4 |
| 進捗サービスユニットテスト | Task 6 |
| API テスト（auth / progress / curriculum / chat / history） | Task 7, 9, 10 |

### プレースホルダー検査

- "TBD" / "TODO" / "implement later" — なし
- 「Similar to Task N」での省略 — なし。各タスクで完結
- コード未記載のステップ — なし

### 型・シグネチャ整合性

- `SqlChatStore.append(user_id, phase, role, content)` — Task 8 で定義、Task 9 chat ルートで使用
- `complete_phase(db, user_id, phase) -> tuple[Progress, Progress | None]` — Task 6 定義、Task 10 API で使用
- `initialize_progress(db, user_id)` — Task 6 定義、Task 7 register で使用
- `create_access_token(*, subject, expires_min=None)` — Task 4 定義、Task 7 login / conftest auth_token で使用

### 既知の妥協

- Task 9 で `store._db.commit()` のように `SqlChatStore` 内部の DB セッションへ直接アクセスしている。Sprint 2 で `services/chat.py` を切り出してリファクタする
- email の大小区別は Sprint 1 では受容（Sprint 2 で `citext` 化検討）

---

## 実行ハンドオフ

本計画書は保存済み：`docs/superpowers/plans/2026-06-02-ai-tutor-curriculum-sprint-1.md`。

実装の進め方は 2 通り。**実行する際に好みを指定してください。**

1. **Subagent-Driven (推奨)** — タスク毎に新規サブエージェントを派生、レビュー挟みながら高速反復
   - 必要スキル: `superpowers:subagent-driven-development`
2. **Inline Execution** — 本セッションで連続実行、チェックポイントごとにレビュー
   - 必要スキル: `superpowers:executing-plans`

どちらを採用するか指示があり次第、Task 1 から着手します。
