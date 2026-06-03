# AIチューターカリキュラム Sprint 2 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sprint 1 の認証 + 進捗 + 会話履歴の上に、(1) フェーズ毎タスク単位の課題提出、(2) Claude による同期 AI 採点 (score + feedback)、(3) pgvector + 多言語埋め込みによる RAG をチャットに統合する。

**Architecture:** バックエンドに `submissions` / `embeddings` の 2 テーブルを追加。提出 API は per-task UPSERT、進捗状態は全タスク提出で `submitted` に自動遷移。採点は提出ハンドラ内で同期実行し、Claude の `messages.create` に JSON 形式の応答を強制して score/feedback を取得。RAG は `fastembed` (`intfloat/multilingual-e5-small`, 384 次元) で curriculum + 個人の過去 chat + 提出物を埋め込み、`pgvector` の HNSW インデックスで top-K=4 を取得、Claude system prompt にコンテキストとして注入。フロントは PhaseChatView に提出パネルを追加し、課題ごとにテキストエリア + 採点結果バッジを表示。

**Tech Stack:**
- Backend 追加: `fastembed>=0.4.0` (ONNX 多言語埋め込み)、`numpy` (fastembed 依存)
- DB: PostgreSQL 16 + pgvector (Sprint 1 で拡張宣言済)、HNSW index
- AI: Claude `messages.create` の system prompt に `Respond in JSON ...` を含めて score/feedback 抽出（structured output, jose 不要）
- Frontend: 既存 stack のみ。新規依存なし

---

## スコープ境界

**含む（Sprint 2）：**
- `submissions` テーブル + Alembic migration
- `embeddings` テーブル + HNSW index (`vector(384)`, cosine)
- `POST /api/submissions` (1 タスクの提出、UPSERT、即時採点)
- `GET /api/submissions/{phase}` (フェーズ内全タスクの自分の提出一覧)
- 提出による進捗自動遷移：phase の全タスク提出済 → `progress.status = 'submitted'`
- Sprint 1 既存 `POST /api/progress/{phase}/complete`: `submitted` または `in_progress` から `completed` に遷移可
- RAG 検索サービス（埋め込み + 類似度検索）
- `POST /api/chat` 内部で RAG コンテキストを system prompt に注入
- `make seed-embeddings` ターゲット (curriculum 全文の初回埋め込み)
- フロント：`PhaseChatView` に課題提出パネル追加 (テキストエリア × 3 + 採点バッジ + AI フィードバック表示)

**含まない（後続スプリント）：**
- ファイル/スクリーンショットのアップロード → Sprint 3 候補
- 採点の非同期化（バックグラウンドジョブ）→ Sprint 4
- 採点リクエストの retry / rate limit → Sprint 4
- 管理者ダッシュボード → Sprint 3
- 採点履歴の audit log（提出 1 タスク = 最新 1 行のみ保持） → 後続
- RAG コンテキストの UI 表示（参照されたソース一覧） → 任意で Task 18 に含める検討
- 英語以外への多言語切替（UI は日本語固定）

---

## アーキテクチャ判断（明示）

| 判断 | 選択 | 理由 |
|---|---|---|
| 提出粒度 | (user_id, phase, task_no) UNIQUE | Sprint 2 では履歴は持たない。再提出は UPSERT |
| 採点トリガ | 提出ハンドラ内で同期 | 提出フローを単純化。Claude API はサブ秒〜数秒で応答 |
| Claude 構造化応答 | system prompt で JSON 形式を要求 → 応答テキストから JSON 抽出 | Anthropic SDK の structured output API 不要、シンプル |
| 採点失敗 | Claude エラー → submission は保存しつつ score=null / feedback=エラー文言 | 受講者は再採点で復旧可能（Sprint 3 で API 追加） |
| 進捗自動遷移 | `submissions` 全タスク (3 件) 揃ったら `progress.status = 'submitted'` | `complete` API は別 (自己宣言) |
| 埋め込みモデル | `fastembed` + `intfloat/multilingual-e5-small` (384 次元) | 追加 API キー不要、日本語精度十分、ONNX で軽量 |
| ベクタ DB | `pgvector` 拡張 + HNSW (cosine) | Sprint 1 で拡張宣言済、HNSW は最速の近似最近傍 |
| 埋め込み対象 | curriculum.skills + curriculum.tasks + 個人 chat_history + 個人 submissions | Per-user の文脈を含めることで応答品質向上 |
| 検索フィルタ | (user_id, phase) 内で類似度検索 | 個人別。ユーザ間のリーク防止 |
| top-K | 4 | カリキュラム部分 2 + 個人 chat 1 + 個人 submission 1 を狙ったハイブリッド |
| 埋め込みタイミング | curriculum: `make seed-embeddings` で 1 回 / chat: post-flight insert / submission: post-save insert | Chat と submission は永続化と同じトランザクションで実施 |
| Embedding 失敗時 | log + 検索結果に含めないだけ。検索処理は継続 | RAG はベストエフォート |

---

## ファイル構造（差分のみ）

```
edu/
├── docker-compose.yml                                # Modify: 不要 (Sprint 1 のままで OK)
├── Makefile                                          # Modify: seed-embeddings ターゲット追加
├── README.md                                         # Modify: Sprint 2 完了マーク
├── backend/
│   ├── pyproject.toml                                # Modify: fastembed + numpy 追加
│   ├── alembic/versions/<new>_sprint2.py             # Create: submissions, embeddings, index
│   ├── scripts/
│   │   └── seed_embeddings.py                        # Create: curriculum を埋め込んで DB 投入
│   ├── tests/
│   │   ├── test_models_sprint2.py                    # Create: 新規モデルの sanity
│   │   ├── test_embedding_client.py                  # Create
│   │   ├── test_rag_service.py                       # Create
│   │   ├── test_grading_service.py                   # Create
│   │   ├── test_submission_service.py                # Create
│   │   ├── test_api_submissions.py                   # Create
│   │   ├── test_api_chat.py                          # Modify: RAG コンテキスト注入の検証追加
│   │   └── test_api_progress.py                      # Modify: 全タスク提出での 'submitted' 遷移
│   └── app/
│       ├── models/
│       │   ├── submission.py                         # Create
│       │   └── embedding.py                          # Create
│       ├── models/__init__.py                        # Modify: 新モデル import
│       ├── core/
│       │   └── embedding_client.py                   # Create: fastembed ラッパー
│       ├── schemas/
│       │   ├── submission.py                         # Create
│       │   └── grading.py                            # Create
│       ├── services/
│       │   ├── embedding.py                          # Create: 埋め込み生成 + persist
│       │   ├── rag.py                                # Create: 検索 + context formatter
│       │   ├── grading.py                            # Create: Claude による採点
│       │   ├── submission.py                         # Create: UPSERT + 進捗連鎖
│       │   └── progress.py                           # Modify: mark_submitted_if_all_tasks_done() 追加
│       └── api/
│           ├── submissions.py                        # Create
│           └── chat.py                               # Modify: RAG コンテキスト注入
└── frontend/
    ├── src/
    │   ├── types/curriculum.ts                       # Modify: Submission, GradingResult 追加
    │   ├── lib/api.ts                                # Modify: submitTask, listSubmissions
    │   ├── stores/curriculum.ts                      # Modify: submissions マップ
    │   ├── views/PhaseChatView.vue                   # Modify: 課題提出パネル追加
    │   └── components/
    │       ├── SubmissionPanel.vue                   # Create
    │       └── TaskSubmissionCard.vue                # Create
```

---

## Task 1: バックエンド依存追加（fastembed）

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/pyproject.toml`

- [ ] **Step 1: `dependencies` に追加**

```toml
[project]
dependencies = [
    # 既存はそのまま、末尾に追加:
    "fastembed>=0.4.0",
    "numpy>=2.0.0",
    "pgvector>=0.3.0",  # SQLAlchemy 連携の Vector type 提供
]
```

- [ ] **Step 2: 依存解決**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
uv sync --extra dev
```

期待: fastembed, numpy, pgvector, それらの ONNX runtime 等が `Installed`。

