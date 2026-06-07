# 03 DB設計書

**版:** 1.0
**作成日:** 2026-06-02
**DBMS:** PostgreSQL 16（image: `pgvector/pgvector:pg16`）

---

## 1. 全体方針

- ORM は SQLAlchemy 2.x async、ドライバは asyncpg
- マイグレーションは Alembic（async env）、リビジョンは `backend/alembic/versions/` 配下
- すべての主キーは UUIDv4（PostgreSQL の `gen_random_uuid()` ではなく Python 側 `uuid.uuid4()` で生成し、移植性を確保）
- タイムスタンプは `TIMESTAMP WITH TIME ZONE`、アプリ側で `datetime.now(UTC)` を入れる
- 文字列のサイズ制約は ORM 側で `String(N)`、DB 側でも反映
- pgvector 拡張は Sprint 1 で `CREATE EXTENSION IF NOT EXISTS vector` のみ宣言。実テーブルへの `vector` カラムは Sprint 2 で追加
- DB は 2 つ作成：`ai_tutor`（運用 + dev）、`ai_tutor_test`（テスト）。両方で pgvector 拡張を有効化

---

## 2. ER 図

```
                  ┌──────────────┐
                  │    users     │
                  │──────────────│
                  │ id (PK,UUID) │
                  │ email (UQ)   │
                  │ name         │
                  │ password_hash│
                  │ created_at   │
                  └──────┬───────┘
                         │ 1
              ┌──────────┴───────────┐
              │ N                    │ N
        ┌─────▼──────┐         ┌────▼─────────┐
        │  progress  │         │ chat_history │
        │────────────│         │──────────────│
        │ id (PK)    │         │ id (PK)      │
        │ user_id FK │         │ user_id FK   │
        │ phase      │         │ phase        │
        │ status     │         │ role         │
        │ started_at │         │ content      │
        │ completed_at│        │ created_at   │
        │ UQ(user_id,phase)    │              │
        └────────────┘         └──────────────┘
```

- `users.id ←─ progress.user_id`（`ON DELETE CASCADE`）
- `users.id ←─ chat_history.user_id`（`ON DELETE CASCADE`）
- `progress` には `(user_id, phase)` の UNIQUE 制約

---

## 3. テーブル定義

### 3.1 `users`

| カラム | 型 | NULL | デフォルト | 備考 |
|---|---|---|---|---|
| `id` | `UUID` | NO | （アプリ） | PK、`uuid.uuid4()` |
| `email` | `VARCHAR(255)` | NO | — | UNIQUE、INDEX |
| `name` | `VARCHAR(100)` | NO | — | 表示用 |
| `password_hash` | `VARCHAR(255)` | NO | — | bcrypt（`$2b$12$...`） |
| `created_at` | `TIMESTAMPTZ` | NO | `datetime.now(UTC)` | — |

**インデックス:**
- PK: `users_pkey (id)`
- UNIQUE: `ix_users_email (email)`

**運用メモ:**
- `email` は大小文字区別あり（Postgres デフォルト）。アプリ側で `email.lower()` 正規化はせず、ユーザ入力をそのまま保持。重複判定は SQL の UNIQUE に委ねる
- `password_hash` のフィールド幅 255 は bcrypt（60 文字）+ 将来の argon2 移行余裕

### 3.2 `progress`

受講者の各フェーズの進捗状態を保持する。ユーザ登録時に 4 行を seed する。

| カラム | 型 | NULL | デフォルト | 備考 |
|---|---|---|---|---|
| `id` | `UUID` | NO | （アプリ） | PK |
| `user_id` | `UUID` | NO | — | FK → `users.id` ON DELETE CASCADE、INDEX |
| `phase` | `INTEGER` | NO | — | 1〜4 |
| `status` | `VARCHAR(20)` | NO | `'locked'` | `'locked'` / `'in_progress'` / `'submitted'` / `'completed'` |
| `started_at` | `TIMESTAMPTZ` | YES | NULL | `locked → in_progress` 遷移時に記録 |
| `completed_at` | `TIMESTAMPTZ` | YES | NULL | `* → completed` 遷移時に記録 |

