# Render demo pilot

Render上に、最低限のデモ環境を構築するための手順。

## 構成

| Resource | Render plan | Purpose |
|---|---|---|
| `edu-demo-web` | Static Site | Vue frontend |
| `edu-demo-api` | Starter | FastAPI backend |
| Supabase project | Free | PostgreSQL + pgvector |
| `submission-uploads` | 1 GB disk | 提出ファイル |

Redisとbackground workerは使用しない。採点とカリキュラムembedding更新はAPI
process内で同期実行する。

想定固定費は約 `$7.25/month`。これにAnthropic API利用料と超過帯域料金が加わる。

## デモ向けの制約

- backendは1 instanceのみ
- 非同期採点、予約broadcast worker、Redis pub/subは無効
- embeddingはstub mode。画面・チャット・提出・採点フローの確認用であり、
  semantic search品質の評価には使用しない
- upload diskを付けるためbackend deploy時に数秒の停止が発生する
- Supabase Freeは少人数デモ専用
- RenderからSupabaseへのDB接続はSupavisor session poolerを使用する

## 初回作成

1. SupabaseでSingapore regionのFree projectを作成する。
2. Supabase DashboardのDatabase Extensionsで`vector`を有効化する。
3. **Connect** からSession poolerの接続文字列（port `5432`）を取得する。
4. Render DashboardでGitHub repository `y-hashiguchi/edu` へのアクセスを許可する。
5. **New > Blueprint** を選択し、このrepositoryの `render.yaml` を指定する。
6. 初回作成時に以下のsecret値を入力する。

| Key | Value |
|---|---|
| `DATABASE_URL` | Supabase Session pooler URL |
| `ANTHROPIC_API_KEY` | デモ用Anthropic API key |
| `CORS_ALLOW_ORIGINS` | frontendの公開URL |
| `VITE_API_BASE_URL` | backendの公開URL |

公開URLは通常、次の形式になる。

```text
https://edu-demo-web.onrender.com
https://edu-demo-api.onrender.com
```

Renderがsuffix付きURLを割り当てた場合は、実際のURLを使用する。初回frontend build後に
URLを修正した場合は、frontendをmanual deployしてbuildし直す。

`JWT_SECRET_KEY` はBlueprintが自動生成する。Supabase URLの
`postgres://` / `postgresql://` schemeはアプリ側でasyncpg URLへ正規化される。
transaction pooler（port `6543`）はprepared statement制約があるため使用しない。

## 自動処理

backend deployでは以下を実行する。

1. Docker image build
2. Supabaseへの接続後、`uv run alembic upgrade head`
3. backend起動
4. 初回のみ `uv run python -m scripts.seed_embeddings`
5. `/healthz` health check

`render.yaml` はGitHub Actions成功後にのみ自動deployする。

## 動作確認

```bash
curl -sf https://YOUR-API.onrender.com/healthz
curl -sf https://YOUR-API.onrender.com/api/courses/catalog
curl -sf -o /dev/null -w '%{http_code}\n' https://YOUR-WEB.onrender.com/login
```

ブラウザで以下を確認する。

1. ユーザー登録
2. ログイン
3. チャット
4. テキスト提出と同期採点
5. 小さいファイルの提出とダウンロード

## 管理者への昇格

対象ユーザーを通常登録した後、backendのRender Shellで実行する。

```bash
uv run python -m scripts.promote_admin admin@example.com
```

## ローカル検証

```bash
make render-validate
cd backend && uv run pytest tests/test_database_url.py
```

Render CLIが導入済みなら、公式schema検証も実行する。

```bash
render blueprints validate render.yaml
```

## 次の拡張

利用者数や採点待ち時間が増えた段階で、次の順に拡張する。

1. Render Key Valueとbackground workerを追加
2. `GRADING_ASYNC_ENABLED=true`
3. embedding stubを無効化し、実embedding modelのmemory要件に合わせてbackendを増強
4. uploadをS3へ移行
5. Supabase planを有料へ変更