- [ ] **Step 3: fastembed の動作確認**

```bash
ANTHROPIC_API_KEY=test JWT_SECRET_KEY=test uv run python -c "
from fastembed import TextEmbedding
m = TextEmbedding('intfloat/multilingual-e5-small')
v = list(m.embed(['Gitとは何ですか']))[0]
print('dim=', len(v), 'first3=', list(v[:3]))
"
```

期待: 初回はモデル DL (~110MB)、`dim= 384` と数値 3 つ。

- [ ] **Step 4: コミット**

```bash
cd /Volumes/Seagate3TB/projects/edu
git add backend/pyproject.toml backend/uv.lock
git commit -m "feat(backend): add fastembed + pgvector deps for Sprint 2 RAG"
```

---

## Task 2: SQLAlchemy モデル — Submission / Embedding

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/models/submission.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/models/embedding.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/models/__init__.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_models_sprint2.py`

- [ ] **Step 1: `app/models/submission.py` を作成**

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
    __table_args__ = (
        UniqueConstraint("user_id", "phase", "task_no", name="uq_submissions_user_phase_task"),
        CheckConstraint("phase BETWEEN 1 AND 4", name="ck_submissions_phase"),
        CheckConstraint("task_no BETWEEN 1 AND 5", name="ck_submissions_task_no"),
        CheckConstraint("score IS NULL OR score BETWEEN 0 AND 100", name="ck_submissions_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    phase: Mapped[int] = mapped_column(Integer)
    task_no: Mapped[int] = mapped_column(Integer)  # 1-indexed within phase
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

- [ ] **Step 2: `app/models/embedding.py` を作成**

```python
"""Embedding ORM model (pgvector-backed)."""

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

EMBEDDING_DIM = 384  # intfloat/multilingual-e5-small


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        Index(
            "ix_embeddings_user_phase",
            "user_id",
            "phase",
        ),
        Index(
            "ix_embeddings_vector_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # user_id NULL means "global / curriculum" content
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(50))
    # e.g. "phase:1:skill:0" / chat_history.id / submission.id
    source_ref: Mapped[str] = mapped_column(String(200))
    phase: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

- [ ] **Step 3: `app/models/__init__.py` に追加**

```python
"""Model registry. Import all models here so SQLAlchemy metadata sees them."""

from app.models.chat_history import ChatHistory  # noqa: F401
from app.models.embedding import Embedding  # noqa: F401
from app.models.progress import Progress, ProgressStatus  # noqa: F401
from app.models.submission import Submission  # noqa: F401
from app.models.user import User  # noqa: F401
```

- [ ] **Step 4: `tests/test_models_sprint2.py` を作成**

```python
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.embedding import EMBEDDING_DIM, Embedding
from app.models.submission import Submission
from app.models.user import User


async def _make_user(db, email: str = "alice@example.com") -> User:
    u = User(email=email, name="A", password_hash=hash_password("password123"))
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_submission_round_trip(db_session):
    user = await _make_user(db_session)
    db_session.add(
        Submission(
            user_id=user.id,
            phase=1,
            task_no=1,
            content="Hello",
            ai_feedback="OK",
            score=85,
        )
    )
    await db_session.commit()

    row = (await db_session.execute(select(Submission))).scalar_one()
    assert row.user_id == user.id
    assert row.score == 85


@pytest.mark.asyncio
async def test_submission_unique_per_user_phase_task(db_session):
    user = await _make_user(db_session)
    db_session.add(Submission(user_id=user.id, phase=1, task_no=1, content="A"))
    await db_session.commit()

    db_session.add(Submission(user_id=user.id, phase=1, task_no=1, content="B"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_submission_score_range_constraint(db_session):
    user = await _make_user(db_session)
    db_session.add(Submission(user_id=user.id, phase=1, task_no=1, content="C", score=150))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_embedding_stores_vector(db_session):
    vec = [0.1] * EMBEDDING_DIM
    db_session.add(
        Embedding(
            user_id=None,
            source_type="curriculum_skill",
            source_ref="phase:1:skill:0",
            phase=1,
            content="Git / GitHub",
            embedding=vec,
        )
    )
    await db_session.commit()

    row = (await db_session.execute(select(Embedding))).scalar_one()
    assert len(row.embedding) == EMBEDDING_DIM
    assert pytest.approx(row.embedding[0]) == 0.1
```

- [ ] **Step 5: モデル sanity 確認は次タスクで migration 後に通すため、ここでは作成のみ**

- [ ] **Step 6: コミット**

```bash
git add backend/app/models/submission.py backend/app/models/embedding.py backend/app/models/__init__.py backend/tests/test_models_sprint2.py
git commit -m "feat(backend): add Submission and Embedding (pgvector) ORM models"
```

---

