# 04 IF設計書（REST API）

**版:** 1.0
**作成日:** 2026-06-02
**Base URL:** `http://localhost:8000`（dev）
**Content-Type:** `application/json`（全エンドポイント共通）

---

## 1. 共通仕様

### 1.1 認証ヘッダー

認証が必要なエンドポイントは以下のヘッダーを必須とする。

```
Authorization: Bearer <access_token>
```

`<access_token>` は `POST /api/auth/login` のレスポンスで取得した JWT。

### 1.2 認証エラー応答

| HTTP | 条件 | レスポンス |
|---|---|---|
| 401 | `Authorization` ヘッダー無し / 形式不正 / 期限切れ / 署名不一致 | `{"detail": "Not authenticated"}` または `{"detail": "Invalid token"}` |
| 401 | トークンが指す `user_id` が存在しない | `{"detail": "User not found"}` |
| 403 | 認証は通ったが対象フェーズが `locked` | `{"detail": "phase {n} is locked"}` |

### 1.3 バリデーションエラー応答

FastAPI/Pydantic 標準の 422 を返す。

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters",
      "input": "abc"
    }
  ]
}
```

### 1.4 ID 表現

`user_id` 等の UUID は文字列で扱う（例: `"3f5e7c8a-...."`）。リクエスト/レスポンスとも文字列。

### 1.5 タイムゾーン

タイムスタンプは ISO 8601 形式の UTC を返す（例: `"2026-06-02T08:15:30.123456+00:00"`）。

### 1.6 CORS

dev では `CORS_ALLOW_ORIGINS=http://localhost:5173` のみ許可。

---

## 2. エンドポイント一覧

| # | メソッド | パス | 認証 | 概要 |
|---|---|---|---|---|
| 1 | GET | `/healthz` | 不要 | ヘルスチェック |
| 2 | POST | `/api/auth/register` | 不要 | アカウント登録 |
| 3 | POST | `/api/auth/login` | 不要 | ログイン → JWT 発行 |
| 4 | GET | `/api/auth/me` | 必要 | 自分の情報取得 |
| 5 | GET | `/api/curriculum/phases` | 必要 | フェーズ一覧（進捗状態込み） |
| 6 | GET | `/api/progress` | 必要 | 自分の進捗一覧 |
| 7 | POST | `/api/progress/{phase}/complete` | 必要 | フェーズ完了 + 次フェーズ解放 |
| 8 | POST | `/api/chat` | 必要 | AI チューターにメッセージ送信 |
| 9 | GET | `/api/chat/history/{phase}` | 必要 | フェーズの会話履歴取得 |

---

## 3. エンドポイント詳細

### 3.1 `GET /healthz`

**用途:** Docker Compose ヘルスチェック / 監視

**Response 200:**
```json
{"status": "ok"}
```

### 3.2 `POST /api/auth/register`

**用途:** 新規受講者の登録。成功すると `users` + `progress` × 4 が同一トランザクションで作成される。

**Request:**
```json
{
  "email": "alice@example.com",
  "name": "アリス",
  "password": "password123"
}
```

| フィールド | 型 | 制約 |
|---|---|---|
| `email` | string (EmailStr) | RFC 5322 準拠、最大 255 文字 |
| `name` | string | 1–100 文字 |
| `password` | string | 8–128 文字 |

**Response 201:**
```json
{
  "id": "3f5e7c8a-1d6f-4f2b-9c01-2e7e1b3a8c4d",
  "email": "alice@example.com",
  "name": "アリス",
  "created_at": "2026-06-02T08:15:30.123456+00:00"
}
```

**Error:**

| HTTP | 条件 | detail |
|---|---|---|
| 409 | email 重複 | `"Email already registered"` |
| 422 | バリデーション失敗 | FastAPI 標準 |

### 3.3 `POST /api/auth/login`

