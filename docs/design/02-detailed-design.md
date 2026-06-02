# 02 詳細設計書

**版:** 1.0
**作成日:** 2026-06-02

---

## 1. パッケージ構成（バックエンド）

```
backend/app/
├── main.py                     FastAPI ファクトリ・ルーター登録
├── config.py                   Pydantic Settings
├── db/
│   ├── base.py                 DeclarativeBase
│   └── session.py              async engine / SessionLocal / get_db
├── models/
│   ├── __init__.py             集約 import（Alembic 用）
│   ├── user.py
│   ├── progress.py
│   └── chat_history.py
├── schemas/                    Pydantic DTO
│   ├── auth.py
│   ├── progress.py
│   ├── chat.py
│   └── curriculum.py
├── core/
│   ├── claude_client.py        AsyncAnthropic ラッパー
│   ├── security.py             パスワードハッシュ / JWT
│   └── deps.py                 get_db / get_current_user
├── data/
│   └── curriculum.py           4 フェーズ定数（Sprint 0 から不変）
├── memory/
│   └── chat_store.py           SqlChatStore（Sprint 1）
├── services/
│   └── progress.py             進捗ドメインロジック
└── api/                        ルーティング層
    ├── auth.py
    ├── curriculum.py
    ├── progress.py
    └── chat.py
```

### 設計原則

- **層分離:** `api/` は HTTP / DTO のみ、ドメインロジックは `services/` か `memory/`、永続化は `models/` + SQLAlchemy
- **依存方向:** `api → services / memory / core → models / db / data`。逆方向は禁止
- **非同期:** 全てのルートハンドラと DB アクセスは async。同期処理は `claude_client` の内側にも残さない
- **DI:** FastAPI の `Depends` 経由。`get_db` / `get_current_user` / `get_claude_client` の 3 つで API 層の依存を統一

---

## 2. モジュール詳細

### 2.1 `db/base.py`

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

**責務:** ORM 共通基底。全モデルがこれを継承する。

### 2.2 `db/session.py`

| 関数 | 役割 |
|---|---|
| `engine` | `create_async_engine(settings.database_url)` で生成。プロセス内シングルトン |
| `SessionLocal` | `async_sessionmaker(engine, expire_on_commit=False)` |
| `get_db()` | FastAPI dependency。`async with SessionLocal() as session: yield session` |

`expire_on_commit=False` の理由：commit 後にもオブジェクトの属性を参照したい場面（API 応答の組立）があるため。

### 2.3 `core/security.py`

| 関数 | シグネチャ | 役割 |
|---|---|---|
| `hash_password` | `(plain: str) -> str` | bcrypt ハッシュ生成 |
| `verify_password` | `(plain: str, hashed: str) -> bool` | 検証 |
| `create_access_token` | `(subject: str, expires_min: int \| None = None) -> str` | JWT 生成（`sub` + `exp`） |
| `decode_access_token` | `(token: str) -> str` | 検証 → `sub` 文字列を返す。失敗時 `JWTError` |

```python
_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_rounds,
)
```

### 2.4 `core/deps.py`

| 関数 | 役割 |
|---|---|
| `get_db` | `db/session.py` を re-export（ハンドラ側の import 統一） |
| `get_current_user` | `OAuth2PasswordBearer` から token を取得し、`decode_access_token` → DB の users 行を取得して `User` を返す |
| `oauth2_scheme` | `OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)`（`auto_error=False` で `Authorization` 欠落時は手動で 401） |

擬似コード：

```python
async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if token is None:
        raise HTTPException(401, "Not authenticated")
    try:
        sub = decode_access_token(token)
        uid = uuid.UUID(sub)
    except (JWTError, ValueError):
        raise HTTPException(401, "Invalid token")
    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if user is None:
        raise HTTPException(401, "User not found")
    return user
```

### 2.5 `core/claude_client.py`

Sprint 0 の sync 実装を `AsyncAnthropic` に差し替える。

```python
class ClaudeClient:
    def __init__(self, sdk: AsyncAnthropic, model: str) -> None:
        self._sdk = sdk
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        max_tokens: int = 1024,
    ) -> str:
        response = await self._sdk.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=history,
        )
        return response.content[0].text


def get_claude_client() -> ClaudeClient:
    sdk = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return ClaudeClient(sdk=sdk, model=settings.anthropic_model)
```

