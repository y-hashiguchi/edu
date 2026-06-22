# Render + Supabase 最小パイロット 引き継ぎ

**最終更新:** 2026-06-21 19:00 JST 前後  
**リポジトリ:** `/Volumes/Seagate3TB/projects/edu`  
**ブランチ:** `main`

## 目的

既存の教育システムを、最低限のデモパイロットとして公開する。

- Frontend: Render Static Site
- Backend: Render Starter Web Service、1インスタンス
- PostgreSQL: Supabase Free / Supavisor Transaction Pooler
- Upload: Render persistent disk 1 GB
- 想定固定費: 約 `$7.25/月` + Anthropic API利用料

## 議論した内容・決定事項

### 最小構成

- Redisとbackground workerは使用しない。
- 非同期採点、予約broadcast、curriculum cache pub/subは無効化する。
- embeddingはstub modeを使用する。
- semantic search品質の評価は、このパイロットの対象外とする。
- スケール要件が明確になるまではAPIを1インスタンスで運用する。

### Supabase

- Direct接続はローカル環境のDNS/IPv6制約で利用できなかった。
- Session Pooler `5432`は認証に失敗した。
- Transaction Pooler `6543`は接続できたため、Renderからはこちらを使用する。
- `DATABASE_URL`には`prepared_statement_cache_size=0`を付ける。
- ただし、これだけではasyncpgのprepared statement名衝突を防げなかった。
- SQLAlchemyは`NullPool`を使い、asyncpgのprepared statement名をUUID化する。

### Render

- Docker起動コマンドはshell引用形式を使わず、直接コマンド形式にする。

```yaml
dockerCommand: uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

- migrationはpre-deployで実行する。
- GitHub Actions成功後だけ自動デプロイする。

```yaml
preDeployCommand: uv run alembic upgrade head
autoDeployTrigger: checksPass
```

### セキュリティ

- DBパスワードやAPIキーはソースコードへ保存しない。
- Renderのsecret環境変数として管理する。
- Anthropic APIキーがRender画面およびRender例外ログで一時的に見える状態になった。
- **現在のAnthropic APIキーは必ずローテーションすること。**
- 秘密値が写った既知の一時スクリーンショットは削除したが、Renderログ側にも値の断片が残っている可能性がある。

## 公開環境

- Frontend: <https://edu-demo-web.onrender.com>
- Backend: <https://edu-demo-api.onrender.com>
- Health: <https://edu-demo-api.onrender.com/healthz>
- Version: <https://edu-demo-api.onrender.com/version> （稼働中の commit/branch を返す。デプロイ反映の外部確認用）
- Render API service ID: `srv-d8qvr0ugvqtc73eb6kjg`
- Supabase project ref: `njaxokacfeokzhgbmdeq`
- Region: Singapore

## 完了した作業

### インフラ・デプロイ

- Render Blueprintを作成。
- Frontend Static Siteを公開。
- Backend Starter Web Serviceを公開。
- Render persistent diskを`/app/uploads`へマウント。
- Supabase Freeプロジェクトを作成。
- Alembic migrationをRender pre-deployで実行。
- Render互換のAPI起動コマンドへ修正。
- Supabase Transaction Poolerへの接続を確立。
- Supavisor上のprepared statement名衝突を修正。

### 公開確認

以下は確認済み。

```text
GET /healthz
=> 200 {"status":"ok"}

GET /api/courses/catalog
=> 200

Frontend
=> HTTP 200
```

ユーザーのログインとPhase 1画面表示も確認済み。

### 追加した障害ログ

`backend/app/api/chat.py`でAnthropic SDK例外をスタックトレース付きで記録するようにした。

```python
try:
    reply = await claude.complete(
        system_prompt=system_prompt,
        history=next_history,
    )
except Exception as e:
    logger.exception("Anthropic chat completion failed")
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="upstream LLM error",
    ) from e
```

## 作業中のタスクと現在の進捗

### タスク: Phase 1チャットの502解消

**状態: 完全解決・本番検証済み（2026-06-21）。**

公開環境での検証結果（検証用アカウントを登録して実施）:

```text
POST /api/chat?course=ai-driven-dev (phase 1) => 200, assistant 応答あり
GET  /api/chat/history/1            => 200, user/assistant 両メッセージが永続化
```

502 / `Anthropic chat completion failed` は再現せず。キーのローテーション（新キーをRenderへ設定）と改行除去デプロイ（`a13c8cb`）の組み合わせで解消。

#### 根本原因（確定）

`httpx.LocalProtocolError: Illegal header value` → `anthropic.APIConnectionError` → チャット502。

- 原因は、Renderの`ANTHROPIC_API_KEY`に混入した改行/空白を、コードが正規化せずそのままAuthorizationヘッダーへ渡していたこと。
- httpxはヘッダー値に改行を含むと送信を拒否する。
- `APIConnectionError`（認証失敗の401ではなくトランスポート層エラー）であることが、「キー自体は正しいが値が壊れている」ことの裏付け。
- ローカル`.env`のキーは検査済みで完全にクリーン（108文字、CR/LF・前後空白・引用符なし）。ローカルでチャットが成功していた事実と整合する。
- `backend/app/core/claude_client.py`は`AsyncAnthropic(api_key=settings.anthropic_api_key)`とキーを無加工で渡しており、`backend/app/config.py`にも正規化が無かった。

#### 実施した修正（コード）

システム境界（設定読み込み）でキーの空白を全除去する恒久対策を入れた。プラットフォーム非依存で、Render側でキーに改行が付いても自動的に除去される。

- `backend/app/config.py`
  - `normalize_api_key(value)` を追加（`"".join(value.split())` で全空白・CR/LFを除去）。
  - `anthropic_api_key` に `field_validator(mode="before")` を追加して読み込み時に正規化。
- `backend/tests/test_anthropic_key.py`（新規）
  - 純粋関数テスト5件 + Settings配線テスト1件。TDDでRED→GREENを確認。

#### 検証

```text
uv run pytest -q
=> 521 passed, 1 skipped