**Request:**
```json
{
  "email": "alice@example.com",
  "password": "password123"
}
```

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5...",
  "token_type": "bearer"
}
```

トークン本体は `{ "sub": "<user.id>", "exp": <unix_ts> }`。`exp` はサーバ時刻 + `JWT_EXPIRES_MIN` 分。

**Error:**

| HTTP | 条件 | detail |
|---|---|---|
| 401 | email が存在しない or パスワード不一致 | `"Invalid credentials"`（区別しない） |
| 422 | バリデーション失敗 | FastAPI 標準 |

### 3.4 `GET /api/auth/me`

**Response 200:**
```json
{
  "id": "3f5e7c8a-1d6f-4f2b-9c01-2e7e1b3a8c4d",
  "email": "alice@example.com",
  "name": "アリス",
  "created_at": "2026-06-02T08:15:30.123456+00:00"
}
```

**Error:** 共通 401。

### 3.5 `GET /api/curriculum/phases`

**用途:** フェーズ一覧 + 進捗状態 + ロック状態。フロントの HomeView が起動時に呼ぶ。

**Response 200:**
```json
[
  {
    "phase": 1,
    "title": "開発環境の近代化",
    "goal": "AIツールを使いこなすための「土台」を固める",
    "duration": "2〜3週間",
    "skills": ["Git / GitHub", "VSCode拡張機能", "ターミナル操作", "REST API基礎"],
    "tasks": [
      "Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成",
      "VSCode拡張（GitLens・REST Client・GitHub Copilot）の導入と動作確認",
      "curlでREST APIを叩き、JSONレスポンス構造をまとめる"
    ],
    "locked": false,
    "status": "in_progress"
  },
  {
    "phase": 2,
    "title": "AIツール活用マスター",
    "...": "...",
    "locked": true,
    "status": "locked"
  }
]
```

| 追加フィールド | 型 | 説明 |
|---|---|---|
| `locked` | bool | `status == 'locked'` のショートカット。FE で UI 分岐するため |
| `status` | string | `'locked' / 'in_progress' / 'submitted' / 'completed'` |

**Error:** 共通 401。

### 3.6 `GET /api/progress`

**Response 200:**
```json
[
  {
    "phase": 1,
    "status": "in_progress",
    "started_at": "2026-06-02T08:15:31.000000+00:00",
    "completed_at": null
  },
  {
    "phase": 2,
    "status": "locked",
    "started_at": null,
    "completed_at": null
  },
  {
    "phase": 3,
    "status": "locked",
    "started_at": null,
    "completed_at": null
  },
  {
    "phase": 4,
    "status": "locked",
    "started_at": null,
    "completed_at": null
  }
]
```

並び順は `phase` 昇順。

### 3.7 `POST /api/progress/{phase}/complete`

**Path Parameter:**

| 名前 | 型 | 制約 |
|---|---|---|
| `phase` | integer | 1〜4 |

**Request body:** なし

**Response 200:**
```json
{
  "phase": 1,
  "status": "completed",
  "started_at": "2026-06-02T08:15:31.000000+00:00",
  "completed_at": "2026-06-02T09:00:00.000000+00:00",
  "next_unlocked": {
    "phase": 2,
    "status": "in_progress",
    "started_at": "2026-06-02T09:00:00.000000+00:00",
    "completed_at": null
  }
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `next_unlocked` | object \| null | 当該完了で解放された次フェーズ。最終フェーズ完了時 or 既に解放済の場合は `null` |

**Error:**

| HTTP | 条件 | detail |
|---|---|---|
| 401 | 認証エラー | 共通 |
| 403 | 当該フェーズが `locked` | `"phase {n} is locked"` |
| 404 | 当該 `phase` が `progress` テーブルに無い（通常起きない） | `"progress for phase {n} not found"` |
| 422 | `phase` が範囲外 | FastAPI 標準 |

冪等性：既に `completed` のフェーズに対する再呼び出しは 200 を返し、`next_unlocked` は `null`（既に解放済のため）。

### 3.8 `POST /api/chat`

**Request:**
```json
{
  "phase": 1,
  "message": "Gitとは何ですか？"
}
```

| フィールド | 型 | 制約 |
|---|---|---|
| `phase` | integer | 1〜4 |
| `message` | string | 1–4000 文字 |

**Sprint 0 との差分:** `user_id` フィールドは削除。`current_user.id` を採用。

**Response 200:**
```json
{
  "reply": "Gitはバージョン管理ツールです...",
  "history": [
    {"role": "user", "content": "Gitとは何ですか？"},
    {"role": "assistant", "content": "Gitはバージョン管理ツールです..."}
  ]
}
```

`history` は当該フェーズの全履歴（新しい 2 件を含む全件）。

**Error:**

| HTTP | 条件 | detail |
|---|---|---|
| 401 | 認証エラー | 共通 |
| 403 | フェーズが `locked` | `"phase {n} is locked"` |
| 404 | `phase` が CURRICULUM に無い（防御的） | `"phase {n} not found"` |
| 422 | バリデーション失敗 | FastAPI 標準 |
| 502 | Claude API エラー | `"upstream LLM error"`（エラー詳細はサーバログ） |

### 3.9 `GET /api/chat/history/{phase}`

**Path Parameter:**

| 名前 | 型 | 制約 |
|---|---|---|
| `phase` | integer | 1〜4 |

**Response 200:**
```json
[
  {"role": "user", "content": "Gitとは何ですか？"},
  {"role": "assistant", "content": "Gitはバージョン管理ツールです..."}
]
```

履歴が無い場合は空配列 `[]`。

**Error:**

| HTTP | 条件 | detail |
|---|---|---|
| 401 | 認証エラー | 共通 |
| 403 | フェーズが `locked` | `"phase {n} is locked"` |
| 404 | `phase` が範囲外 | FastAPI 422 にて捕捉 |

---

## 4. データモデル（DTO 一覧）

### 4.1 リクエスト

| Schema | 用途 | 必須フィールド |
|---|---|---|
| `RegisterRequest` | 3.2 | email, name, password |
| `LoginRequest` | 3.3 | email, password |
| `ChatRequest` | 3.8 | phase, message |

### 4.2 レスポンス

| Schema | 用途 |
|---|---|
| `UserOut` | 3.2 / 3.4 |
| `TokenResponse` | 3.3 |
| `PhaseSummary` | 3.5（`locked`/`status` 追加版） |
| `ProgressOut` | 3.6 / 3.7 |
| `ProgressCompleteResponse` | 3.7（`ProgressOut` + `next_unlocked`） |
| `ChatMessage` | 3.8 / 3.9 |
| `ChatResponse` | 3.8 |

---

## 5. 認証フロー詳細

### 5.1 トークン発行

```
Client                       Server
  │                            │
  │ POST /api/auth/login       │
  │   { email, password }      │
  │ ────────────────────────▶ │
  │                            │ ① users.email を SELECT
  │                            │ ② verify_password(plain, hash)
  │                            │ ③ create_access_token(sub=user.id)
  │ ◀──────────────────────── │
  │  200 { access_token }      │
```

### 5.2 トークン検証

```
Client                       Server
  │ Authorization: Bearer JWT │
  │ ────────────────────────▶ │
  │                            │ ① oauth2_scheme で token を抽出
  │                            │ ② jose.jwt.decode(token, secret, alg)
  │                            │ ③ exp 検証（jose が自動）
  │                            │ ④ sub を UUID にパース
  │                            │ ⑤ users.id で SELECT
  │ ◀──────────────────────── │
  │  200 / 401                 │
```

### 5.3 期限切れの扱い

`exp < now` の場合 `jose.JWTError`。FastAPI ハンドラは 401 `"Invalid token"` を返す。フロント側は 401 を捕捉して `/login` へ強制遷移する（画面設計書 5 章）。

---

## 6. OpenAPI

FastAPI が自動生成。`http://localhost:8000/docs`（Swagger UI）/ `http://localhost:8000/redoc`（ReDoc）で参照可能。タグは `auth` / `curriculum` / `progress` / `chat` / `health` に分類する。

---

## 7. レート制限・スロットリング

Sprint 1 では未実装。Claude API 側のレート上限（無料枠 50RPM 想定）を超えた場合のフロント側 UI は「数秒待って再試行」ヒントを表示するに留める。Sprint 4 でアプリ側レート制限を導入する。

---

## 8. Sprint 2 追加エンドポイント

### 8.1 `POST /api/submissions`

**用途:** 1 タスクの提出 + 即時採点（UPSERT）

**Request:**
```json
{ "phase": 1, "task_no": 1, "content": "Gitでブランチ切ってPR出しました..." }
```

| フィールド | 型 | 制約 |
|---|---|---|
| `phase` | integer | 1–4 |
| `task_no` | integer | 1–5 |
| `content` | string | 1–10000 文字 |

**Response 201:**
```json
{
  "id": "uuid",
  "phase": 1,
  "task_no": 1,
  "content": "...",
  "ai_feedback": "良い回答です。次は…",
  "score": 82,
  "submitted_at": "2026-06-03T08:15:30+00:00",
  "graded_at": "2026-06-03T08:15:32+00:00"
}
```

**Error:**

| HTTP | 条件 | detail |
|---|---|---|
| 401 | 認証 | 共通 |
| 403 | フェーズロック中 | `"phase {n} is locked"` |
| 404 | 該当 phase 不在 (内部不整合) | `"phase {n} not found"` |
| 422 | バリデーション失敗（含む `task_no` 範囲外） | FastAPI 標準 |
| 502 | 採点 Claude エラー | (補足: row は保存され score=null / ai_feedback="採点エラー…" となる。Sprint 2 では 502 ではなく **201 + score=null** で返す方針) |

**冪等性:** 同 (user, phase, task_no) は UPSERT。`graded_at` は再採点ごとに更新。

### 8.2 `GET /api/submissions/{phase}`

**Path:** `phase` 1–4。

**Response 200:**
```json
[
  { "phase": 1, "task_no": 1, "content": "...", "score": 82, "ai_feedback": "...", ... },
  { "phase": 1, "task_no": 2, "content": "...", "score": null, "ai_feedback": null, ... }
]
```

並び順は `task_no` 昇順。フェーズ内で未提出のタスクは配列に含まれない。

### 8.3 進捗自動遷移

Sprint 1 で導入した `progress.status` は `POST /api/submissions` でも変化する:

- フェーズ内の全タスクが少なくとも 1 回提出済になった瞬間に、`in_progress → submitted` に自動遷移
- `submitted` 状態は `POST /api/progress/{phase}/complete` で受講者が明示的に「完了する」操作をするまで保持
- `complete` API は `submitted` でも `in_progress` でも受け付ける（Sprint 1 仕様維持）

### 8.4 `POST /api/chat` (拡張)

Sprint 2 で内部処理が変わる（外部 API 仕様は不変）:

1. 受信メッセージで RAG 検索 (`top_k=4`)
2. 取得した類似コンテンツを system prompt に追記
3. Claude を呼び出して `reply` を取得
4. user message と assistant reply を **両方とも** embeddings に永続化（次回以降の RAG hit を増やす）
5. chat_history への永続化（既存）

RAG 失敗時はコンテキスト無し、または不完全状態で続行（response は変わらない）。

## Sprint 3 追加

### POST /api/submissions（multipart）

**Content-Type:** `multipart/form-data`
**Auth:** Bearer JWT

| field | type | required |
|---|---|---|
| phase | int (1-4) | yes |
| task_no | int (1-5) | yes |
| content | string | yes |
| files | UploadFile[] | no, max 3 |

- **201:** `SubmissionOut`（`files` + `grading_history` を含む）
- **400:** 拡張子NG / サイズ超過 / MIME詐称 / files超過
- **403:** phase locked
- **404:** phase not found
- **422:** task_no が範囲外

### POST /api/submissions/{submission_id}/regrade

**Auth:** Bearer JWT

- **200:** `GradingAttemptOut`
- **404:** submission not found（他ユーザーのものを含む）
- **429:** cooldown 中。`Retry-After` ヘッダで残秒数を返す

### GET /api/submissions/{phase}

`SubmissionOut[]`、各 `SubmissionOut` に `files` と `grading_history`（新しい順）を含む。

### GET /api/submissions/{submission_id}/files/{file_id}

所有者本人のみダウンロード可能。レスポンスは:
- `Content-Disposition: attachment; filename="..."`
- `X-Content-Type-Options: nosniff`

- **404:** submission または file が存在しないか、ユーザーの所有でない場合

---

## Sprint 4 追加

Sprint 4 で導入された全エンドポイントは、Sprint 3 で導入した CSP middleware により `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'` を返す。

### 認可レイヤ

| Dependency | 効果 |
|---|---|
| `get_current_user` | 既存。JWT 未提示・無効 → 401。 |
| `get_current_admin` | Sprint 4 新規。`get_current_user` の上に重ね、`is_admin=false` で 403 `"admin privileges required"`。 |

非 admin が `/api/admin/*` を叩くと 401 vs 403 が明確に分かれる（外部リバースプロキシ側のメトリクス取得に有用）。

### 管理者ロール反映

#### GET /api/auth/me（拡張）

`UserOut` レスポンスに `is_admin: bool` を追加。SPA はこのフラグでルートガード（`/admin/*` 進入可否）を判定する。サーバー側 endpoint は引き続き `get_current_admin` で再判定するため、SPA 状態の改竄では権限昇格できない。

### Admin: 受講者管理

#### GET /api/admin/users

クエリ:
- `limit` (1..200, default 50)
- `offset` (>=0, default 0)

レスポンス: `AdminUserListOut { items, total, limit, offset }`

各 `AdminUserSummary` は `completed_phases` / `in_progress_phases` を含む（dashboard の N+1 を回避）。

- **403:** 非 admin
- **422:** `limit > 200`

#### GET /api/admin/users/{user_id}

レスポンス: `AdminUserDetail { progress[4], latest_scores: {1..4: int|null} }`

`latest_scores` は phase 1..4 を必ず含む（採点済み提出がない phase は null）。

- **404:** 該当 user_id なし

### Admin: 提出物管理

#### GET /api/admin/submissions

クエリ:
- `user_id` (UUID, 任意)
- `phase` (1..4, 任意)
- `limit` (1..200, default 50)
- `offset` (>=0, default 0)

レスポンス: `AdminSubmissionListOut`。各行に `user_email` / `user_name` を denormalize 同梱。

#### GET /api/admin/submissions/{submission_id}

レスポンス: `AdminSubmissionDetail { files, grading_history, comments }`。提出本文・採点履歴・コメントを 1 リクエストで取得（dashboard 二度問い合わせ防止）。

- **404:** 該当 submission なし

### Admin: コメント

#### POST /api/admin/submissions/{submission_id}/comments

ボディ: `CommentCreate { body: 1..2000 chars }`

レスポンス: 201 `AdminCommentOut { author_name }`

- **403:** 非 admin
- **404:** submission なし
- **422:** body validation
- **429:** `admin_write_rate_limit`（default `60/minute` per IP）

#### GET /api/admin/submissions/{submission_id}/comments

レスポンス: `AdminCommentOut[]`（古い順）

### Admin: 通知

#### POST /api/admin/notifications

ボディ: `NotificationCreate`
```jsonc
{
  "recipient_user_id": "<uuid>",
  "title": "1..200 chars",
  "body": "1..2000 chars",
  "link": "0..500 chars | null"
}
```

レスポンス: 201 `NotificationOut { sender_name, read_at: null }`

- **404:** `recipient_user_id` のユーザーが存在しない（FK 違反を 500 に落とさず pre-flight）
- **422:** validation
- **429:** `admin_write_rate_limit`

#### GET /api/admin/notifications

自分（admin）が送信した通知の一覧（outbox）。共同講師の outbox は見えない。

### Learner: `/api/me/...`

`/api/me/*` 配下のエンドポイントは全て `current_user.id` で結果をフィルタする構造ガード（BOLA 防御の系統的保証）。

#### GET /api/me/submissions/{submission_id}/comments

レスポンス: `LearnerCommentOut[]` — `author_user_id` を意図的に省く（講師内部 UUID を露出させない）。

- **404:** submission が存在しない、または自分の提出でない（どちらの場合も同じレスポンスで BOLA-distinguishability を遮断）

#### GET /api/me/notifications

レスポンス:
```jsonc
{
  "items": "NotificationOut[]、設定 notification_poll_limit (default 50) で cap",
  "unread_count": "未読総数（cap 対象外、真値）"
}
```

#### POST /api/me/notifications/{notification_id}/read

冪等。既読フラグを立てる。

- **404:** 通知が存在しない、または自分宛でない（同じレスポンス）

### 環境変数（追加）

| 変数 | デフォルト | 用途 |
|---|---|---|
| `NOTIFICATION_POLL_LIMIT` | `50` | `/api/me/notifications` の `items` 上限 |
| `CSP_POLICY` | `default-src 'none'; frame-ancestors 'none'; base-uri 'none'` | CSP middleware の方針 |
| `ADMIN_WRITE_RATE_LIMIT` | `60/minute` | admin 書き込み系のレート制限 |
