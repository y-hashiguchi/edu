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

## 実装進捗

- [x] Sprint 0: スケルトン + カリキュラム配信 + AIチューター対話MVP
- [ ] Sprint 1: PostgreSQL + 認証 + 進捗管理 + 会話履歴永続化
- [ ] Sprint 2: 課題提出 + AI採点
- [ ] Sprint 3: 管理者ダッシュボード

詳細は `docs/superpowers/plans/` を参照。