uv run ruff check app/config.py tests/test_anthropic_key.py
=> All checks passed
```

## 状態: パイロット一区切り（2026-06-21）

チャット502解消・`/version`追加・キーローテーション・キー分離まで完了。

### キー運用（分離済み）
- **本番(Render)**: 2026-06-21に発行した新キー。チャット稼働確認済み。
- **ローカル(`.env`、gitignore済み)**: 別途発行した新キー（末尾`wwAA`）。最小コールで有効確認済み。
- **旧キー`edu-ai-tutor-dev`（末尾`jwAA`、露出していた dev キー）**: Anthropic Consoleで失効済み。

### 残作業（任意）
1. 検証用ダミーアカウント（`edu-verify-*@example.com`、コース`ai-driven-dev`、2件）が本番DBに残存。デモ運用上は無害だが、気になる場合は削除する。
2. 提出・同期採点フローの手動確認。
3. GitHub ActionsのNode.js 20非推奨警告に対応（`actions/checkout`等のバージョン更新）。E2Eで稀にflaky（`admin-cohort.spec.ts`）が出る点も将来調査対象。

### 値を表示しない検査例

実際のキーを標準出力へ出さないこと。

```bash
python - <<'PY'
from pathlib import Path

lines = Path(".env").read_text().splitlines()
matches = [line for line in lines if line.startswith("ANTHROPIC_API_KEY=")]
assert len(matches) == 1
value = matches[0].split("=", 1)[1]
print({
    "starts_correctly": value.startswith("sk-ant-"),
    "length": len(value),
    "contains_cr": "\r" in value,
    "contains_lf": "\n" in value,
})
PY
```

## 重要なコード・設計方針

### Supavisor対応

`backend/app/config.py`:

```python
from collections.abc import Callable
from uuid import uuid4


def asyncpg_connect_args() -> dict[str, Callable[[], str]]:
    return {
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    }
```

`backend/app/db/session.py`:

```python
engine = create_async_engine(
    settings.database_url,
    future=True,
    echo=False,
    poolclass=NullPool,
    connect_args=asyncpg_connect_args(),
)
```

理由:

- Transaction Poolerでは接続先サーバーが切り替わり得る。
- asyncpgの固定prepared statement名は他接続と衝突する。
- `prepared_statement_cache_size=0`だけではprepare自体は止まらない。
- `NullPool`と一意なstatement名を併用する。

### LLMエラー処理

- ユーザーには内部例外を返さず、汎用502を返す。
- サーバーログには`logger.exception`でスタックトレースを残す。
- APIキーなどの秘密値が例外メッセージに含まれる可能性があるため、ログ共有時はマスクする。

### デモ構成

- APIは1インスタンス。
- Redis/workerは追加しない。
- `EMBEDDING_STUB_MODE=true`
- `GRADING_ASYNC_ENABLED=false`
- `CURRICULUM_CACHE_PUBSUB_ENABLED=false`
- `SCHEDULED_BROADCAST_CRON_ENABLED=false`
- uploadはRender diskを使用する。

## コミットと検証

最新コミット:

```text
8ea2cf8 feat: add GET /version endpoint exposing running revision
9148489 test: cover GET /version deploy-revision endpoint
a13c8cb fix: normalize Anthropic API key whitespace
537c47d test: reproduce Anthropic API key header corruption
75b7630 fix: isolate asyncpg prepared statement names
d46b5ad test: reproduce Supavisor prepared statement collision
5954acc fix: log Anthropic chat failures
c9d00ee test: reproduce missing Anthropic error log
87e292a fix: use Render-compatible API startup command
2f0e065 test: reproduce Render Docker command failure
decfaaa feat(deploy): add Render Supabase pilot blueprint
```

すべて`main`へpush済み（`a13c8cb`まで、2026-06-21）。

直近の検証:

```text
uv run pytest tests/test_database_url.py tests/test_api_chat.py -q
=> 12 passed

uv run ruff check app/config.py app/db/session.py tests/test_database_url.py
=> All checks passed

GitHub Actions CI 27896236884
=> frontend/backend/docker-build/e2e 全て成功
=> E2E 11 passed
```

Render:

```text
commit 75b7630
=> Deploy live
```

## 主要ファイル

| ファイル | 内容 |
|---|---|
| `render.yaml` | Render API、Static Site、disk、secret、migration |
| `docs/infra/render-demo.md` | Render + Supabase構築手順 |
| `backend/app/config.py` | DB URL正規化、asyncpg statement名生成、APIキー空白除去 |
| `backend/app/db/session.py` | `NullPool`とasyncpg接続設定 |
| `backend/app/api/chat.py` | Anthropic失敗時の例外ログ |
| `backend/app/api/health.py` | `/healthz` と `/version`（稼働 commit/branch） |
| `backend/tests/test_database_url.py` | Supabase/asyncpg接続設定テスト |
| `backend/tests/test_api_chat.py` | Anthropic失敗時の502・ログテスト |
| `backend/tests/test_anthropic_key.py` | APIキー正規化テスト（改行/空白除去） |

## リポジトリ状態

```text
branch: main

untracked:
  HANDOFF_20260617.md
  HANDOFF_20260621_RENDER_SUPABASE.md
```

`HANDOFF_20260617.md`は既存ユーザー作業として扱い、変更していない。
このファイル`HANDOFF_20260621_RENDER_SUPABASE.md`は今回更新したが、まだ未追跡・未コミット。
