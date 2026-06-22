# edu プロジェクト 残作業 TODO

最終更新: 2026-06-22（git log / コード / 本番実測で一次確認）

> このファイルは過去の陳腐化したメモリではなく、**実際の git 履歴・コード・本番挙動を一次確認**して作成したもの。
> リポジトリ実到達点: **Sprint 28 + デプロイ強化フェーズ**（Sprint 29 の S3 移行スクリプトまで完了）。
> HEAD: `aabb4b1`（origin/main 同期）。

---

## ✅ 完了済み（記録訂正・再実装しないこと）

- Sprint 1〜28 全完了。**Sprint 29（local→S3 移行スクリプト）も完了**（`c48ef24`、`backend/scripts/migrate_uploads_to_s3.py` + テスト）
- Sprint 10 コホート集計 dashboard（`93a2a00`、cohort 23 tests passing）
- 旧 follow-up の残はすべて消化済み: Sprint 6 MED-2/6 → Sprint 14、Sprint 9 LOW-2 → Sprint 12、Sprint 10 LOW-1 → Sprint 12
- コード内 TODO/FIXME マーカー: 0 件

---

## 🔧 実際に残っている作業

### 1. ~~`/version` が `revision=unknown`~~ ✅ 非バグ（2026-06-22 本番再実測で確認）
- 本番 `GET /version` は `{"commit":"aabb4b1...","branch":"main"}` と**実コミットを正しく返している**
- `app/api/health.py` は `settings.render_git_commit/branch`（Render の `RENDER_GIT_*` env）から取得、正常動作
- 当初の `{revision:unknown}` は不安定チャネル期の偽出力で現実ではなかった。**対応不要**

### 2. 未追跡ファイルの git 整理（高・手早い）
- **対象**: `HANDOFF_20260617.md`, `HANDOFF_20260621_RENDER_SUPABASE.md`, `demo-01-login.png`
- **アクション**: HANDOFF 2件はコミット（秘密情報スキャン後）、`demo-01-login.png`（Playwright デモのスクショ）は削除 or `.gitignore`

### 3. 本番 DB の検証用ダミーアカウント削除（中・任意）
- `edu-verify-*@example.com` 等が本番 Supabase に残存。デモ運用上は無害だが整理可能
- 出典: `HANDOFF_20260621_RENDER_SUPABASE.md` 残作業

### 4. Render ログの秘密値断片の確認（中・セキュリティ衛生・任意）
- 過去の一時スクショに写った秘密値が Render ログ側に断片で残る可能性
- 出典: `HANDOFF_20260621_RENDER_SUPABASE.md`

### 5. インフラ拡張候補（低・未着手の候補止まり）
- ECS/Fargate 向け Compose 代替の検討
- ALB Terraform（`infra/terraform/alb/`）の実運用検証
- 出典: `HANDOFF_20260617.md` 優先度中

---

## メモ
- デモ検証は **API 経由（curl）が安定**。Playwright(MCP) は Render コールドスタートと併発して不安定
- ローカルテストは SQLite in-memory（Docker 不要）。`make verify` = pytest + vitest
- 本番: Web <https://edu-demo-web.onrender.com> / API <https://edu-demo-api.onrender.com>