## Task 3: Alembic マイグレーション (Sprint 2)

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/alembic/versions/<auto>_sprint2.py`

- [ ] **Step 1: マイグレーション生成**

```bash
cd /Volumes/Seagate3TB/projects/edu/backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
ANTHROPIC_API_KEY=test JWT_SECRET_KEY=test \
uv run alembic revision --autogenerate -m "sprint2 submissions and embeddings"
```

期待: `alembic/versions/<date>_<rev>_sprint2_submissions_and_embeddings.py` が生成され、`submissions` テーブル / `embeddings` テーブル / 3 つの index (`ix_submissions_user_id`, `ix_embeddings_user_phase`, `ix_embeddings_vector_hnsw`) が含まれる。

- [ ] **Step 2: 生成されたマイグレーションを検査**

期待される `upgrade()` の構造（autogenerate により細部は異なる場合あり）:

```python
def upgrade() -> None:
    # submissions
    op.create_table(
        "submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.Integer(), nullable=False),
        sa.Column("task_no", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("phase BETWEEN 1 AND 4", name="ck_submissions_phase"),
        sa.CheckConstraint("task_no BETWEEN 1 AND 5", name="ck_submissions_task_no"),
        sa.CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 100", name="ck_submissions_score"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "phase", "task_no", name="uq_submissions_user_phase_task"),
    )
    op.create_index(op.f("ix_submissions_user_id"), "submissions", ["user_id"])

    # embeddings
    op.create_table(
        "embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_ref", sa.String(length=200), nullable=False),
        sa.Column("phase", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_embeddings_user_phase", "embeddings", ["user_id", "phase"])
    op.create_index(
        "ix_embeddings_vector_hnsw",
        "embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_embeddings_vector_hnsw", table_name="embeddings")
    op.drop_index("ix_embeddings_user_phase", table_name="embeddings")
    op.drop_table("embeddings")
    op.drop_index(op.f("ix_submissions_user_id"), table_name="submissions")
    op.drop_table("submissions")
```

`Vector(384)` の import が必要なので、ファイル冒頭に `from pgvector.sqlalchemy import Vector` を追記（autogenerate が拾えないことが多い）。

- [ ] **Step 3: 適用**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor \
ANTHROPIC_API_KEY=test JWT_SECRET_KEY=test \
uv run alembic upgrade head

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tutor_test \
ANTHROPIC_API_KEY=test JWT_SECRET_KEY=test \
uv run alembic upgrade head
```

期待: 双方 OK。`\dt` で 6 テーブル (alembic_version + users + progress + chat_history + submissions + embeddings)。

- [ ] **Step 4: モデルテスト実行**

```bash
uv run pytest tests/test_models_sprint2.py -v
```

期待: 4 テスト PASS。

- [ ] **Step 5: コミット**

```bash
git add backend/alembic/versions
git commit -m "feat(backend): add Alembic migration for submissions and embeddings"
```

---

## Task 4: Embedding クライアント (fastembed ラッパー)

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/core/embedding_client.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_embedding_client.py`

- [ ] **Step 1: テスト先行**

```python
"""tests/test_embedding_client.py"""
import pytest

from app.core.embedding_client import EmbeddingClient, EMBEDDING_DIM


@pytest.mark.asyncio
async def test_embed_returns_correct_dim():
    client = EmbeddingClient()
    vectors = await client.embed(["Gitとは何ですか"])
    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIM


@pytest.mark.asyncio
async def test_embed_batch():
    client = EmbeddingClient()
    vectors = await client.embed(["Gitとは", "Pythonとは", "Vue.jsとは"])
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == EMBEDDING_DIM


@pytest.mark.asyncio
async def test_embed_empty_input_returns_empty():
    client = EmbeddingClient()
    vectors = await client.embed([])
    assert vectors == []


@pytest.mark.asyncio
async def test_similar_queries_have_higher_cosine_similarity():
    import numpy as np

    client = EmbeddingClient()
    vecs = await client.embed(
        ["Gitでブランチを切る方法", "Gitのブランチ作成手順", "Pythonの内包表記"]
    )
    a = np.array(vecs[0])
    b = np.array(vecs[1])
    c = np.array(vecs[2])

    sim_ab = a @ b / (np.linalg.norm(a) * np.linalg.norm(b))
    sim_ac = a @ c / (np.linalg.norm(a) * np.linalg.norm(c))
    assert sim_ab > sim_ac
```

- [ ] **Step 2: テスト実行（失敗確認）**

```bash
uv run pytest tests/test_embedding_client.py -v
```

期待: ImportError。

- [ ] **Step 3: `app/core/embedding_client.py` を作成**

```python
"""Embedding client wrapping fastembed multilingual model.

The TextEmbedding constructor is heavy (downloads ONNX model ~110MB on
first use), so we lazy-init a process-wide singleton. Embedding is
CPU-bound; we wrap with asyncio.to_thread to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
from threading import Lock

from fastembed import TextEmbedding

EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
EMBEDDING_DIM = 384

_model: TextEmbedding | None = None
_init_lock = Lock()


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        with _init_lock:
            if _model is None:
                _model = TextEmbedding(EMBEDDING_MODEL)
    return _model


class EmbeddingClient:
    """Thin async facade around fastembed."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # fastembed's embed() returns a generator of numpy arrays.
        # Run in a thread to avoid blocking the event loop.
        def _do() -> list[list[float]]:
            model = _get_model()
            return [vec.tolist() for vec in model.embed(texts)]

        return await asyncio.to_thread(_do)


def get_embedding_client() -> EmbeddingClient:
    return EmbeddingClient()
```

- [ ] **Step 4: テスト PASS 確認**

```bash
uv run pytest tests/test_embedding_client.py -v
```

期待: 4 テスト PASS（初回はモデル DL で数十秒）。

- [ ] **Step 5: コミット**

```bash
git add backend/app/core/embedding_client.py backend/tests/test_embedding_client.py
git commit -m "feat(backend): add EmbeddingClient (fastembed multilingual-e5-small)"
```

---

## Task 5: Embedding 永続化サービス

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/services/embedding.py`

採点 / RAG から呼ぶ薄いラッパー。テストは Task 6 と統合。

- [ ] **Step 1: 作成**

```python
"""Embedding write helpers."""

import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding_client import EmbeddingClient
from app.models.embedding import Embedding


async def upsert_embeddings(
    db: AsyncSession,
    client: EmbeddingClient,
    *,
    user_id: uuid.UUID | None,
    items: list[tuple[str, str, int | None, str]],
) -> None:
    """Embed a batch of texts and insert into embeddings.

    items: list of (source_type, source_ref, phase, content) tuples.

    For a given (source_type, source_ref), pre-existing rows are removed
    before insertion (idempotent re-embedding).
    """
    if not items:
        return

    refs = [(t, r) for t, r, _, _ in items]
    if refs:
        for source_type, source_ref in refs:
            await db.execute(
                delete(Embedding).where(
                    Embedding.source_type == source_type,
                    Embedding.source_ref == source_ref,
                )
            )

    contents = [c for _, _, _, c in items]
    vectors = await client.embed(contents)

    for (source_type, source_ref, phase, content), vec in zip(items, vectors, strict=True):
        db.add(
            Embedding(
                user_id=user_id,
                source_type=source_type,
                source_ref=source_ref,
                phase=phase,
                content=content,
                embedding=vec,
            )
        )
    await db.flush()
```

- [ ] **Step 2: コミット**

```bash
git add backend/app/services/embedding.py
git commit -m "feat(backend): add upsert_embeddings helper for persistent vectorization"
```

---

## Task 6: RAG 検索サービス

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/services/rag.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_rag_service.py`

- [ ] **Step 1: テスト先行**

```python
"""tests/test_rag_service.py"""
import uuid

import pytest

from app.core.embedding_client import EmbeddingClient
from app.core.security import hash_password
from app.models.user import User
from app.services.embedding import upsert_embeddings
from app.services.rag import format_context, search_context


async def _make_user(db, email="alice@example.com") -> User:
    u = User(email=email, name="A", password_hash=hash_password("password123"))
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_search_returns_topk_per_phase(db_session):
    user = await _make_user(db_session)
    client = EmbeddingClient()

    # global curriculum-style entries
    await upsert_embeddings(
        db_session,
        client,
        user_id=None,
        items=[
            ("curriculum_skill", "phase:1:skill:0", 1, "Git / GitHub の基礎"),
            ("curriculum_skill", "phase:1:skill:1", 1, "VSCode 拡張機能"),
            ("curriculum_skill", "phase:2:skill:0", 2, "Cursor IDE と Copilot"),
        ],
    )
    # user-specific chat entry
    await upsert_embeddings(
        db_session,
        client,
        user_id=user.id,
        items=[
            ("chat_message", "msg-1", 1, "git branchの使い方を教えてください"),
        ],
    )
    await db_session.commit()

    results = await search_context(
        db_session, client, user_id=user.id, phase=1, query="Gitのブランチを切る", top_k=4
    )
    contents = [r.content for r in results]
    # Phase 1 のものが優先されるはず
    assert any("Git" in c for c in contents)
    # Phase 2 のものは含まれない
    assert not any("Cursor" in c for c in contents)


@pytest.mark.asyncio
async def test_format_context_produces_text(db_session):
    from app.services.rag import RagHit

    hits = [
        RagHit(source_type="curriculum_skill", content="Git / GitHub", score=0.9),
        RagHit(source_type="chat_message", content="昨日はpython基礎をやりました", score=0.7),
    ]
    text = format_context(hits)
    assert "Git / GitHub" in text
    assert "python基礎" in text
    assert "参考" in text  # Japanese label


@pytest.mark.asyncio
async def test_search_returns_empty_when_no_data(db_session):
    user = await _make_user(db_session)
    client = EmbeddingClient()
    results = await search_context(
        db_session, client, user_id=user.id, phase=1, query="anything", top_k=4
    )
    assert results == []
```

- [ ] **Step 2: 失敗確認**

```bash
uv run pytest tests/test_rag_service.py -v
```

期待: `ModuleNotFoundError`.

- [ ] **Step 3: `app/services/rag.py` を作成**

```python
"""RAG search + context formatter."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embedding_client import EmbeddingClient
from app.models.embedding import Embedding


@dataclass(frozen=True)
class RagHit:
    source_type: str
    content: str
    score: float


async def search_context(
    db: AsyncSession,
    client: EmbeddingClient,
    *,
    user_id: uuid.UUID,
    phase: int,
    query: str,
    top_k: int = 4,
) -> list[RagHit]:
    """Embed the query and search embeddings filtered by (user OR global) and phase."""
    if not query.strip():
        return []
    vectors = await client.embed([query])
    qvec = vectors[0]

    # Filter: rows that are either global (user_id IS NULL) or for this user.
    # Within those, prefer the same phase.
    stmt = (
        select(
            Embedding.source_type,
            Embedding.content,
            Embedding.embedding.cosine_distance(qvec).label("distance"),
        )
        .where(
            or_(Embedding.user_id.is_(None), Embedding.user_id == user_id),
            or_(Embedding.phase == phase, Embedding.phase.is_(None)),
        )
        .order_by("distance")
        .limit(top_k)
    )
    rows = (await db.execute(stmt)).all()
    return [
        RagHit(source_type=r.source_type, content=r.content, score=1.0 - float(r.distance))
        for r in rows
    ]


def format_context(hits: list[RagHit]) -> str:
    """Render hits as a system-prompt snippet."""
    if not hits:
        return ""
    lines = ["以下はこの受講者の学習履歴・カリキュラム内容からの参考情報です:", ""]
    for i, h in enumerate(hits, 1):
        label = {
            "curriculum_skill": "カリキュラム(スキル)",
            "curriculum_task": "カリキュラム(課題)",
            "chat_message": "過去のやり取り",
            "submission": "本人の提出物",
        }.get(h.source_type, h.source_type)
        lines.append(f"[{i}] ({label}, 類似度={h.score:.2f}) {h.content}")
    lines.append("")
    lines.append("関連がある場合のみ参考にし、無関係な情報は無視してください。")
    return "\n".join(lines)
```

- [ ] **Step 4: テスト実行**

```bash
uv run pytest tests/test_rag_service.py -v
```

期待: 3 テスト PASS（初回はモデル DL）。

- [ ] **Step 5: コミット**

```bash
git add backend/app/services/rag.py backend/tests/test_rag_service.py
git commit -m "feat(backend): add RAG search_context + format_context (pgvector cosine)"
```

---

## Task 7: 採点サービス (Claude による JSON 出力)

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/services/grading.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/schemas/grading.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_grading_service.py`

- [ ] **Step 1: `app/schemas/grading.py` を作成**

```python
"""Grading DTOs."""

from pydantic import BaseModel, Field


class GradingResult(BaseModel):
    score: int = Field(ge=0, le=100)
    feedback: str
```

- [ ] **Step 2: テスト先行**

```python
"""tests/test_grading_service.py"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.claude_client import ClaudeClient
from app.services.grading import GradingError, grade_submission


def _fake(reply: str) -> ClaudeClient:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text=reply)])
    )
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")