例外戦略：SDK が `anthropic.APIError` を上げた場合、`api/chat.py` で `HTTPException(502, "upstream LLM error")` に変換する。

### 2.6 `models/user.py`

```python
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

### 2.7 `models/progress.py`

```python
class ProgressStatus(str, Enum):
    LOCKED = "locked"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    COMPLETED = "completed"


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (UniqueConstraint("user_id", "phase", name="uq_progress_user_phase"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    phase: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default=ProgressStatus.LOCKED.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 2.8 `models/chat_history.py`

```python
class ChatHistory(Base):
    __tablename__ = "chat_history"
    __table_args__ = (
        Index("ix_chat_history_user_phase_created", "user_id", "phase", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    phase: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
```

### 2.9 `services/progress.py`

ドメインロジックの単位。トランザクションは呼び出し側（API 層）で `await db.commit()` する責務を持つが、サービス層は `db.flush()` を行う。

| 関数 | シグネチャ | 役割 |
|---|---|---|
| `initialize_progress` | `(db, user_id: UUID) -> None` | 4 フェーズを seed。Phase 1: `in_progress`、他: `locked` |
| `list_progress` | `(db, user_id: UUID) -> list[Progress]` | phase 昇順 |
| `is_phase_unlocked` | `(db, user_id: UUID, phase: int) -> bool` | `status != 'locked'` |
| `complete_phase` | `(db, user_id: UUID, phase: int) -> tuple[Progress, Progress \| None]` | 当該フェーズを `completed`、次フェーズが `locked` なら `in_progress` に解放。`(current, next_unlocked)` を返す |

例外：

| 例外 | 発生条件 | API 層での対応 |
|---|---|---|
| `PhaseLockedError(phase: int)` | `complete_phase` で対象が `locked` | 403 |
| `PhaseNotFoundError(phase: int)` | `progress` テーブルに該当行無し | 404 |

サービス層内ではこれらドメイン例外を投げ、API 層で `HTTPException` に変換する。

### 2.10 `memory/chat_store.py`

`InMemoryChatStore` を削除し、以下に置き換える。

```python
class SqlChatStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_history(self, user_id: UUID, phase: int) -> list[dict[str, str]]:
        result = await self._db.execute(
            select(ChatHistory)
            .where(ChatHistory.user_id == user_id, ChatHistory.phase == phase)
            .order_by(ChatHistory.created_at)
        )
        return [{"role": m.role, "content": m.content} for m in result.scalars().all()]

    async def append(self, user_id: UUID, phase: int, role: str, content: str) -> None:
        self._db.add(ChatHistory(user_id=user_id, phase=phase, role=role, content=content))
        await self._db.flush()


async def get_chat_store(db: AsyncSession = Depends(get_db)) -> SqlChatStore:
    return SqlChatStore(db)
```

`clear` メソッドは Sprint 1 では公開 API として使わないが、テスト用に残す（または削除して conftest で直接 `TRUNCATE` する）。

### 2.11 `api/auth.py`

3 エンドポイント（`register` / `login` / `me`）。

- `register`:
  1. `db.execute(select(User).where(User.email == payload.email))` で重複チェック → 409
  2. `User` 行を作成、`hash_password` で暗号化
  3. `db.flush()` で `user.id` 確定
  4. `initialize_progress(db, user.id)` 呼び出し
  5. `await db.commit()`、`await db.refresh(user)` → `UserOut` 返却
- `login`:
  1. email で SELECT → 不在 or `verify_password` 失敗で 401（区別しない）
  2. `create_access_token(subject=str(user.id))` → `TokenResponse`
- `me`:
  1. `current_user: User = Depends(get_current_user)` のみ → `UserOut`

### 2.12 `api/progress.py`

- `GET /api/progress`:
  1. `services.progress.list_progress(db, current_user.id)`
  2. `list[ProgressOut]` で返す
- `POST /api/progress/{phase}/complete`:
  1. `services.progress.complete_phase(db, current_user.id, phase)` → `(current, next_unlocked)`
  2. `ProgressCompleteResponse` を組み立てて返す
  3. ドメイン例外を `HTTPException` に変換

### 2.13 `api/curriculum.py`

Sprint 0 の `list_phases` を以下に拡張：

1. `current_user: User = Depends(get_current_user)`（認証必須化）
2. `services.progress.list_progress(db, current_user.id)` で進捗マップを取得
3. `PhaseSummary.locked = (progress.status == 'locked')`, `PhaseSummary.status = progress.status` を埋める

### 2.14 `api/chat.py`

- `POST /api/chat`:
  1. `current_user`, `db`, `claude` を `Depends`
  2. `phase` が CURRICULUM に無ければ 404
  3. `is_phase_unlocked` が False なら 403
  4. `SqlChatStore(db).get_history(current_user.id, phase)` で履歴取得
  5. user メッセージを末尾に追加した list を `claude.complete` に渡す
  6. 成功時：`store.append(role='user')`、`store.append(role='assistant')`、`await db.commit()`
  7. `anthropic.APIError` を捕捉して `HTTPException(502)` に変換
  8. `await store.get_history(...)` で最新履歴を取得し `ChatResponse` 返却
- `GET /api/chat/history/{phase}`:
  1. `phase` が CURRICULUM に無ければ 404
  2. `is_phase_unlocked` が False なら 403
  3. `SqlChatStore(db).get_history(current_user.id, phase)` → `list[ChatMessage]`

---

## 3. シーケンス図

### 3.1 ログイン

```
Browser   FastAPI/auth   security    DB
  │ POST /api/auth/login │           │
  │ {email,password}     │           │
  │──────────────────────▶          │
  │                      │ SELECT user│
  │                      │───────────▶
  │                      │ ◀──────────│
  │                      │ verify_password
  │                      │──────▶ pwd_context.verify
  │                      │ ◀────── True
  │                      │ create_access_token
  │                      │──────▶ jose.encode
  │                      │ ◀────── jwt
  │ ◀────────────────────│           │
  │  200 {access_token}  │           │
```

### 3.2 チャット送信（認証 + 進捗チェック付き）

```
Browser   chat   deps      svc/progress   memory/store     Claude
  │ POST /api/chat        │              │                 │
  │ Authorization: Bearer │              │                 │
  │ {phase, message}      │              │                 │
  │───────────────────────▶              │                 │
  │     get_current_user (deps)          │                 │
  │     → User                           │                 │
  │     is_phase_unlocked ──────────▶    │                 │
  │     ◀──── True                       │                 │
  │     SqlChatStore.get_history ──────────────▶           │
  │     ◀── history                                        │
  │     claude.complete ──────────────────────────────────▶│
  │     ◀── reply                                          │
  │     store.append × 2 ───────────────────────▶          │
  │     db.commit                                          │
  │     store.get_history ─────────────────────▶           │
  │     ◀── full_history                                   │
  │ ◀───────────────────                                   │
  │  200 ChatResponse                                      │
```

### 3.3 フェーズ完了 → 次フェーズ解放

```
Browser   progress    svc/progress   DB
  │ POST /api/progress/1/complete    │
  │──────────────────────▶           │
  │   complete_phase(user, 1) ──────▶│
  │      SELECT progress WHERE p=1   │
  │      ◀────────                  │
  │      status='completed'          │
  │      completed_at=now            │
  │      SELECT progress WHERE p=2  │
  │      ◀────────                  │
  │      (locked) status='in_progress'
  │      started_at=now             │
  │      commit                      │
  │   ◀── (current, next_unlocked) │
  │ ◀─────────────                  │
  │  200                            │
```

---

## 4. エラー処理方針

| レイヤ | 戦略 |
|---|---|
| Pydantic | バリデーション失敗は FastAPI が 422 を自動応答 |
| サービス層 | ドメイン例外（`PhaseLockedError` 等）を定義、API 層で HTTP 変換 |
| API 層 | `HTTPException` のみを使い、メッセージは仕様書記載の固定文言 |
| DB | `IntegrityError` 等は API 層で適切な 4xx に変換、それ以外は 500（FastAPI デフォルト） |
| Claude SDK | `anthropic.APIError` を 502 に変換、ログにスタック残し |
| 未捕捉 | uvicorn が 500 を返す。サーバログにスタック出力 |

`detail` の文言は IF 設計書（04）に従う。

---

## 5. ロギング

- Sprint 1 では `print`/`logging.getLogger(__name__).info` の最低限のみ
- 構造化ログ・分散トレースは Sprint 4 で導入
- 認証失敗のログは 1 行（email / ip）に留め、パスワードは出力禁止

---

## 6. フロントエンド構成

```
frontend/src/
├── main.ts                 createApp / Pinia / persistedstate / Router
├── App.vue                 ヘッダー + RouterView
├── env.d.ts
├── lib/api.ts              fetch ラッパー（401 ハンドリング）
├── router/index.ts         routes + beforeEach ガード
├── stores/
│   ├── auth.ts             token / user 保持（localStorage 永続）
│   └── curriculum.ts       phases / progress / chatLogs（永続化対象外）
├── types/curriculum.ts     PhaseSummary / Progress / ChatMessage
├── views/
│   ├── LoginView.vue
│   ├── HomeView.vue
│   └── PhaseChatView.vue
└── components/
    ├── PhaseCard.vue       lock 表示
    ├── ChatLog.vue
    ├── ChatInput.vue
    └── ChatMessage.vue
```

### 6.1 `lib/api.ts` の責務

- `VITE_API_BASE_URL` を基底に fetch
- リクエスト前に auth store からトークンを取得し `Authorization` ヘッダーに追加
- 401 を受けたら auth store の `logout()` を呼び `router.push('/login')`
- それ以外の non-2xx は `Error` で throw

```ts
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const authStore = useAuthStore();
  const headers: HeadersInit = { 'Content-Type': 'application/json', ...(init?.headers ?? {}) };
  if (authStore.token) headers['Authorization'] = `Bearer ${authStore.token}`;

  const res = await fetch(`${baseUrl}${path}`, { ...init, headers });

  if (res.status === 401) {
    authStore.logout();
    router.push('/login');
    throw new Error('Unauthorized');
  }
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}
```

### 6.2 `stores/auth.ts`

| State | 説明 |
|---|---|
| `token: string \| null` | JWT |
| `user: UserOut \| null` | `/api/auth/me` の結果 |

| Action | 役割 |
|---|---|
| `login(email, pw)` | `POST /api/auth/login` → token 保存 → `me()` |
| `register(email, name, pw)` | `POST /api/auth/register` → 完了後 `login` |
| `me()` | `GET /api/auth/me` → user 保存 |
| `logout()` | token / user を null に。localStorage も自動クリア（plugin） |

`pinia-plugin-persistedstate` で `token` のみ localStorage 同期。`user` はリロード時に `/me` で復元。

### 6.3 `router/index.ts`

```
beforeEach(to, from):
  publicRoutes = ['login']
  if to.name not in public and !auth.token:
    return { name: 'login' }
  if to.name == 'login' and auth.token:
    return { name: 'home' }
```

未認証で `/phases/1` を直接開いた場合は `/login` にリダイレクト。ログイン済で `/login` を開いた場合は `/` へ。

### 6.4 ロック表示の判定

`HomeView` 起動時に `curriculumStore.fetchPhasesWithProgress()` を呼ぶ。`PhaseSummary.locked` を見て `PhaseCard` の `<RouterLink>` を `<div class="locked">` に差し替える。

### 6.5 履歴自動ロード

`PhaseChatView` のセットアップで：

```
onMounted:
  if phases is empty: fetchPhasesWithProgress()
  if phase.locked: router.push('/')  // 念のため
  await curriculumStore.loadHistory(phase)
```

`loadHistory(phase)` は `GET /api/chat/history/{phase}` → `chatLogs[phase]` を上書き。

### 6.6 完了ボタン

`PhaseChatView` 末尾に「このフェーズを完了する」ボタン。クリックで `curriculumStore.completePhase(phase)` → `POST /api/progress/{phase}/complete` → ストアの progress を更新 → `router.push('/')`。

---

## 7. 共通設計指針

- **Immutability:** ストアの state は spread で更新（既存 Sprint 0 と同じ）
- **Error UI:** ネットワークエラー / 422 は画面下部のバナーで表示
- **Loading UI:** すべての非同期操作にローディング表示
- **Accessibility:** ボタンには aria-label、入力フォームには label、エラーには `role="alert"`

詳細は画面設計書（05）参照。