**インデックス・制約:**
- PK: `progress_pkey (id)`
- UNIQUE: `uq_progress_user_phase (user_id, phase)` — 1ユーザ1フェーズ1行を保証
- INDEX: `ix_progress_user_id (user_id)` — マイページの一覧取得高速化

**状態遷移:**

```
locked ──── unlock by service ───▶ in_progress
                                         │
                                         │ POST /api/progress/{phase}/complete
                                         ▼
                                     completed
                                         │
                                         │ phase+1 が locked なら自動的に
                                         └▶ next.status = in_progress
                                            next.started_at = now()
```

`submitted` 状態は Sprint 1 では使用しない（Sprint 2 で活用）。enum 値としてのみ予約。

**Sprint 1 で許容される遷移:**

| from | to | 契機 |
|---|---|---|
| `locked` | `in_progress` | 1) 登録時の Phase 1 seed、2) 前フェーズ `completed` の連鎖解放 |
| `in_progress` | `completed` | `POST /api/progress/{phase}/complete` |
| `completed` | `completed` | 同上（冪等） |

それ以外の遷移はサービス層で 409/422 を返す。

### 3.3 `chat_history`

フェーズ毎の会話履歴。`role` と `content` を時系列順に保持。

| カラム | 型 | NULL | デフォルト | 備考 |
|---|---|---|---|---|
| `id` | `UUID` | NO | （アプリ） | PK |
| `user_id` | `UUID` | NO | — | FK → `users.id` ON DELETE CASCADE |
| `phase` | `INTEGER` | NO | — | 1〜4 |
| `role` | `VARCHAR(20)` | NO | — | `'user'` / `'assistant'` |
| `content` | `TEXT` | NO | — | 制約：1〜4000 文字（アプリ側 Pydantic） |
| `created_at` | `TIMESTAMPTZ` | NO | `datetime.now(UTC)` | ソートキー |

**インデックス:**
- PK: `chat_history_pkey (id)`
- INDEX: `ix_chat_history_user_phase_created (user_id, phase, created_at)` — 履歴ロードの主クエリ用

**運用メモ:**
- 削除はせず append-only（Sprint 1）。フェーズ完了後も履歴は残す
- `content` の上限はアプリ側 Pydantic で 4000 文字、DB は TEXT（無制限）
- AI 応答のメタデータ（モデル名、トークン数）は Sprint 1 では保持しない（Sprint 4 でコスト計測時に拡張）

---

## 4. マイグレーション運用

### 4.1 初回マイグレーション

実装計画 Task 4 で生成する `backend/alembic/versions/20260602_0001_initial.py`（命名は Alembic 設定の `file_template` に従う）に以下を含める：

```python
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "progress",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("phase", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="locked"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "phase", name="uq_progress_user_phase"),
    )
    op.create_index("ix_progress_user_id", "progress", ["user_id"])

    op.create_table(
        "chat_history",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("phase", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_chat_history_user_phase_created",
        "chat_history",
        ["user_id", "phase", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_history_user_phase_created", table_name="chat_history")
    op.drop_table("chat_history")
    op.drop_index("ix_progress_user_id", table_name="progress")
    op.drop_table("progress")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    # vector 拡張は他テーブルでも使う可能性があるため drop しない
```

### 4.2 適用方法

| シーン | コマンド |
|---|---|
| 通常起動 | `make dev` → backend コンテナが起動時に `alembic upgrade head` を実行 |
| ローカル直接 | `cd backend && uv run alembic upgrade head` |
| 1段戻す | `uv run alembic downgrade -1` |
| 新規リビジョン | `uv run alembic revision --autogenerate -m "<message>"` |

### 4.3 命名規約

| 種別 | 規約 | 例 |
|---|---|---|
| テーブル | snake_case 複数形 | `users`, `chat_history` |
| カラム | snake_case | `password_hash`, `created_at` |
| PK | `<table>_pkey`（Postgres デフォルト） | `users_pkey` |
| UNIQUE | `uq_<table>_<col1>_<col2>` | `uq_progress_user_phase` |
| INDEX | `ix_<table>_<col>` | `ix_users_email` |
| FK | `fk_<table>_<col>_<reftable>`（Alembic auto は無名でも可） | — |

### 4.4 テスト DB の扱い