@pytest.mark.asyncio
async def test_grade_parses_json_object():
    claude = _fake('{"score": 85, "feedback": "良い回答です。"}')
    result = await grade_submission(
        claude=claude, task_description="Gitとは", content="Gitはバージョン管理"
    )
    assert result.score == 85
    assert "良い" in result.feedback


@pytest.mark.asyncio
async def test_grade_handles_wrapped_json():
    """Claude が説明文に JSON を埋め込んだ場合も抽出できる。"""
    text = "評価結果は以下です:\n{\"score\": 60, \"feedback\": \"もう少し具体例を\"}\nです。"
    claude = _fake(text)
    result = await grade_submission(
        claude=claude, task_description="x", content="y"
    )
    assert result.score == 60


@pytest.mark.asyncio
async def test_grade_clamps_out_of_range_score():
    claude = _fake('{"score": 150, "feedback": "x"}')
    result = await grade_submission(
        claude=claude, task_description="x", content="y"
    )
    assert result.score == 100


@pytest.mark.asyncio
async def test_grade_raises_on_unparseable():
    claude = _fake("これは JSON ではありません")
    with pytest.raises(GradingError):
        await grade_submission(claude=claude, task_description="x", content="y")
```

- [ ] **Step 3: 失敗確認**

```bash
uv run pytest tests/test_grading_service.py -v
```

- [ ] **Step 4: `app/services/grading.py` を作成**

```python
"""Submission grading via Claude with JSON output."""

import json
import re

from app.core.claude_client import ClaudeClient
from app.schemas.grading import GradingResult


class GradingError(Exception):
    pass


SYSTEM_PROMPT = (
    "あなたは AI 駆動型開発カリキュラムの教育評価者です。\n"
    "受講者の提出物を採点します。以下を守ってください:\n"
    "- 課題の意図に沿っているか、論理性、具体性で評価\n"
    "- 0 〜 100 の整数スコアを必ず付ける\n"
    "- 日本語 2〜4 文の建設的フィードバックを返す\n"
    "- 出力は次の JSON のみ。前置きや後置きを書かない:\n"
    '  {"score": <integer 0-100>, "feedback": "<日本語のコメント>"}'
)


def _extract_json(text: str) -> dict:
    """Find the first {...} block and parse it."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise GradingError(f"No JSON object in response: {text[:200]!r}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise GradingError(f"Invalid JSON: {e}: {text[:200]!r}") from e


async def grade_submission(
    *, claude: ClaudeClient, task_description: str, content: str
) -> GradingResult:
    user_message = (
        f"課題: {task_description}\n\n"
        f"受講者の提出:\n{content}\n\n"
        "上記を採点し、指定された JSON のみで返答してください。"
    )
    reply = await claude.complete(
        system_prompt=SYSTEM_PROMPT,
        history=[{"role": "user", "content": user_message}],
    )

    obj = _extract_json(reply)
    try:
        score_raw = int(obj["score"])
        feedback = str(obj["feedback"])
    except (KeyError, ValueError, TypeError) as e:
        raise GradingError(f"missing or invalid fields: {obj!r}") from e

    score = max(0, min(100, score_raw))
    return GradingResult(score=score, feedback=feedback)
```

- [ ] **Step 5: テスト PASS 確認**

```bash
uv run pytest tests/test_grading_service.py -v
```

期待: 4 テスト PASS。

- [ ] **Step 6: コミット**

```bash
git add backend/app/schemas/grading.py backend/app/services/grading.py backend/tests/test_grading_service.py
git commit -m "feat(backend): add Claude-backed grading service with JSON output extraction"
```

---

## Task 8: 提出サービス + 進捗連鎖

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/services/submission.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/services/progress.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_submission_service.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_progress_service.py` (新規ケース1件)

- [ ] **Step 1: `app/services/progress.py` に補助関数を追加**

```python
# ... 既存 import に追加:
from app.models.submission import Submission

# 既存関数末尾に追加:

async def maybe_mark_submitted(
    db: AsyncSession, user_id: uuid.UUID, phase: int, required_task_count: int
) -> Progress | None:
    """Promote in_progress -> submitted iff all tasks in phase have a submission."""
    progress = await _get(db, user_id, phase)
    if progress is None or progress.status != ProgressStatus.IN_PROGRESS.value:
        return None
    cnt = (
        await db.execute(
            select(Submission.task_no).where(
                Submission.user_id == user_id, Submission.phase == phase
            )
        )
    ).all()
    if len({row.task_no for row in cnt}) < required_task_count:
        return None
    progress.status = ProgressStatus.SUBMITTED.value
    await db.flush()
    return progress
```

- [ ] **Step 2: `app/services/submission.py` を作成**

```python
"""Submission domain service."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.claude_client import ClaudeClient
from app.data.curriculum import CURRICULUM
from app.models.submission import Submission
from app.schemas.grading import GradingResult
from app.services.grading import GradingError, grade_submission
from app.services.progress import maybe_mark_submitted


class SubmissionPhaseInvalidError(Exception):
    pass


class SubmissionTaskInvalidError(Exception):
    pass


async def upsert_and_grade(
    *,
    db: AsyncSession,
    claude: ClaudeClient,
    user_id: uuid.UUID,
    phase: int,
    task_no: int,
    content: str,
) -> Submission:
    if phase not in CURRICULUM:
        raise SubmissionPhaseInvalidError(phase)
    tasks = CURRICULUM[phase]["tasks"]
    if task_no < 1 or task_no > len(tasks):
        raise SubmissionTaskInvalidError(task_no)
    task_description = tasks[task_no - 1]

    existing = (
        await db.execute(
            select(Submission).where(
                Submission.user_id == user_id,
                Submission.phase == phase,
                Submission.task_no == task_no,
            )
        )
    ).scalar_one_or_none()

    now = datetime.now(UTC)
    if existing is None:
        row = Submission(
            user_id=user_id,
            phase=phase,
            task_no=task_no,
            content=content,
            submitted_at=now,
        )
        db.add(row)
    else:
        row = existing
        row.content = content
        row.submitted_at = now
        row.ai_feedback = None
        row.score = None
        row.graded_at = None

    await db.flush()

    # Grade synchronously; failures persist a "graded with error" record.
    try:
        result: GradingResult = await grade_submission(
            claude=claude, task_description=task_description, content=content
        )
        row.score = result.score
        row.ai_feedback = result.feedback
        row.graded_at = now
    except GradingError as e:
        row.ai_feedback = f"採点エラー: {e}"
        row.score = None
        row.graded_at = now

    # Promote progress if all tasks submitted
    await maybe_mark_submitted(db, user_id, phase, required_task_count=len(tasks))

    await db.commit()
    return row


