# 01 システム基本設計書

**版:** 1.0
**作成日:** 2026-06-02
**対象スプリント:** Sprint 1

---

## 1. システム概要

### 1.1 目的

訓練修了後メンバー（Java/Python 基礎・HTML/CSS/JS・DB 基礎修了済）が、AI 駆動型開発スキル（Git・AI ツール活用・AI 協調開発・AI アプリ実装）を 3〜4 ヶ月で体系的に習得するための、Web ベースの **AI チューター対話型学習システム** を提供する。

### 1.2 利用シナリオ（Sprint 1 想定）

1. 受講者はメールアドレスとパスワードでアカウントを登録する。
2. ログイン後、4 フェーズのカリキュラム一覧を確認する（Phase 1 のみ解放、他はロック）。
3. Phase 1 を選択し、AI チューターと対話して学習を進める。
4. 学習完了を自己宣言（「このフェーズを完了する」）すると Phase 1 が `completed`、Phase 2 が解放される。
5. 同様に Phase 2 → 3 → 4 と段階的に解放される。
6. 任意のタイミングで再ログインしても、進捗と会話履歴は復元される。

### 1.3 スコープ（Sprint 1）

| カテゴリ | 含む | 含まない |
|---|---|---|
| 認証 | メール+パスワード登録、JWT ログイン、`/me` 取得 | リフレッシュトークン、OAuth、パスワードリセット、メール確認 |
| 進捗管理 | フェーズ状態の永続化、解放ロック、完了による次フェーズ解放 | 課題提出、AI 採点、提出物保管 |
| 会話 | フェーズ毎の履歴永続化、初期化時の再ロード | 会話のエクスポート、削除 UI |
| カリキュラム | 4 フェーズ + システムプロンプト（Sprint 0 と同一） | 動的編集、運営による配信 |
| 管理機能 | （なし） | 管理者ダッシュボード、ユーザ管理 UI |
| 運用 | ローカル Docker Compose 起動、`alembic upgrade head` | CI/CD、本番デプロイ、監視 |

---

## 2. システム構成

### 2.1 論理アーキテクチャ

```
┌──────────────────────────────────┐
│ ブラウザ（Vue 3 SPA / Vite dev）             │
│  ├─ /login                                    │
│  ├─ /  （HomeView：フェーズ一覧）              │
│  └─ /phases/:phase （PhaseChatView：チャット） │
└───────────────┬──────────────────┘
                │  HTTPS (dev: HTTP)
                │  Authorization: Bearer <JWT>
                ▼
┌──────────────────────────────────┐
│ FastAPI（uvicorn）                            │
│  ├─ /api/auth/*       認証                    │
│  ├─ /api/curriculum/* カリキュラム配信         │
│  ├─ /api/progress/*   進捗 CRUD               │
│  ├─ /api/chat         チャット送信             │
│  └─ /api/chat/history チャット履歴取得         │
│                                                │
│  Layers:                                       │
│   api/      ルーティング・DTO 変換             │
│   services/ ドメインロジック（進捗解放など）   │
│   memory/   ChatStore（SqlChatStore）          │
│   core/     security、claude_client、deps     │
│   models/   SQLAlchemy ORM                     │
│   db/       Async engine / session             │
└───────┬───────────────────┬────────┘
        │ asyncpg            │ HTTPS
        ▼                    ▼
┌──────────────┐  ┌─────────────────┐
│ PostgreSQL 16 │  │ Anthropic API     │
│ + pgvector    │  │ claude-sonnet-4-5 │
│ (Sprint 1 で  │  │                   │
│  拡張のみ宣言)│  └─────────────────┘
│  users        │
│  progress     │
│  chat_history │
└──────────────┘
```

### 2.2 物理構成（ローカル開発）

`docker-compose` で `postgres` / `backend` / `frontend` の 3 サービスを起動する。

| サービス | イメージ | ポート | 用途 |
|---|---|---|---|
| postgres | `pgvector/pgvector:pg16` | 5432 | DB（`ai_tutor` 本番用、`ai_tutor_test` テスト用） |
| backend | `python:3.12-slim` + `uv` | 8000 | FastAPI |
| frontend | `node:20-alpine` + `vite` | 5173 | Vue 3 dev server |

backend は起動時に `alembic upgrade head` を実行してからアプリ本体を立ち上げる。

### 2.3 技術スタック

| レイヤ | 技術 | 採用根拠 |
|---|---|---|
| 言語（BE） | Python 3.12 | Sprint 0 継承 |
| Web FW | FastAPI 0.115+ | 非同期・型・OpenAPI 自動 |
| ORM | SQLAlchemy 2.x async | 公式 async、Alembic と統合 |
| DB ドライバ | asyncpg | 高速・公式推奨 |
| マイグレーション | Alembic（async env） | デファクト |
| 認証 | python-jose（HS256）+ passlib[bcrypt] | 軽量・実績 |
| AI SDK | `anthropic.AsyncAnthropic` | async ルートと整合 |
| Validation | Pydantic v2 + email-validator | FastAPI 標準 |
| 言語（FE） | TypeScript 5.6 | Sprint 0 継承 |
| FE FW | Vue 3 + Vite | Sprint 0 継承 |
| ストア | Pinia + `pinia-plugin-persistedstate` | localStorage 永続化 |
| ルーター | Vue Router 4 | Sprint 0 継承 |
| DB | PostgreSQL 16 + pgvector | Sprint 2 RAG 準備 |

---

## 3. 非機能要件

### 3.1 性能