- `ai_tutor_test` は `docker-compose` 初回起動時に `backend/db-init/01-create-test-db.sql` で作成
- テスト実行時は Alembic を流さず、`Base.metadata.create_all` で全テーブルを作成（高速化）
- 各テストの開始前に `TRUNCATE <全テーブル> RESTART IDENTITY CASCADE` でクリア
- 同様の理由でテスト時の `BCRYPT_ROUNDS=4`、`JWT_SECRET_KEY=test-secret`

---

## 5. 容量見積（参考）

Sprint 1 想定（20 名、各 200 メッセージ）：

| テーブル | 行数 | 想定サイズ |
|---|---|---|
| users | 20 | < 5 KB |
| progress | 80 | < 10 KB |
| chat_history | 4,000 | ≈ 8 MB（平均 2 KB / 行）|

Sprint 4 本番時にも `chat_history` が主体。月間 100 名 × 1,000 メッセージなら ≈ 200 MB / 月。VACUUM / パーティションは現時点で不要。

---

## 6. バックアップ / リストア（参考）

- ローカル: `docker compose exec postgres pg_dump -U postgres ai_tutor > backup.sql`
- リストア: `cat backup.sql | docker compose exec -T postgres psql -U postgres ai_tutor`
- 本番運用設計は Sprint 4 で定義（マネージドサービス採用を想定）

---

## 7. 既知の懸念

| 懸念 | 評価 | 対応 |
|---|---|---|
| `chat_history.content` のサイズ無制限 | LOW（4000 文字制約はアプリ側のみ）| 監査追加時に DB 制約も追加検討 |
| `users.email` 大小区別 | MEDIUM | アプリで `lower()` 正規化を入れるか、Sprint 2 で `citext` カラム化検討 |
| `progress.status` が文字列 | MEDIUM | `CHECK` 制約 or Postgres ENUM 化は Sprint 2 で議論 |
| トランザクション境界 | LOW | API ハンドラ毎にセッションを開く設計で十分 |

---

## 8. Sprint 2 追加分

### 8.1 `submissions`

| カラム | 型 | NULL | デフォルト | 備考 |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid.uuid4()` | PK |
| `user_id` | `UUID` | NO | — | FK → `users.id` ON DELETE CASCADE、INDEX |
| `phase` | `INTEGER` | NO | — | 1〜4、`CHECK` |
| `task_no` | `INTEGER` | NO | — | 1〜5、`CHECK` |
| `content` | `TEXT` | NO | — | 提出本文 |
| `ai_feedback` | `TEXT` | YES | NULL | 採点コメント |
| `score` | `INTEGER` | YES | NULL | 0〜100、`CHECK` |
| `submitted_at` | `TIMESTAMPTZ` | NO | `datetime.now(UTC)` | — |
| `graded_at` | `TIMESTAMPTZ` | YES | NULL | 採点完了時刻 |

**制約・INDEX:**
- `UNIQUE(user_id, phase, task_no)` `uq_submissions_user_phase_task` — UPSERT 用
- `INDEX ix_submissions_user_id (user_id)`

UPSERT 方針: 同じ (user, phase, task_no) への再提出は上書き。履歴は保持しない (Sprint 4+ で audit table 検討)。

### 8.2 `embeddings`

| カラム | 型 | NULL | 備考 |
|---|---|---|---|
| `id` | `UUID` | NO | PK |
| `user_id` | `UUID` | YES | NULL=グローバル(カリキュラム)、それ以外は個人。FK CASCADE |
| `source_type` | `VARCHAR(50)` | NO | `curriculum_skill` / `curriculum_task` / `chat_message` / `submission` |
| `source_ref` | `VARCHAR(200)` | NO | 例 `phase:1:skill:0`、`user:<uuid>:phase:1:<iso>:u` |
| `phase` | `INTEGER` | YES | フィルタ高速化 |
| `content` | `TEXT` | NO | 埋め込み元の本文 |
| `embedding` | `vector(384)` | NO | `pgvector.sqlalchemy.Vector` |
| `created_at` | `TIMESTAMPTZ` | NO | — |

**INDEX:**
- `INDEX ix_embeddings_user_phase (user_id, phase)` — RAG フィルタ
- `INDEX ix_embeddings_vector_hnsw (embedding vector_cosine_ops) USING hnsw` — 近似最近傍

384 次元の根拠: `intfloat/multilingual-e5-small` の出力次元。

### 8.3 ER 図 (差分)

```
   users ─< submissions
   users ─< embeddings  (user_id NULL = global)