async def list_user_submissions(
    db: AsyncSession, user_id: uuid.UUID, phase: int
) -> list[Submission]:
    rows = (
        await db.execute(
            select(Submission)
            .where(Submission.user_id == user_id, Submission.phase == phase)
            .order_by(Submission.task_no)
        )
    ).scalars().all()
    return list(rows)
```

- [ ] **Step 3: テスト**

```python
"""tests/test_submission_service.py"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.claude_client import ClaudeClient
from app.core.security import hash_password
from app.models.progress import ProgressStatus
from app.models.user import User
from app.services.progress import initialize_progress, list_progress
from app.services.submission import (
    SubmissionTaskInvalidError,
    list_user_submissions,
    upsert_and_grade,
)


async def _user(db) -> User:
    u = User(email="alice@example.com", name="A", password_hash=hash_password("password123"))
    db.add(u)
    await db.flush()
    await initialize_progress(db, u.id)
    await db.commit()
    return u


def _fake(reply: str) -> ClaudeClient:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text=reply)])
    )
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")


@pytest.mark.asyncio
async def test_upsert_creates_and_grades(db_session):
    user = await _user(db_session)
    claude = _fake('{"score": 80, "feedback": "良い"}')

    row = await upsert_and_grade(
        db=db_session, claude=claude, user_id=user.id, phase=1, task_no=1,
        content="Gitでブランチ切ってPRしました",
    )

    assert row.score == 80
    assert "良い" in row.ai_feedback
    assert row.graded_at is not None


@pytest.mark.asyncio
async def test_upsert_updates_existing(db_session):
    user = await _user(db_session)
    claude = _fake('{"score": 70, "feedback": "一回目"}')
    await upsert_and_grade(
        db=db_session, claude=claude, user_id=user.id, phase=1, task_no=1, content="初回",
    )

    claude2 = _fake('{"score": 90, "feedback": "二回目"}')
    row = await upsert_and_grade(
        db=db_session, claude=claude2, user_id=user.id, phase=1, task_no=1, content="改善版",
    )

    assert row.content == "改善版"
    assert row.score == 90

    listed = await list_user_submissions(db_session, user.id, 1)
    assert len(listed) == 1  # UPSERT, no duplicate


@pytest.mark.asyncio
async def test_all_tasks_submitted_promotes_progress(db_session):
    user = await _user(db_session)
    claude = _fake('{"score": 75, "feedback": "OK"}')
    for tno in [1, 2, 3]:
        await upsert_and_grade(
            db=db_session, claude=_fake('{"score":80,"feedback":"x"}'),
            user_id=user.id, phase=1, task_no=tno, content=f"task {tno}",
        )

    rows = await list_progress(db_session, user.id)
    phase1 = next(r for r in rows if r.phase == 1)
    assert phase1.status == ProgressStatus.SUBMITTED.value


@pytest.mark.asyncio
async def test_partial_submission_keeps_in_progress(db_session):
    user = await _user(db_session)
    await upsert_and_grade(
        db=db_session, claude=_fake('{"score":80,"feedback":"x"}'),
        user_id=user.id, phase=1, task_no=1, content="task 1",
    )

    rows = await list_progress(db_session, user.id)
    phase1 = next(r for r in rows if r.phase == 1)
    assert phase1.status == ProgressStatus.IN_PROGRESS.value


@pytest.mark.asyncio
async def test_invalid_task_no_raises(db_session):
    user = await _user(db_session)
    with pytest.raises(SubmissionTaskInvalidError):
        await upsert_and_grade(
            db=db_session, claude=_fake('{"score":80,"feedback":"x"}'),
            user_id=user.id, phase=1, task_no=99, content="x",
        )


@pytest.mark.asyncio
async def test_grading_failure_stores_error_message(db_session):
    user = await _user(db_session)
    claude = _fake("これは JSON ではありません")  # parse failure
    row = await upsert_and_grade(
        db=db_session, claude=claude, user_id=user.id, phase=1, task_no=1,
        content="提出内容",
    )
    assert row.score is None
    assert row.ai_feedback.startswith("採点エラー")
```

- [ ] **Step 4: 全テスト実行**

```bash
uv run pytest tests/test_submission_service.py -v
```

期待: 6 テスト PASS。

- [ ] **Step 5: 既存 test_progress_service.py は影響なしの確認**

```bash
uv run pytest tests/test_progress_service.py -v
```

期待: 9 テスト PASS。

- [ ] **Step 6: コミット**

```bash
git add backend/app/services/submission.py backend/app/services/progress.py backend/tests/test_submission_service.py
git commit -m "feat(backend): add submission service with sync grading and progress promotion"
```

---

## Task 9: 提出 API

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/schemas/submission.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/app/api/submissions.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/main.py`
- Create: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_api_submissions.py`

- [ ] **Step 1: `app/schemas/submission.py` を作成**

```python
"""Submission API DTOs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SubmissionCreate(BaseModel):
    phase: int = Field(ge=1, le=4)
    task_no: int = Field(ge=1, le=5)
    content: str = Field(min_length=1, max_length=10000)


class SubmissionOut(BaseModel):
    id: uuid.UUID
    phase: int
    task_no: int
    content: str
    ai_feedback: str | None
    score: int | None
    submitted_at: datetime
    graded_at: datetime | None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: `app/api/submissions.py` を作成**

```python
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.claude_client import ClaudeClient, get_claude_client
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.submission import SubmissionCreate, SubmissionOut
from app.services.progress import is_phase_unlocked
from app.services.submission import (
    SubmissionPhaseInvalidError,
    SubmissionTaskInvalidError,
    list_user_submissions,
    upsert_and_grade,
)

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    claude: ClaudeClient = Depends(get_claude_client),
    db: AsyncSession = Depends(get_db),
) -> SubmissionOut:
    if not await is_phase_unlocked(db, current_user.id, payload.phase):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"phase {payload.phase} is locked",
        )
    try:
        row = await upsert_and_grade(
            db=db,
            claude=claude,
            user_id=current_user.id,
            phase=payload.phase,
            task_no=payload.task_no,
            content=payload.content,
        )
    except SubmissionPhaseInvalidError as e:
        raise HTTPException(status_code=404, detail=f"phase {e.args[0]} not found") from e
    except SubmissionTaskInvalidError as e:
        raise HTTPException(status_code=422, detail=f"task {e.args[0]} not found") from e

    return SubmissionOut.model_validate(row)


@router.get("/{phase}", response_model=list[SubmissionOut])
async def list_my_submissions(
    phase: int = Path(ge=1, le=4),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SubmissionOut]:
    if not await is_phase_unlocked(db, current_user.id, phase):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"phase {phase} is locked"
        )
    rows = await list_user_submissions(db, current_user.id, phase)
    return [SubmissionOut.model_validate(r) for r in rows]
```

- [ ] **Step 3: `app/main.py` に追加**

```python
from app.api import auth, curriculum, health, progress, submissions
# ...
app.include_router(submissions.router)
```

- [ ] **Step 4: テスト**