| 項目 | 目標 |
|---|---|
| `/api/auth/login` レイテンシ | ≤ 300ms（bcrypt 12 ラウンド込み、ローカル DB） |
| `/api/chat` レイテンシ | Claude API 応答 + 50ms（DB 書き込み）以内 |
| `/api/curriculum/phases` レイテンシ | ≤ 50ms（静的データ + progress 1 クエリ） |
| 同時利用 | Sprint 1 想定 20 名 / 同時 5 セッション |

### 3.2 可用性 / 運用

- ローカル開発前提のため SLA は定義しない
- Postgres データは Docker volume `postgres_data` に永続化（`make clean` で削除）
- `alembic upgrade head` は backend 起動コマンドに組み込み、起動時に自動適用
- 障害時の手順は本スプリントでは整備しない（Sprint 2 で監査ログ整備）

### 3.3 セキュリティ

| 項目 | 設計方針 |
|---|---|
| パスワード保管 | `passlib[bcrypt]`、`BCRYPT_ROUNDS=12`（本番）/ `4`（テスト） |
| 認証トークン | JWT HS256、`exp=60min`、`sub=user.id (UUID 文字列)` |
| トークン保管（FE） | localStorage（Sprint 1 受容リスク。Sprint 2+ で HttpOnly Cookie 検討） |
| シークレット管理 | `JWT_SECRET_KEY` / `ANTHROPIC_API_KEY` を `.env` のみで管理、`.env` は git 管理外 |
| CORS | `CORS_ALLOW_ORIGINS=http://localhost:5173`（dev 限定） |
| 入力検証 | Pydantic v2 で全 DTO を検証、`min/max_length` / `pattern` / `EmailStr` |
| SQL インジェクション | SQLAlchemy 2.x の Core/ORM 経由のみ。生 SQL は Alembic マイグレーションに限定 |
| エラー詳細リーク | 401/403/404/422 の `detail` は固定文言。500 系はスタックトレースを返さない |
| 監査ログ | Sprint 1 ではアプリケーションログのみ（DB トリガー監査は Sprint 3） |

### 3.4 多言語対応

- UI 表記・AI 応答ともに日本語前提
- 文字コードは UTF-8 統一、Postgres も `LC_COLLATE=ja_JP.UTF-8` を要求しない（`C` で運用）

### 3.5 ブラウザ対応

- Chrome / Edge / Firefox / Safari 最新 2 バージョン
- 受講者の利用環境を考慮し IE 系は対象外

---

## 4. データフロー（高レベル）

### 4.1 登録フロー

```
[Browser] /login → 新規登録切替
   │ POST /api/auth/register {email, name, password}
   ▼
[FastAPI] register
   │ ① email 重複チェック
   │ ② bcrypt ハッシュ
   │ ③ users INSERT
   │ ④ progress INSERT × 4（Phase 1 のみ in_progress）
   │ ⑤ commit
   ▼
[Browser] 成功 → /login へ遷移、ユーザに案内表示
```

### 4.2 ログイン → チャットフロー

```
[Browser] /login
   │ POST /api/auth/login → access_token
   │ ストアに保存（localStorage 同期）
   ▼
[Browser] / (HomeView)
   │ GET /api/auth/me        （ガード用）
   │ GET /api/curriculum/phases
   │ GET /api/progress
   │ → 各 PhaseCard に locked/status を反映
   ▼
[Browser] /phases/1
   │ GET /api/chat/history/1 → 既存履歴を復元
   │
   │ ユーザがメッセージ送信
   │ POST /api/chat {phase:1, message}
   │   サーバ側で
   │     ① is_phase_unlocked(user, 1) → True
   │     ② SqlChatStore.get_history
   │     ③ AsyncAnthropic.messages.create
   │     ④ SqlChatStore.append × 2 (user / assistant)
   │     ⑤ commit
   │     ⑥ ChatResponse 返却
   ▼
[Browser] 「このフェーズを完了する」クリック
   │ POST /api/progress/1/complete
   │   ① Phase 1 → completed
   │   ② Phase 2 → in_progress（unlock）
   ▼
[Browser] HomeView 再描画 → Phase 2 が解放表示
```

---

## 5. ロードマップ（参考）

```
Sprint 0  ✓ スケルトン + 対話 MVP（メモリ）
Sprint 1  ★ DB + 認証 + 進捗 + 履歴永続化      ←本書
Sprint 2    課題提出 + AI 採点 + RAG (pgvector)
Sprint 3    管理者ダッシュボード
Sprint 4    本番デプロイ / CI / 監視
```

---

## 6. 制約事項

- 本 Sprint では「複数人が同じシステムを使う」状態は機能的に成立するが、運用ガイド（受講者リスト・パスワード初期発行）は別資料で扱う
- `JWT_SECRET_KEY` は `.env` ベースのため、複数インスタンス間の鍵共有はファイル配布で実施（Sprint 4 で Secrets Manager 化）
- 監視・アラート・障害復旧手順は本スプリント対象外
- 個人情報の取り扱いは `email` / `name` / `password_hash` のみ。本番運用前にプライバシーポリシーの整備が必要

---

## 7. 用語

| 用語 | 定義 |
|---|---|
| フェーズ | 学習カリキュラムの単位。Sprint 1 では 4 フェーズ固定 |
| ロック | 前フェーズが未完了で当該フェーズを利用できない状態（`progress.status = 'locked'`） |
| 解放（unlock） | `locked → in_progress` への遷移 |
| 完了 | 受講者の自己宣言による `* → completed` 遷移 |
| AI チューター | フェーズ毎のシステムプロンプトで人格を切替えた Claude API クライアント |
| 会話履歴 | `(user_id, phase)` で一意なメッセージ列。フェーズをまたいでは共有されない |