```

## Sprint 3 追加

### submission_files

| Column | Type | Constraint |
|---|---|---|
| id | UUID | PK |
| submission_id | UUID | FK submissions.id ON DELETE CASCADE |
| file_path | TEXT | NOT NULL |
| mime_type | VARCHAR(120) | NOT NULL |
| size_bytes | INTEGER | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

INDEX: `ix_submission_files_submission_id (submission_id)`

### grading_attempts

| Column | Type | Constraint |
|---|---|---|
| id | UUID | PK |
| submission_id | UUID | FK submissions.id ON DELETE CASCADE |
| status | VARCHAR(20) | CHECK IN ('graded','failed') |
| score | INTEGER | NULL OR 0..100 |
| feedback | TEXT | NULL |
| error_message | TEXT | NULL |
| model_name | VARCHAR(120) | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

INDEX:
- `ix_grading_attempts_submission_id (submission_id)`
- `ix_grading_attempts_submission_created (submission_id, created_at DESC)`

`submissions.score` / `submissions.ai_feedback` は最新 graded attempt のキャッシュとして保持される（既存 API 互換性のため）。

---

## Sprint 4 追加

### users.is_admin

既存 `users` テーブルに 1 カラム追加。RBAC は単一フラグで表現する（roles テーブル分解は YAGNI）。

| Column | Type | Constraint |
|---|---|---|
| is_admin | BOOLEAN | NOT NULL DEFAULT false |

マイグレーション (`20260606_af4220e315e6_sprint4_admin_comments_notifications.py`) は `server_default='false'` を持つため、既存全行は別 UPDATE 不要で false に backfill される。運用上の admin 化は `scripts/promote_admin.py <email>` で実施。

### instructor_comments

講師から提出物に対する一方向コメント（受講者からの返信は Sprint 5 以降）。

| Column | Type | Constraint |
|---|---|---|
| id | UUID | PK |
| submission_id | UUID | FK submissions.id **ON DELETE CASCADE** |
| author_user_id | UUID | FK users.id **ON DELETE RESTRICT** |
| body | TEXT | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now(), `onupdate` 自動更新 |

INDEX: `ix_instructor_comments_submission_id (submission_id)`

FK セマンティクス:
- 提出が削除されればコメントも消える（orphan を残さない）。
- 講師ユーザーの削除は RESTRICT — 削除前に「無名化」運用 (`author_user_id` を別の保守ユーザーに付け替える) を強制する。

### notifications

In-app 通知（SSE/WS なし、フロント 30 秒ポーリング）。

| Column | Type | Constraint |
|---|---|---|
| id | UUID | PK |
| recipient_user_id | UUID | FK users.id **ON DELETE CASCADE** |
| sender_user_id | UUID | FK users.id **ON DELETE RESTRICT** |
| title | VARCHAR(200) | NOT NULL |
| body | TEXT | NOT NULL |
| link | VARCHAR(500) | NULL |
| read_at | TIMESTAMPTZ | NULL（既読化時のみセット） |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

INDEX: `ix_notifications_recipient_user_id (recipient_user_id)`

`read_at IS NULL` が未読の真値。`unread_count` 集計はこの列を `WHERE read_at IS NULL` で COUNT して算出する（separate column を持たず、二重管理にしない）。

### ER 図 (Sprint 4 差分)

```text
users 1 ──< instructor_comments >── 1 submissions    (author / submission)
users 1 ──< notifications              (recipient / sender 双方向)
```

### マイグレーション ノート

Sprint 3 で `ix_grading_attempts_submission_created` を migration から作っていたがモデルに `Index(...)` 宣言が無く、Sprint 4 の autogenerate が誤って drop しようとした。Sprint 4 マイグレーションで該当 drop を手で除去し、`GradingAttempt.__table_args__` に同 index を宣言して将来の `alembic check` も無音化した。