```python
"""tests/test_api_submissions.py"""
from unittest.mock import AsyncMock, MagicMock

from app.core.claude_client import ClaudeClient, get_claude_client


def _fake(reply: str) -> ClaudeClient:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text=reply)])
    )
    return ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")


def test_submit_requires_auth(client, db_session):
    response = client.post(
        "/api/submissions", json={"phase": 1, "task_no": 1, "content": "x"}
    )
    assert response.status_code == 401


def test_submit_creates_and_returns_grade(auth_client):
    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake('{"score":88,"feedback":"good"}')
    try:
        response = auth_client.post(
            "/api/submissions",
            json={"phase": 1, "task_no": 1, "content": "Gitでブランチ切りました"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["score"] == 88
        assert "good" in body["ai_feedback"]
    finally:
        app.dependency_overrides.clear()


def test_submit_locked_phase_returns_403(auth_client):
    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake('{"score":80,"feedback":"x"}')
    try:
        response = auth_client.post(
            "/api/submissions", json={"phase": 2, "task_no": 1, "content": "x"}
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_submit_invalid_task_returns_422(auth_client):
    from app.main import app
    app.dependency_overrides[get_claude_client] = lambda: _fake('{"score":80,"feedback":"x"}')
    try:
        response = auth_client.post(
            "/api/submissions", json={"phase": 1, "task_no": 99, "content": "x"}
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_list_returns_submissions(auth_client):
    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake('{"score":80,"feedback":"x"}')
    try:
        auth_client.post("/api/submissions", json={"phase": 1, "task_no": 1, "content": "A"})
        auth_client.post("/api/submissions", json={"phase": 1, "task_no": 2, "content": "B"})
        response = auth_client.get("/api/submissions/1")
        assert response.status_code == 200
        data = response.json()
        assert [r["task_no"] for r in data] == [1, 2]
    finally:
        app.dependency_overrides.clear()


def test_list_requires_auth(client, db_session):
    response = client.get("/api/submissions/1")
    assert response.status_code == 401


def test_all_submissions_promote_progress_to_submitted(auth_client):
    from app.main import app

    app.dependency_overrides[get_claude_client] = lambda: _fake('{"score":80,"feedback":"x"}')
    try:
        for tno in (1, 2, 3):
            auth_client.post(
                "/api/submissions",
                json={"phase": 1, "task_no": tno, "content": f"task {tno}"},
            )
        # Verify via /api/progress
        resp = auth_client.get("/api/progress")
        phases = {r["phase"]: r["status"] for r in resp.json()}
        assert phases[1] == "submitted"
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 5: 実行**

```bash
uv run pytest tests/test_api_submissions.py -v
```

期待: 7 テスト PASS。

- [ ] **Step 6: コミット**

```bash
git add backend/app/schemas/submission.py backend/app/api/submissions.py backend/app/main.py backend/tests/test_api_submissions.py
git commit -m "feat(backend): add POST /api/submissions + GET /api/submissions/{phase}"
```

---

## Task 10: Embedding seed スクリプト

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/backend/scripts/seed_embeddings.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/Makefile`

- [ ] **Step 1: `backend/scripts/seed_embeddings.py` を作成**

```python
"""Seed curriculum content into embeddings table.

Run via `make seed-embeddings` (or directly with uv run python).

Idempotent: re-runs delete and re-insert rows with the same source_ref.
"""

import asyncio

from app.core.embedding_client import EmbeddingClient
from app.data.curriculum import CURRICULUM
from app.db.session import SessionLocal
from app.services.embedding import upsert_embeddings


async def main() -> None:
    client = EmbeddingClient()
    items: list[tuple[str, str, int | None, str]] = []
    for phase_no, phase in CURRICULUM.items():
        for i, skill in enumerate(phase["skills"]):
            items.append(("curriculum_skill", f"phase:{phase_no}:skill:{i}", phase_no, skill))
        for i, task in enumerate(phase["tasks"]):
            items.append(("curriculum_task", f"phase:{phase_no}:task:{i}", phase_no, task))

    async with SessionLocal() as db:
        await upsert_embeddings(db, client, user_id=None, items=items)
        await db.commit()

    print(f"Seeded {len(items)} embedding rows.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: `Makefile` に追加**

```makefile
.PHONY: dev test test-backend test-frontend lint clean migrate revision db-shell seed-embeddings

# 既存ターゲットの下に:

seed-embeddings:
	docker compose up -d postgres
	cd backend && uv run python scripts/seed_embeddings.py
```

- [ ] **Step 3: 実行確認**

```bash
cd /Volumes/Seagate3TB/projects/edu
make seed-embeddings
```

期待: `Seeded 28 embedding rows.` (4 phase × (4 skills + 3 tasks) = 28)。

- [ ] **Step 4: コミット**

```bash
git add backend/scripts/seed_embeddings.py Makefile
git commit -m "feat(backend): add seed-embeddings script for curriculum content"
```

---

## Task 11: Chat ハンドラに RAG コンテキスト注入

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/app/api/chat.py`
- Modify: `/Volumes/Seagate3TB/projects/edu/backend/tests/test_api_chat.py` (新規 1 件)

- [ ] **Step 1: `app/api/chat.py` を修正**

`chat()` ハンドラの中、`reply = await claude.complete(...)` の前を以下に書き換える:

```python
# 既存 import に追加:
from app.core.embedding_client import EmbeddingClient, get_embedding_client
from app.services import embedding as embedding_service
from app.services.rag import format_context, search_context

# ハンドラのシグネチャに追加: embedder: EmbeddingClient = Depends(get_embedding_client)

# Claude 呼び出し直前:
hits = await search_context(
    store.db,
    embedder,
    user_id=current_user.id,
    phase=request.phase,
    query=request.message,
    top_k=4,
)
context_block = format_context(hits)
system_prompt = CURRICULUM[request.phase]["system_prompt"]
if context_block:
    system_prompt = system_prompt + "\n\n" + context_block

# (既存) claude.complete(system_prompt=system_prompt, history=next_history) に変更

# 応答永続化の後、user message と assistant reply を embeddings にも追加:
await embedding_service.upsert_embeddings(
    store.db,
    embedder,
    user_id=current_user.id,
    items=[
        (
            "chat_message",
            f"user:{current_user.id}:phase:{request.phase}:{datetime.now(UTC).isoformat()}:u",
            request.phase,
            request.message,
        ),
        (
            "chat_message",
            f"user:{current_user.id}:phase:{request.phase}:{datetime.now(UTC).isoformat()}:a",
            request.phase,
            reply,
        ),
    ],
)
```

ファイル全体は import 整理込みで以下のようになる:

```python
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.core.claude_client import ClaudeClient, get_claude_client
from app.core.deps import get_current_user
from app.core.embedding_client import EmbeddingClient, get_embedding_client
from app.data.curriculum import CURRICULUM
from app.memory.chat_store import SqlChatStore, get_chat_store
from app.models.user import User
from app.schemas.chat import ChatMessage, ChatRequest, ChatResponse
from app.services import embedding as embedding_service
from app.services.progress import is_phase_unlocked
from app.services.rag import format_context, search_context

router = APIRouter(prefix="/api", tags=["chat"])


async def _ensure_phase_accessible(
    user: User, phase: int, store: SqlChatStore
) -> None:
    if phase not in CURRICULUM:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"phase {phase} not found"
        )
    unlocked = await is_phase_unlocked(store.db, user.id, phase)
    if not unlocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"phase {phase} is locked"
        )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    claude: ClaudeClient = Depends(get_claude_client),
    store: SqlChatStore = Depends(get_chat_store),
    embedder: EmbeddingClient = Depends(get_embedding_client),
) -> ChatResponse:
    await _ensure_phase_accessible(current_user, request.phase, store)

    history = await store.get_history(current_user.id, request.phase)
    next_history = history + [{"role": "user", "content": request.message}]

    # RAG: retrieve top-K relevant context
    hits = await search_context(
        store.db,
        embedder,
        user_id=current_user.id,
        phase=request.phase,
        query=request.message,
        top_k=4,
    )
    system_prompt = CURRICULUM[request.phase]["system_prompt"]
    context_block = format_context(hits)
    if context_block:
        system_prompt = system_prompt + "\n\n" + context_block

    try:
        reply = await claude.complete(system_prompt=system_prompt, history=next_history)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="upstream LLM error"
        ) from e

    await store.append(current_user.id, request.phase, "user", request.message)
    await store.append(current_user.id, request.phase, "assistant", reply)

    # Embed this round of conversation for future RAG hits
    now_iso = datetime.now(UTC).isoformat()
    await embedding_service.upsert_embeddings(
        store.db,
        embedder,
        user_id=current_user.id,
        items=[
            (
                "chat_message",
                f"user:{current_user.id}:phase:{request.phase}:{now_iso}:u",
                request.phase,
                request.message,
            ),
            (
                "chat_message",
                f"user:{current_user.id}:phase:{request.phase}:{now_iso}:a",
                request.phase,
                reply,
            ),
        ],
    )

    await store.db.commit()

    full_history = await store.get_history(current_user.id, request.phase)
    return ChatResponse(reply=reply, history=[ChatMessage(**m) for m in full_history])


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

- [ ] **Step 2: 既存 test_api_chat.py の Claude 呼出引数アサーションを修正**

`test_chat_carries_history_across_calls` などで `kwargs["system"]` を検証している場合、RAG コンテキストが付与されると等値比較で失敗する。アサーションを「system プロンプトに `Phase1` が含まれる」程度に緩める、または system は検証から外す。

具体的には Task 5 の test_chat_carries_history_across_calls は messages のみ検証しているため不要。test_claude_client.py の同等テストは Mock SDK 直叩きなので影響なし。確認のみ。

- [ ] **Step 3: 新規テスト追加（test_api_chat.py 末尾）**

```python
def test_chat_includes_rag_context_in_system_prompt(auth_client):
    from app.main import app

    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text="reply")])
    )
    fake = ClaudeClient(sdk=fake_sdk, model="claude-sonnet-4-5")
    app.dependency_overrides[get_claude_client] = lambda: fake

    try:
        # First message — no prior RAG, but the system prompt should still
        # include the phase header.
        response = auth_client.post(
            "/api/chat", json={"phase": 1, "message": "Gitのブランチを教えて"}
        )
        assert response.status_code == 200
        system_sent = fake_sdk.messages.create.await_args.kwargs["system"]
        assert "Phase1" in system_sent
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 4: 実行**

`make seed-embeddings` を済ませてから:

```bash
uv run pytest tests/test_api_chat.py tests/test_api_chat_history.py -v
```

期待: 全 PASS。RAG コンテキスト注入により system prompt は長くなるが既存テストはアサーションを system に依存していないため影響なし。

- [ ] **Step 5: コミット**

```bash
git add backend/app/api/chat.py backend/tests/test_api_chat.py
git commit -m "feat(backend): inject RAG context into chat system prompt; embed Q/A per turn"
```

---

## Task 12: 全テスト確認 + lint

- [ ] **Step 1: 全テスト**

```bash
docker compose up -d postgres
uv run pytest -v
```

期待: バックエンド全テスト (Sprint 1 の 67 + Sprint 2 の 約 30) すべて PASS。

- [ ] **Step 2: lint**

```bash
uv run ruff check app tests
```

期待: All checks passed。

- [ ] **Step 3: コミット不要（緑であれば次へ）**

---

## Task 13: フロント — Submission 型定義 + API クライアント

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/types/curriculum.ts`
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/lib/api.ts`

- [ ] **Step 1: `types/curriculum.ts` 末尾に追加**

```ts
export interface Submission {
  id: string;
  phase: number;
  task_no: number;
  content: string;
  ai_feedback: string | null;
  score: number | null;
  submitted_at: string;
  graded_at: string | null;
}
```

- [ ] **Step 2: `lib/api.ts` の `api` オブジェクトに追加**

```ts
listSubmissions: (phase: number) =>
  rawRequest<Submission[]>(`/api/submissions/${phase}`),

submitTask: (payload: { phase: number; task_no: number; content: string }) =>
  rawRequest<Submission>('/api/submissions', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
```

`Submission` の import を file 先頭に追加。

- [ ] **Step 3: ビルド確認**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: コミット**

```bash
git add frontend/src/types/curriculum.ts frontend/src/lib/api.ts
git commit -m "feat(frontend): add Submission type and submit/list API client methods"
```

---

## Task 14: フロント — Pinia store に submissions

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/stores/curriculum.ts`

- [ ] **Step 1: state に追加**

```ts
interface State {
  phases: PhaseSummary[];
  progress: Record<number, ProgressOut>;
  chatLogs: Record<number, ChatMessage[]>;
  submissions: Record<number, Submission[]>;  // ← 追加
  loading: boolean;
  error: string | null;
}

// state() 初期化に追加:
submissions: {},
```

- [ ] **Step 2: actions に追加**

```ts
async loadSubmissions(phase: number) {
  this.submissions[phase] = await api.listSubmissions(phase);
},

async submitTask(phase: number, task_no: number, content: string) {
  const submission = await api.submitTask({ phase, task_no, content });
  const list = this.submissions[phase] ?? [];
  const idx = list.findIndex((s) => s.task_no === task_no);
  if (idx >= 0) list[idx] = submission;
  else list.push(submission);
  this.submissions[phase] = [...list].sort((a, b) => a.task_no - b.task_no);
  // progress could have just promoted to 'submitted'; refresh
  await this.fetchPhasesWithProgress();
  return submission;
},
```

- [ ] **Step 3: ビルド確認 + コミット**

```bash
npm run build
git add frontend/src/stores/curriculum.ts
git commit -m "feat(frontend): track submissions in curriculum store"
```

---

## Task 15: フロント — SubmissionPanel + TaskSubmissionCard コンポーネント

**Files:**
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/components/TaskSubmissionCard.vue`
- Create: `/Volumes/Seagate3TB/projects/edu/frontend/src/components/SubmissionPanel.vue`

- [ ] **Step 1: `TaskSubmissionCard.vue`**

```vue
<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { Submission } from '@/types/curriculum';

const props = defineProps<{
  taskNo: number;
  taskText: string;
  submission?: Submission;
  busy: boolean;
}>();
const emit = defineEmits<{
  submit: [taskNo: number, content: string];
}>();

const draft = ref(props.submission?.content ?? '');
watch(() => props.submission?.content, (v) => {
  if (v !== undefined) draft.value = v;
});

const isGraded = computed(() => props.submission?.score != null);
const scoreLabel = computed(() =>
  isGraded.value ? `${props.submission!.score} / 100` : '採点中…',
);

const send = () => {
  if (!draft.value.trim()) return;
  emit('submit', props.taskNo, draft.value.trim());
};
</script>

<template>
  <article class="task-card">
    <header>
      <span class="num">Task {{ taskNo }}</span>
      <span v-if="submission" class="badge" :class="{ graded: isGraded }">
        {{ scoreLabel }}
      </span>
    </header>
    <p class="desc">{{ taskText }}</p>

    <textarea
      v-model="draft"
      rows="4"
      placeholder="提出内容を記入してください..."
      :disabled="busy"
    />

    <div v-if="submission?.ai_feedback" class="feedback">
      <strong>AI フィードバック:</strong>
      <p>{{ submission.ai_feedback }}</p>
    </div>

    <button type="button" :disabled="busy || !draft.trim()" @click="send">
      {{ submission ? '再提出する' : '提出する' }}
    </button>
  </article>
</template>

<style scoped>
.task-card {
  background: var(--color-surface);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.task-card header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.num { font-size: 0.8rem; font-weight: 600; color: var(--color-accent); }
.badge {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fef3c7;
  color: #92400e;
}
.badge.graded { background: #dcfce7; color: #166534; }
.desc { margin: 0; font-size: 0.92rem; }
textarea {
  resize: vertical;
  min-height: 88px;
  font: inherit;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.6rem;
}
.feedback {
  background: #f9fafb;
  padding: 0.6rem 0.9rem;
  border-radius: 10px;
}
.feedback p { margin: 0.3rem 0 0; color: #374151; font-size: 0.9rem; }
button {
  align-self: flex-start;
  background: var(--color-accent);
  color: white;
  border: 0;
  border-radius: 10px;
  padding: 0.5rem 1rem;
  cursor: pointer;
  font: inherit;
}
button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
```

- [ ] **Step 2: `SubmissionPanel.vue`**

```vue
<script setup lang="ts">
import { computed } from 'vue';
import type { PhaseSummary, Submission } from '@/types/curriculum';
import TaskSubmissionCard from '@/components/TaskSubmissionCard.vue';

const props = defineProps<{
  phase: PhaseSummary;
  submissions: Submission[];
  busyTaskNo: number | null;
}>();
const emit = defineEmits<{
  submit: [taskNo: number, content: string];
}>();

const byTaskNo = computed(() => {
  const m: Record<number, Submission> = {};
  for (const s of props.submissions) m[s.task_no] = s;
  return m;
});
</script>

<template>
  <section class="panel">
    <h3>課題提出</h3>
    <TaskSubmissionCard
      v-for="(task, i) in phase.tasks"
      :key="i"
      :task-no="i + 1"
      :task-text="task"
      :submission="byTaskNo[i + 1]"
      :busy="busyTaskNo === i + 1"
      @submit="(no, content) => emit('submit', no, content)"
    />
  </section>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.panel h3 {
  margin: 0;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6b7280;
}
</style>
```

- [ ] **Step 3: ビルド確認**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: コミット**

```bash
git add frontend/src/components/TaskSubmissionCard.vue frontend/src/components/SubmissionPanel.vue
git commit -m "feat(frontend): add TaskSubmissionCard + SubmissionPanel components"
```

---

## Task 16: フロント — PhaseChatView に提出パネル統合

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/frontend/src/views/PhaseChatView.vue`

- [ ] **Step 1: 編集**

`<script setup>` 内:

```ts
import SubmissionPanel from '@/components/SubmissionPanel.vue';
// 既存 import の隣に追加

const submissions = computed(() => store.submissions[props.phase] ?? []);
const busyTaskNo = ref<number | null>(null);

onMounted(async () => {
  // ... 既存 + 末尾に追加:
  if (!data.locked) {
    await store.loadSubmissions(props.phase);
  }
});

const submitTask = async (taskNo: number, content: string) => {
  busyTaskNo.value = taskNo;
  sendError.value = null;
  try {
    await store.submitTask(props.phase, taskNo, content);
  } catch (e) {
    sendError.value = e instanceof Error ? e.message : 'unknown error';
  } finally {
    busyTaskNo.value = null;
  }
};
```

`<template>` の `<ChatInput ...>` の後ろ、`<hr />` の前に挿入:

```vue
<hr class="thin" />
<SubmissionPanel
  v-if="phaseData"
  :phase="phaseData"
  :submissions="submissions"
  :busy-task-no="busyTaskNo"
  @submit="submitTask"
/>
```

- [ ] **Step 2: ビルド + 手動確認**

```bash
cd frontend && npm run build
# docker compose up で全体起動して /phases/1 を開く
```

提出パネルが Chat 入力欄の下に表示され、3 つの TaskSubmissionCard が並ぶことを目視確認。

- [ ] **Step 3: コミット**

```bash
git add frontend/src/views/PhaseChatView.vue
git commit -m "feat(frontend): integrate SubmissionPanel into PhaseChatView"
```

---

## Task 17: README + 設計書差分 + ドキュメント

**Files:**
- Modify: `/Volumes/Seagate3TB/projects/edu/README.md`
- Modify: `/Volumes/Seagate3TB/projects/edu/docs/design/03-db-design.md`
- Modify: `/Volumes/Seagate3TB/projects/edu/docs/design/04-interface-design.md`
- Modify: `/Volumes/Seagate3TB/projects/edu/docs/design/05-screen-design.md`

- [ ] **Step 1: README に Sprint 2 完了マーク + seed-embeddings 記載**

```markdown
## 実装進捗
- [x] Sprint 0: スケルトン + カリキュラム配信 + AIチューター対話MVP
- [x] Sprint 1: PostgreSQL + JWT 認証 + 進捗管理 + 会話履歴永続化
- [x] Sprint 2: 課題提出 + AI採点 + RAG (pgvector + fastembed)
- [ ] Sprint 3: 管理者ダッシュボード
- [ ] Sprint 4: CI/CD + 本番デプロイ + 監視

## 初回起動時の手順 (Sprint 2)
```bash
make dev              # サービス起動 + マイグレーション
make seed-embeddings  # カリキュラム埋め込みを 1 回投入
```
```

- [ ] **Step 2: 設計書追記（短く、Sprint 2 セクションを追加）**

DB 設計書、IF 設計書、画面設計書それぞれの末尾に「## Sprint 2 追加分」セクションを追加。テーブル/エンドポイント/UI の差分のみ記述。詳細は Sprint 2 計画書を参照、と書く。

- [ ] **Step 3: 最終確認**

```bash
make test    # backend + frontend
make lint
cd frontend && npm run build
```

期待: 全 PASS。

- [ ] **Step 4: コミット**

```bash
git add README.md docs/design
git commit -m "docs: mark Sprint 2 complete and update design specs"
```

---

## 完了基準（Sprint 2 受入チェックリスト）

### 機能

- [ ] `make seed-embeddings` で 28 件のカリキュラム埋め込みが投入される
- [ ] 認証済ユーザが `/phases/1` で課題テキストを入力 → 提出 → 数秒で score + AI feedback がカードに表示
- [ ] 全 3 タスク提出後、Home のフェーズバッジが `提出済み (submitted)` に切替
- [ ] チャット送信時、関連あるカリキュラム/過去 chat が Claude system prompt に注入されている (バックエンドログまたはテストで検証)
- [ ] 採点 JSON 解析失敗時もユーザは「採点エラー」表示でフォールバック動作

### 非機能

- [ ] バックエンドカバレッジ ≥ 75% (RAG/embedding はモデル DL のため除外可)
- [ ] `ruff check app tests` clean
- [ ] フロント `npm run build` clean
- [ ] 提出 API レスポンス < 5s (Claude 採点込み)

### ドキュメント

- [ ] README に Sprint 2 完了マーク
- [ ] DB / IF / 画面設計書に Sprint 2 セクション追記

---

## 後続スプリント

| Sprint | 主スコープ |
|---|---|
| 3 | ファイルアップロード、再採点、管理者ダッシュボード (ロール + 全受講者進捗) |
| 4 | CI/CD (GitHub Actions)、AWS デプロイ、監視 (Sentry/OpenTelemetry)、Secrets Manager |

---

## 自己レビュー

### スペック網羅

| 設計要件 | 対応タスク |
|---|---|
| submissions テーブル + UPSERT | Task 2, 3, 8 |
| 採点 (Claude JSON 出力) | Task 7 |
| 採点の同期実行 | Task 8 (upsert_and_grade 内部) |
| 進捗自動遷移 → submitted | Task 8 (maybe_mark_submitted), Task 9 (E2E 検証) |
| embeddings + pgvector + HNSW | Task 2, 3 |
| fastembed multilingual-e5-small | Task 1, 4 |
| RAG 検索 | Task 6 |
| RAG context 注入 | Task 11 |
| カリキュラム seed | Task 10 |
| 提出 API | Task 9 |
| フロント提出 UI | Task 13, 14, 15, 16 |

### プレースホルダー検査

- "TODO", "later", "TBD" — なし
- 「Similar to Task N」— なし

### 型整合性

- `Submission` (model / schema / TS) — フィールド名一致 (id, phase, task_no, content, ai_feedback, score, submitted_at, graded_at)
- `GradingResult` (Pydantic) — score: int 0-100, feedback: str
- `EMBEDDING_DIM=384` を 1 箇所だけで定義し参照

### 既知の妥協

- 採点同期実行: Claude が遅延した場合 HTTP 接続が長く保持される。Sprint 4 で非同期化検討
- RAG embedding を chat ハンドラ内で永続化: 失敗時の補正なし。Sprint 4 でリトライキュー化
- HNSW index は HSNW のメンテナンスが必要だが、Sprint 2 のデータ量 (~数百行) では問題なし

---

## 実行ハンドオフ

本計画書は `docs/superpowers/plans/2026-06-03-ai-tutor-curriculum-sprint-2.md` に保存。

`feature/sprint-2` ブランチで `superpowers:executing-plans` を起動して Task 1 から実行する。
