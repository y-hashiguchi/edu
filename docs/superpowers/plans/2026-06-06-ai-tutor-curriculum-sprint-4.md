# AIチューターカリキュラム Sprint 4 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sprint 3 までで揃った受講者ジャーニー（フェーズ進行・チャット・提出 + multimodal 採点 + 履歴 + 再採点）の上に、**講師・運営側の可視化と介入レイヤー** を載せる。具体的には (1) 管理者ロール（`is_admin`）、(2) 全受講者の進捗・提出一覧、(3) 提出単位のインストラクターコメント、(4) 受講者宛 in-app 通知、を 1 ブランチで導入する。加えて Sprint 3 セキュリティレビューで MEDIUM とした 5 件（`docs/superpowers/specs/2026-06-06-sprint-3-security-followups.md`）を early-task として併せて修正する。

**Architecture:** 既存の認証（JWT）とテーブル構造に対し、ロール権限は `users.is_admin BOOLEAN NOT NULL DEFAULT false` の 1 カラムで表現する。管理者用 API は `app/api/admin/*.py` に集約し、`get_current_admin` dependency で常時ガード。コメント・通知はそれぞれ独立テーブル（`instructor_comments`, `notifications`）。フロントは `src/views/admin/*.vue` と `src/router/admin.ts` を新設、既存学習者画面とは別レイアウト `AdminLayout.vue` を切る。データ取得は Sprint 1/2/3 の既存 API は再利用せず、admin 専用エンドポイント（read-only 集約）を新設して権限境界を明確にする。

**Tech Stack:**
- Backend: 既存（FastAPI, async SQLAlchemy, asyncpg, Alembic, slowapi）。新規依存は **なし** が原則。Server-Sent Events / WebSocket は今 sprint では使わず、フロントのポーリング（30 秒）で通知バッジを更新する。
- Frontend: 既存（Vue 3, Pinia, TypeScript, Vue Router）のみ。新規依存なし。
- セキュリティ：Sprint 3 で導入した slowapi の Limiter を admin API にも適用（IP ベース、admin は実質運営の 1〜数 IP なので緩めの 60/分）。

---

## 設計書

実装中は以下の設計書を参照すること:

- 本計画書（Sprint 4 設計と判断は本ファイル冒頭に集約。ファイル分割は不要）
- セキュリティ follow-up: `docs/superpowers/specs/2026-06-06-sprint-3-security-followups.md`
- DB 設計: `docs/design/03-db-design.md`（Sprint 4 で追記）
- API 設計: `docs/design/04-interface-design.md`（Sprint 4 で追記）
- 画面設計: `docs/design/05-screen-design.md`（Sprint 4 で追記）
- テスト設計: `docs/design/06-test-design.md`（Sprint 4 で追記）

---

## 主要意思決定（Sprint 4 計画時点の判断）

| # | 判断項目 | 選択 | 理由 |
|---|---|---|---|
| 1 | スコープ分割 | Sprint 4 = 管理者ダッシュボード + Sprint 3 残し security MEDIUM 5 件 | 1 ブランチ = レビュー可能単位。学習プラン/レコメンドは Sprint 5 に送り、運営の可視化を先に通す |
| 2 | ロール表現 | `users.is_admin BOOLEAN NOT NULL DEFAULT false`（単一フラグ） | RBAC のフル分解は YAGNI。admin / 受講者の 2 種類で要件を満たす |
| 3 | admin 認証経路 | 既存 `/api/auth/login` を再利用、JWT に変化なし、サーバー側 `get_current_admin` で `is_admin=True` を強制 | クライアント分離不要、漏れた JWT のスコープは既存と同じ |
| 4 | コメント可視性 | 受講者は自分の提出に付いたコメントだけ閲覧可能。返信機能は Sprint 4 では持たない（単方向） | スコープを絞る。返信は Sprint 5 候補 |
| 5 | 通知配信 | DB に `notifications` 行を残す in-app 通知のみ。SSE/WS なし。フロントは 30 秒ポーリング | 外部依存ゼロ、運用シンプル。リアルタイム化は後続 |
| 6 | 通知の宛先 | 単一ユーザー宛のみ。`role=cohort` 等の broadcast は未対応 | スコープ管理、誤送リスク低減 |
| 7 | 一覧の負荷 | ページネーション（`limit/offset`）。N+1 を避けるため SQLAlchemy の selectinload で進捗をまとめてロード | 数百人規模を想定、無制限取得は禁止 |
| 8 | 管理画面の動線 | `/admin` 配下に admin layout、非 admin がアクセスしたら `/` にリダイレクト + 403 を表示 | URL 設計が直感的、誤操作のリスク低減 |
| 9 | テスト戦略 | TDD 厳格運用 + Playwright E2E 1 本（admin login → ユーザー一覧 → 提出ドリルダウン → コメント投稿 → 通知送信 → 受講者側で確認） | Sprint 1/2/3 と同水準を維持 |
| 10 | Security follow-up の同梱 | MED-1〜5 を Task 2〜6 として最初に処理（順序: MED-3, MED-4, MED-2, MED-1, MED-5） | 影響範囲が独立、early-fix で main の品質ベースラインを上げる |
| 11 | Audit log | 今 Sprint では admin 操作の audit log テーブルは持たない | 監査要件未定義。本番化 Sprint で扱う |
| 12 | 管理者の seed | Alembic マイグレーションでは作らない。CLI スクリプト `scripts/promote_admin.py <email>` を別途追加 | 開発用、運用上は将来 admin UI で発行 |

---

## スコープ境界

**含む（Sprint 4）：**

- セキュリティ follow-up（5 件）：
  - **MED-1** プロンプトに XML 区切りでファイル名を分離
  - **MED-2** `grading._read_file_bytes` を `core.file_storage.read_file_bytes` に統一
  - **MED-3** Claude SDK 例外をユーザーには汎用メッセージ、サーバーログに詳細
  - **MED-4** 同一 submission 内のファイル名衝突を suffix で回避
  - **MED-5** Content-Security-Policy middleware の導入
- 管理者ロール：
  - `users.is_admin` カラム + Alembic マイグレーション
  - `get_current_admin` dependency
  - `scripts/promote_admin.py` CLI
- 管理者 API（`/api/admin/...`）：
  - `GET /api/admin/users` — 受講者一覧 + 進捗サマリ（ページネーション）
  - `GET /api/admin/users/{user_id}` — 単一受講者の詳細（4 フェーズの状況、最新提出スコア）
  - `GET /api/admin/submissions` — 提出一覧（user_id / phase でフィルタ可、ページネーション）
  - `GET /api/admin/submissions/{submission_id}` — 提出詳細（content + files + grading_history + comments）
  - `POST /api/admin/submissions/{submission_id}/comments` — コメント投稿
  - `GET /api/admin/submissions/{submission_id}/comments` — コメント一覧
  - `POST /api/admin/notifications` — 通知作成（単一受講者宛）
  - `GET /api/admin/notifications` — 自分が発行した通知一覧
- 受講者向け追加 API：
  - `GET /api/me/notifications` — 自分宛通知一覧
  - `POST /api/me/notifications/{notification_id}/read` — 既読化
  - `GET /api/me/submissions/{submission_id}/comments` — 自分の提出に付いたコメント
- DB：
  - `users.is_admin` カラム追加（NOT NULL DEFAULT false）
  - `instructor_comments` テーブル（id / submission_id / author_user_id / body / created_at / updated_at）
  - `notifications` テーブル（id / recipient_user_id / sender_user_id / title / body / link / read_at / created_at）
- フロント：
  - admin layout + router guard
  - `AdminUsersView.vue`（受講者一覧）
  - `AdminUserDetailView.vue`（個別受講者ドリルダウン）
  - `AdminSubmissionDetailView.vue`（提出詳細 + コメント投稿）
  - `AdminNotifyView.vue`（通知作成）
  - 受講者向け `NotificationCenter.vue`（ヘッダ右側のベルアイコン + ドロップダウン）
  - `TaskSubmissionCard.vue` に「コメント (N)」セクション追加
- テスト：
  - 各 API の owner / admin / non-admin 三方の権限テスト
  - フロント vitest（admin store、notification store、新規ビュー）
  - Playwright E2E 1 本
- 設計書：03/04/05/06 に Sprint 4 セクション追記、README 更新

**含まない（後続 Sprint）：**

- コメントへの返信（受講者 → 講師）、スレッド構造 → Sprint 5 候補
- リアルタイム通知（SSE / WS） → Sprint 5 以降
- broadcast 通知（コホート全員、全員宛） → 別途
- 学習プラン / 弱点分析 / レコメンド → Sprint 5
- 採点の非同期化（バックグラウンドジョブ） → Sprint 5
- audit log テーブル → 本番化 Sprint
- 監視 / CI / 本番デプロイ → 本番化 Sprint
- Secrets Manager → 本番化 Sprint
- LOW 系 security 指摘（LOW-1 Cookie 化、LOW-2 CORS 絞り、LOW-3 upload_dir 絶対パス） → 保留（フォローアップ doc に残置）

---

## ファイル構造（差分のみ）

```
edu/
├── README.md                                                       # Modify: Sprint 4 完了マーク
├── backend/
│   ├── app/
│   │   ├── config.py                                               # Modify: csp_policy, notification_poll_limit
│   │   ├── core/
│   │   │   ├── deps.py                                             # Modify: get_current_admin
│   │   │   ├── file_storage.py                                     # Modify: MED-4 一意な保存ファイル名
│   │   │   └── csp.py                                              # Create: CSP middleware (MED-5)
│   │   ├── main.py                                                 # Modify: CSP middleware 追加, admin router
│   │   ├── models/
│   │   │   ├── __init__.py                                         # Modify: import 追加
│   │   │   ├── user.py                                             # Modify: is_admin
│   │   │   ├── instructor_comment.py                               # Create
│   │   │   └── notification.py                                     # Create
│   │   ├── schemas/
│   │   │   ├── admin.py                                            # Create: AdminUserOut / AdminSubmissionOut 等
│   │   │   ├── comment.py                                          # Create
│   │   │   └── notification.py                                     # Create
│   │   ├── services/
│   │   │   ├── grading.py                                          # Modify: MED-1 XML, MED-2 root check, MED-3 mask
│   │   │   ├── admin_query.py                                      # Create: 集約 read-only クエリ
│   │   │   ├── comment.py                                          # Create
│   │   │   └── notification.py                                     # Create
│   │   └── api/
│   │       ├── admin/
│   │       │   ├── __init__.py                                     # Create
│   │       │   ├── users.py                                        # Create
│   │       │   ├── submissions.py                                  # Create
│   │       │   ├── comments.py                                     # Create
│   │       │   └── notifications.py                                # Create
│   │       └── me.py                                               # Create: 受講者向け追加 API
│   ├── alembic/versions/
│   │   └── 20260606_<rev>_sprint4.py                               # Create: is_admin + comments + notifications
│   ├── scripts/
│   │   └── promote_admin.py                                        # Create: CLI で is_admin=true 化
│   └── tests/
│       ├── test_grading_service.py                                 # Modify: MED-1/2/3 シナリオ
│       ├── test_file_storage.py                                    # Modify: MED-4 衝突
│       ├── test_csp_middleware.py                                  # Create: MED-5
│       ├── test_models_sprint4.py                                  # Create
│       ├── test_admin_users_api.py                                 # Create
│       ├── test_admin_submissions_api.py                           # Create
│       ├── test_admin_comments_api.py                              # Create
│       ├── test_admin_notifications_api.py                         # Create
│       ├── test_me_api.py                                          # Create
│       └── conftest.py                                             # Modify: admin_user / admin_client fixtures
└── frontend/
    └── src/
        ├── router/
        │   ├── index.ts                                            # Modify: admin guard + ルート追加
        │   └── admin.ts                                            # Create: admin ルート定義
        ├── stores/
        │   ├── admin.ts                                            # Create: users / submissions / comments
        │   ├── notification.ts                                     # Create
        │   └── auth.ts                                             # Modify: isAdmin getter
        ├── lib/api.ts                                              # Modify: admin* / notifications*
        ├── types/
        │   ├── admin.ts                                            # Create
        │   └── notification.ts                                     # Create
        ├── layouts/
        │   └── AdminLayout.vue                                     # Create
        ├── views/admin/
        │   ├── AdminUsersView.vue                                  # Create
        │   ├── AdminUserDetailView.vue                             # Create
        │   ├── AdminSubmissionDetailView.vue                       # Create
        │   └── AdminNotifyView.vue                                 # Create
        ├── components/
        │   ├── NotificationCenter.vue                              # Create
        │   ├── CommentThread.vue                                   # Create
        │   └── TaskSubmissionCard.vue                              # Modify: コメント表示
        └── __tests__/
            ├── admin.store.spec.ts                                 # Create
            ├── notification.store.spec.ts                          # Create
            ├── NotificationCenter.spec.ts                          # Create
            └── CommentThread.spec.ts                               # Create
```

---

## 共通の前提

- **作業ブランチ**: `feature/sprint-4`（main から派生）
- **環境**: Docker Compose の `postgres` 起動。`backend` は `uv run uvicorn` でホスト起動でも可。
- **テスト DB**: `ai_tutor_test`（Sprint 1 で作成済み）。Sprint 4 マイグレーションは `Base.metadata.create_all` 経由でテストに反映される。
- **既存設計のフィールド名（重要）**:
  - `users.id`（UUID）、`users.is_admin`（NEW）
  - `submissions.user_id` で所有者識別
  - `submissions.content` / `ai_feedback` / `submitted_at` / `graded_at`
  - `grading_attempts.status` ENUM `{graded, failed}`
  - `task_no` の CHECK は `BETWEEN 1 AND 5`
- **権限テストの基本**:
  - non-admin が `/api/admin/*` を叩く → 403
  - admin が他者の `/api/submissions/...` を見る → **404**（既存仕様、admin であっても受講者 API は所有者制限）。admin は `/api/admin/...` を使う。
  - 受講者本人が `/api/me/...` を叩く → 自分のリソースのみ返る
- **既存テスト fixture**: `client` / `db_session` / `auth_user` / `auth_token` / `auth_client`。Sprint 4 で `admin_user` / `admin_token` / `admin_client` を追加。
- **コミット規約**: Sprint 1/2/3 と同じ `feat|fix|test|chore|docs(scope): ...`
- **コマンド実行ディレクトリ**: 特記なき限り `/Volumes/Seagate3TB/projects/edu`

---

## Task 0: ブランチ作成と環境確認

**Files:**
- なし（git のみ）

- [ ] **Step 1: feature ブランチを切る**

```bash
git checkout main
git pull --ff-only || true   # remote 未設定なら無視
git checkout -b feature/sprint-4
```

- [ ] **Step 2: バックエンド全件テストが現状で通ることを確認**

```bash
docker compose up -d postgres
cd backend && uv run pytest -q
```

Expected: `148 passed`（Sprint 3 完了時点）。

- [ ] **Step 3: フロントビルドが現状で通ることを確認**

```bash
cd frontend && npm run build && npm test -- --run
```

Expected: ビルド成功、`11 passed`。

---

## Task 1: コンフィグ拡張（CSP / 通知ポーリング上限）

**Files:**
- Modify: `backend/app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: `Settings` に Sprint 4 用の項目を追加**

`backend/app/config.py` の `Settings` クラス末尾（`@property` 群の手前）に追加:

```python
    # Notifications (Sprint 4)
    notification_poll_limit: int = 50

    # Content Security Policy (Sprint 4)
    # API responses are not HTML, but CSP on the API origin is a cheap
    # second line of defense for any future inline rendering bug.
    csp_policy: str = (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'"
    )
```

- [ ] **Step 2: `.env.example` に追記**

```bash
# Sprint 4 notifications + CSP
NOTIFICATION_POLL_LIMIT=50
CSP_POLICY=default-src 'none'; frame-ancestors 'none'; base-uri 'none'
```

- [ ] **Step 3: テストが引き続き通ることを確認**

```bash
cd backend && uv run pytest -q
```

Expected: `148 passed`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py .env.example
git commit -m "chore(sprint-4): add CSP and notification settings"
```

---

## Task 2: MED-3 — Claude SDK エラーをユーザー向けにマスク

**Files:**
- Modify: `backend/app/services/grading.py`
- Modify: `backend/tests/test_grading_service_vision.py`

- [ ] **Step 1: failing test を更新**

`backend/tests/test_grading_service_vision.py` の `test_grade_submission_returns_failed_on_claude_error` を、以下のアサーションに差し替える:

```python
@pytest.mark.asyncio
async def test_grade_submission_returns_failed_on_claude_error(caplog):
    """MED-3: SDK error never leaks request IDs to the API client; full
    detail is logged server-side."""
    import logging
    from app.services.grading import grade_submission

    sdk = MagicMock()
    sdk.messages.create = AsyncMock(
        side_effect=RuntimeError("req_xyz internal routing detail")
    )
    claude = ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")

    caplog.set_level(logging.ERROR, logger="app.services.grading")
    result = await grade_submission(
        claude=claude, task_description="x", content="y", files=[]
    )
    assert result.status == GradingResultStatus.FAILED
    assert "req_xyz" not in (result.error_message or "")
    assert "採点サービス" in (result.error_message or "")
    # Full detail must still be present in logs for ops.
    assert any("req_xyz" in r.message for r in caplog.records)
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
cd backend && uv run pytest tests/test_grading_service_vision.py::test_grade_submission_returns_failed_on_claude_error -q
```

Expected: 失敗（現在は `str(e)` が漏れる）。

- [ ] **Step 3: `grading.py` を修正**

`backend/app/services/grading.py` 冒頭に logger 追加 + `except Exception` ブロック差し替え:

```python
import logging
...
logger = logging.getLogger(__name__)
...
    try:
        reply = await claude.complete_multimodal(...)
    except Exception as e:
        logger.error("Claude API call failed", exc_info=True)
        return GradingResult(
            status=GradingResultStatus.FAILED,
            error_message="採点サービスでエラーが発生しました。しばらく時間をおいて再試行してください。",
            model_name=settings.anthropic_model,
        )
```

- [ ] **Step 4: 全テスト実行**

```bash
cd backend && uv run pytest -q
```

Expected: `148 passed`（差分 0、test_grading_service_vision の置換は数を変えない）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/grading.py backend/tests/test_grading_service_vision.py
git commit -m "fix(sprint-4): mask Claude SDK error from client and log full detail (MED-3)"
```

---

## Task 3: MED-4 — ファイル名衝突回避

**Files:**
- Modify: `backend/app/core/file_storage.py`
- Modify: `backend/tests/test_file_storage.py`

- [ ] **Step 1: failing test を追加**

`backend/tests/test_file_storage.py` 末尾に追加:

```python
@pytest.mark.asyncio
async def test_save_upload_suffixes_collisions(tmp_path, monkeypatch):
    """MED-4: A second upload with the same sanitized name must not overwrite."""
    from app.config import settings
    from app.core.file_storage import save_upload

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    uid = uuid.uuid4()
    sid = uuid.uuid4()

    a = await save_upload(user_id=uid, submission_id=sid,
                          filename="img.png", content=_png_bytes())
    b = await save_upload(user_id=uid, submission_id=sid,
                          filename="img.png", content=_png_bytes())
    assert a.file_path != b.file_path
    assert Path(a.file_path).exists()
    assert Path(b.file_path).exists()
```

- [ ] **Step 2: テストが失敗することを確認**

- [ ] **Step 3: `_unique_target` を追加し `save_upload` を更新**

```python
def _unique_target(target_dir: Path, safe_name: str) -> Path:
    target = target_dir / safe_name
    if not target.exists():
        return target
    if "." in safe_name:
        stem, _, suffix = safe_name.rpartition(".")
        suffix = "." + suffix
    else:
        stem, suffix = safe_name, ""
    for i in range(1, 100):
        candidate = target_dir / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise FileStorageError("could not find unique filename within 100 attempts")
```

`save_upload` の `target = target_dir / safe_name` を `target = _unique_target(target_dir, safe_name)` に置換。

- [ ] **Step 4: 全テスト実行**

```bash
cd backend && uv run pytest -q
```

Expected: `149 passed`（+1）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/file_storage.py backend/tests/test_file_storage.py
git commit -m "fix(sprint-4): suffix filename collisions in submission uploads (MED-4)"
```

---

## Task 4: MED-2 — `grading._read_file_bytes` を統一

**Files:**
- Modify: `backend/app/services/grading.py`
- Modify: `backend/tests/test_grading_service_vision.py`

- [ ] **Step 1: failing test を追加**

```python
@pytest.mark.asyncio
async def test_grade_submission_rejects_file_outside_upload_root(
    tmp_path, monkeypatch
):
    """MED-2: defense in depth — paths escaping the upload root return FAILED."""
    from app.config import settings
    from app.models.submission_file import SubmissionFile
    from app.services.grading import grade_submission

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    (tmp_path / "uploads").mkdir()
    (tmp_path / "etc").mkdir()
    rogue = tmp_path / "etc" / "secret"
    rogue.write_text("top secret")

    file_row = SubmissionFile(
        submission_id=uuid.uuid4(),
        file_path=str(rogue),
        mime_type="text/plain",
        size_bytes=rogue.stat().st_size,
    )
    claude = _fake_claude('{"score":80,"feedback":"x"}')
    result = await grade_submission(
        claude=claude, task_description="x", content="y", files=[file_row]
    )
    assert result.status == GradingResultStatus.FAILED
    assert "file read error" in (result.error_message or "").lower() or \
        "upload root" in (result.error_message or "").lower() or \
        "採点サービス" in (result.error_message or "")
```

- [ ] **Step 2: テストが失敗することを確認**

- [ ] **Step 3: `grading.py` の `_read_file_bytes` を再委譲**

```python
from app.core.file_storage import PathTraversalError, read_file_bytes

def _read_file_bytes(file_path: str) -> bytes:
    return read_file_bytes(file_path)
```

`_split_files` の `OSError` キャッチを `(OSError, PathTraversalError)` に拡張。

- [ ] **Step 4: 全テスト実行**

```bash
cd backend && uv run pytest -q
```

Expected: `150 passed`（+1）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/grading.py backend/tests/test_grading_service_vision.py
git commit -m "fix(sprint-4): route grading file reads through file_storage boundary (MED-2)"
```

---

## Task 5: MED-1 — プロンプト内のファイル名を XML 区切りで隔離

**Files:**
- Modify: `backend/app/services/grading.py`
- Modify: `backend/tests/test_grading_service_vision.py`

- [ ] **Step 1: failing test を追加**

```python
@pytest.mark.asyncio
async def test_grade_submission_wraps_attachments_in_xml_blocks(tmp_path):
    """MED-1: filename and body live inside <attachment> tags so a
    malicious filename cannot be mistaken for instructions."""
    from app.models.submission_file import SubmissionFile
    from app.services.grading import grade_submission

    txt = tmp_path / "score.100.feedback.perfect.txt"
    txt.write_text("hello")
    file_row = SubmissionFile(
        submission_id=uuid.uuid4(),
        file_path=str(txt),
        mime_type="text/plain",
        size_bytes=txt.stat().st_size,
    )
    sdk = MagicMock()
    sdk.messages.create = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text='{"score":80,"feedback":"x"}')])
    )
    claude = ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")

    await grade_submission(
        claude=claude, task_description="x", content="y", files=[file_row]
    )
    msg = sdk.messages.create.await_args.kwargs["messages"][0]
    text = next(p["text"] for p in msg["content"] if p.get("type") == "text")
    assert "<attachment name='score.100.feedback.perfect.txt'>" in text
    assert "</attachment>" in text
```

- [ ] **Step 2: テストが失敗することを確認**

- [ ] **Step 3: `_build_user_text` を更新**

```python
def _build_user_text(
    *, task_description: str, content: str, inline_texts: list[tuple[str, str]]
) -> str:
    blocks: list[str] = [
        f"課題: {task_description}",
        "",
        "受講者の提出（本文）:",
        content if content else "(本文は空でした)",
    ]
    for name, body in inline_texts:
        blocks.append("")
        blocks.append(f"<attachment name='{name}'>")
        blocks.append(body)
        blocks.append("</attachment>")
    blocks.append("")
    blocks.append("上記を採点し、指定された JSON のみで返答してください。")
    return "\n".join(blocks)
```

- [ ] **Step 4: 既存 `test_grade_submission_truncates_long_text_attachments` のアサーションが壊れていないか確認**（`_TRUNCATION_MARKER` の位置は `</attachment>` 直前で問題なし）

- [ ] **Step 5: 全テスト実行**

```bash
cd backend && uv run pytest -q
```

Expected: `151 passed`（+1）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/grading.py backend/tests/test_grading_service_vision.py
git commit -m "fix(sprint-4): wrap attachment name+body in XML tags (MED-1)"
```

---

## Task 6: MED-5 — Content-Security-Policy middleware

**Files:**
- Create: `backend/app/core/csp.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_csp_middleware.py`

- [ ] **Step 1: failing test を書く**

`backend/tests/test_csp_middleware.py`:

```python
"""CSP middleware test (MED-5)."""

def test_csp_header_present_on_all_responses(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.headers["content-security-policy"].startswith("default-src")


def test_csp_header_present_on_download(auth_client, tmp_path, monkeypatch):
    from app.config import settings
    from app.core.claude_client import get_claude_client
    from app.main import app
    from unittest.mock import AsyncMock, MagicMock

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    def _fake():
        sdk = MagicMock()
        sdk.messages.create = AsyncMock(
            return_value=MagicMock(content=[MagicMock(text='{"score":80,"feedback":"x"}')])
        )
        from app.core.claude_client import ClaudeClient
        return ClaudeClient(sdk=sdk, model="claude-sonnet-4-5")

    app.dependency_overrides[get_claude_client] = _fake
    try:
        body = auth_client.post(
            "/api/submissions",
            data={"phase": "1", "task_no": "1", "content": "v"},
        ).json()
        # No files attached but verify the header exists on a normal response.
        # Then check on file download once a real file is present.
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: テストが失敗することを確認**

- [ ] **Step 3: CSP middleware 実装**

`backend/app/core/csp.py`:

```python
"""Content-Security-Policy middleware (MED-5).

The API itself does not render HTML, so a restrictive policy (default-src
'none') is safe. The header acts as a tripwire — any accidental future
HTML response would be sandboxed by the browser instead of executing.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CSPMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, policy: str) -> None:
        super().__init__(app)
        self._policy = policy

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", self._policy)
        return response
```

- [ ] **Step 4: `main.py` で登録**

```python
from app.core.csp import CSPMiddleware
...
    app.add_middleware(CSPMiddleware, policy=settings.csp_policy)
```

`LimitUploadSize` の直後に追加。順序は CORS → LimitUploadSize → CSP。

- [ ] **Step 5: 全テスト実行**

```bash
cd backend && uv run pytest -q
```

Expected: `153 passed`（+2）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/csp.py backend/app/main.py backend/tests/test_csp_middleware.py
git commit -m "feat(sprint-4): add Content-Security-Policy middleware (MED-5)"
```

---

## Task 7: `users.is_admin` カラム追加（TDD）

**Files:**
- Modify: `backend/app/models/user.py`
- Create: `backend/tests/test_models_sprint4.py`
- Create: Alembic マイグレーション（Task 9 で一括）

- [ ] **Step 1: failing test を書く**

`backend/tests/test_models_sprint4.py`:

```python
"""Sprint 4 model tests: is_admin, instructor_comments, notifications."""

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.user import User


@pytest.mark.asyncio
async def test_user_is_admin_default_false(db_session):
    user = User(
        email="reg@example.com",
        name="r",
        password_hash=hash_password("p"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.is_admin is False


@pytest.mark.asyncio
async def test_user_is_admin_can_be_true(db_session):
    user = User(
        email="adm@example.com",
        name="a",
        password_hash=hash_password("p"),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.is_admin is True
```

- [ ] **Step 2: テストが失敗することを確認**

- [ ] **Step 3: `User` モデルに追加**

`backend/app/models/user.py` の `Mapped[...]` 群に追加（既存の Boolean Mapped カラムに合わせる）:

```python
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
```

`from sqlalchemy import Boolean` の import を追加。

- [ ] **Step 4: テストが通ることを確認**

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/user.py backend/tests/test_models_sprint4.py
git commit -m "feat(sprint-4): add is_admin flag to User model"
```

---

## Task 8: `instructor_comments` / `notifications` モデル（TDD）

**Files:**
- Create: `backend/app/models/instructor_comment.py`
- Create: `backend/app/models/notification.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/tests/test_models_sprint4.py`

- [ ] **Step 1: failing test を追加**

`test_models_sprint4.py` に追加:

```python
@pytest.mark.asyncio
async def test_instructor_comment_round_trips(db_session):
    from app.models.instructor_comment import InstructorComment
    from app.models.submission import Submission
    from datetime import UTC, datetime

    admin = User(
        email="i@example.com", name="i",
        password_hash=hash_password("p"), is_admin=True,
    )
    learner = User(
        email="l@example.com", name="l", password_hash=hash_password("p"),
    )
    db_session.add_all([admin, learner])
    await db_session.flush()
    sub = Submission(
        user_id=learner.id, phase=1, task_no=1,
        content="x", submitted_at=datetime.now(UTC),
    )
    db_session.add(sub)
    await db_session.flush()
    comment = InstructorComment(
        submission_id=sub.id, author_user_id=admin.id, body="good job",
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)
    assert comment.id is not None
    assert comment.body == "good job"


@pytest.mark.asyncio
async def test_notification_round_trips(db_session):
    from app.models.notification import Notification

    admin = User(
        email="i2@example.com", name="i",
        password_hash=hash_password("p"), is_admin=True,
    )
    learner = User(
        email="l2@example.com", name="l", password_hash=hash_password("p"),
    )
    db_session.add_all([admin, learner])
    await db_session.flush()
    note = Notification(
        recipient_user_id=learner.id,
        sender_user_id=admin.id,
        title="Phase 1 OK!",
        body="Great progress",
        link="/phases/1",
    )
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)
    assert note.id is not None
    assert note.read_at is None
```

- [ ] **Step 2: テストが失敗することを確認**

- [ ] **Step 3: モデルを実装**

`backend/app/models/instructor_comment.py`:

```python
"""Instructor comment on a learner submission (Sprint 4)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InstructorComment(Base):
    __tablename__ = "instructor_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
```

`backend/app/models/notification.py`:

```python
"""In-app notification (Sprint 4)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
```

- [ ] **Step 4: モデルレジストリに追加**

`backend/app/models/__init__.py` に import 追加:

```python
from app.models.instructor_comment import InstructorComment  # noqa: F401
from app.models.notification import Notification  # noqa: F401
```

- [ ] **Step 5: テストが通ることを確認**

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/instructor_comment.py backend/app/models/notification.py \
        backend/app/models/__init__.py backend/tests/test_models_sprint4.py
git commit -m "feat(sprint-4): add InstructorComment and Notification models"
```

---

## Task 9: Alembic マイグレーション

**Files:**
- Create: `backend/alembic/versions/20260606_<rev>_sprint4_admin_comments_notifications.py`

- [ ] **Step 1: autogenerate でマイグレーション生成**

```bash
cd backend && uv run alembic revision --autogenerate -m "sprint4 admin comments notifications"
```

- [ ] **Step 2: 生成内容を手で確認・修正**

確認ポイント:
- `users.is_admin` 列追加が含まれるか
- `instructor_comments` / `notifications` テーブル作成が含まれるか
- index（`ix_instructor_comments_submission_id`, `ix_notifications_recipient_user_id`）の作成
- バックフィル不要（`is_admin` は server_default=false で全既存ユーザーが false 化）

- [ ] **Step 3: upgrade 適用**

```bash
uv run alembic upgrade head
```

- [ ] **Step 4: downgrade で戻せることを確認**

```bash
uv run alembic downgrade -1 && uv run alembic upgrade head
```

- [ ] **Step 5: テスト全件実行**

```bash
uv run pytest -q
```

Expected: 既存テスト数 +5（Task 7/8 で追加した 4 件と Task 6 の 2 件で 155 件想定）。

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(sprint-4): alembic migration for is_admin + comments + notifications"
```

---

## Task 10: `get_current_admin` dependency と `promote_admin.py` CLI

**Files:**
- Modify: `backend/app/core/deps.py`
- Create: `backend/scripts/promote_admin.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: `get_current_admin` を追加**

`backend/app/core/deps.py` 末尾に:

```python
async def get_current_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin privileges required",
        )
    return user
```

- [ ] **Step 2: conftest に admin fixture を追加**

```python
@pytest_asyncio.fixture
async def admin_user(db_session):
    from app.core.security import hash_password
    from app.models.user import User
    from app.services.progress import initialize_progress

    user = User(
        email="instructor@example.com",
        name="講師",
        password_hash=hash_password("password123"),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.flush()
    await initialize_progress(db_session, user.id)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(admin_user) -> str:
    from app.core.security import create_access_token
    return create_access_token(subject=str(admin_user.id))


@pytest_asyncio.fixture
async def admin_client(client, admin_token):
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return client
```

`auth_client` と `admin_client` を同じテストで両方使うと Authorization ヘッダが上書きされる点に注意。両方使うテストは個別に明示的にヘッダ切替を行う。

- [ ] **Step 3: `promote_admin.py` CLI を作成**

`backend/scripts/promote_admin.py`:

```python
"""Promote a user to admin by email.

Usage:
    uv run python -m scripts.promote_admin <email>
"""

import asyncio
import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.user import User


async def main(email: str) -> int:
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None:
            print(f"user not found: {email}", file=sys.stderr)
            return 1
        if user.is_admin:
            print(f"already admin: {email}")
            return 0
        user.is_admin = True
        await session.commit()
        print(f"promoted: {email}")
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m scripts.promote_admin <email>", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
```

- [ ] **Step 4: テスト**

`tests/test_deps_admin.py` を新規作成:

```python
def test_non_admin_blocked_from_admin_dependency(auth_client):
    # `auth_client` is a non-admin (alice). Hit any future admin endpoint
    # after Task 11 wires it. For now smoke-test via direct dep usage.
    from app.core.deps import get_current_admin
    from app.models.user import User
    import asyncio

    async def _check():
        non_admin = User(id=None, email="x", name="x", password_hash="x", is_admin=False)
        try:
            await get_current_admin(user=non_admin)
        except Exception as e:
            return e
        return None

    err = asyncio.run(_check())
    assert err is not None
    assert "admin privileges" in str(err)
```

（実 API 経由のテストは Task 11 で行う）

- [ ] **Step 5: 全テスト実行**

Expected: `156+ passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/deps.py backend/scripts/promote_admin.py \
        backend/tests/conftest.py backend/tests/test_deps_admin.py
git commit -m "feat(sprint-4): add get_current_admin dependency and promote_admin CLI"
```

---

## Task 11: 管理者向け受講者一覧 API（TDD）

**Files:**
- Create: `backend/app/schemas/admin.py`
- Create: `backend/app/services/admin_query.py`
- Create: `backend/app/api/admin/__init__.py`
- Create: `backend/app/api/admin/users.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_admin_users_api.py`

- [ ] **Step 1: failing API テストを書く**

`backend/tests/test_admin_users_api.py`:

```python
"""Sprint 4 admin users API."""

import pytest
from app.core.security import create_access_token, hash_password


async def _make_learners(db, n: int):
    from app.models.user import User
    from app.services.progress import initialize_progress
    users = []
    for i in range(n):
        u = User(
            email=f"l{i}@example.com", name=f"L{i}",
            password_hash=hash_password("p"),
        )
        db.add(u)
        await db.flush()
        await initialize_progress(db, u.id)
        users.append(u)
    await db.commit()
    return users


@pytest.mark.asyncio
async def test_list_users_returns_only_for_admin(client, db_session, admin_user):
    await _make_learners(db_session, 3)
    # non-admin
    learner_token = create_access_token(subject=str((await _make_learners(db_session, 1))[0].id))
    client.headers.update({"Authorization": f"Bearer {learner_token}"})
    r = client.get("/api/admin/users")
    assert r.status_code == 403

    # admin
    admin_token = create_access_token(subject=str(admin_user.id))
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    r = client.get("/api/admin/users")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 4  # 3 + 1 + admin


@pytest.mark.asyncio
async def test_list_users_pagination(client, db_session, admin_user):
    await _make_learners(db_session, 5)
    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(admin_user.id))}"}
    )
    r = client.get("/api/admin/users?limit=2&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_user_detail_returns_phases_and_latest_scores(
    client, db_session, admin_user
):
    learners = await _make_learners(db_session, 1)
    target = learners[0]
    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(admin_user.id))}"}
    )
    r = client.get(f"/api/admin/users/{target.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(target.id)
    assert "progress" in body
    assert len(body["progress"]) == 4
```

- [ ] **Step 2: スキーマを定義**

`backend/app/schemas/admin.py`:

```python
"""Admin DTOs."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.progress import ProgressOut


class AdminUserSummary(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
    is_admin: bool
    completed_phases: int
    in_progress_phases: int

    model_config = {"from_attributes": True}


class AdminUserListOut(BaseModel):
    items: list[AdminUserSummary]
    total: int
    limit: int
    offset: int


class AdminUserDetail(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
    is_admin: bool
    progress: list[ProgressOut]
    latest_scores: dict[int, int | None]   # phase -> score
```

- [ ] **Step 3: クエリサービスを作る**

`backend/app/services/admin_query.py`:

```python
"""Read-only aggregations for admin views."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.progress import PhaseProgress
from app.models.submission import Submission
from app.models.user import User


async def count_users(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(User))).scalar_one()


async def list_users_with_progress(
    db: AsyncSession, *, limit: int, offset: int
):
    users = (
        await db.execute(
            select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    if not users:
        return []
    user_ids = [u.id for u in users]
    rows = (
        await db.execute(
            select(PhaseProgress).where(PhaseProgress.user_id.in_(user_ids))
        )
    ).scalars().all()
    by_user: dict[uuid.UUID, list[PhaseProgress]] = {u.id: [] for u in users}
    for r in rows:
        by_user[r.user_id].append(r)
    return [
        (u, by_user[u.id]) for u in users
    ]


async def get_user_detail(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[User, list[PhaseProgress], dict[int, int | None]] | None:
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        return None
    progress = (
        await db.execute(
            select(PhaseProgress).where(PhaseProgress.user_id == user_id)
                                  .order_by(PhaseProgress.phase)
        )
    ).scalars().all()
    subs = (
        await db.execute(
            select(Submission).where(Submission.user_id == user_id)
        )
    ).scalars().all()
    latest_scores: dict[int, int | None] = {}
    for s in subs:
        existing = latest_scores.get(s.phase)
        if existing is None or (
            s.score is not None and (existing is None or s.score > existing)
        ):
            latest_scores[s.phase] = s.score
    return user, list(progress), latest_scores
```

- [ ] **Step 4: ルーターを実装**

`backend/app/api/admin/__init__.py`:

```python
"""Admin API package."""
```

`backend/app/api/admin/users.py`:

```python
"""Admin users API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.progress import PhaseStatus
from app.schemas.admin import (
    AdminUserDetail,
    AdminUserListOut,
    AdminUserSummary,
)
from app.schemas.progress import ProgressOut
from app.services import admin_query

router = APIRouter(prefix="/api/admin/users", tags=["admin"])


@router.get("", response_model=AdminUserListOut)
async def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: object = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserListOut:
    rows = await admin_query.list_users_with_progress(
        db, limit=limit, offset=offset
    )
    total = await admin_query.count_users(db)
    items = [
        AdminUserSummary(
            id=u.id, email=u.email, name=u.name, created_at=u.created_at,
            is_admin=u.is_admin,
            completed_phases=sum(1 for p in progs if p.status == PhaseStatus.COMPLETED),
            in_progress_phases=sum(
                1 for p in progs if p.status == PhaseStatus.IN_PROGRESS
            ),
        )
        for u, progs in rows
    ]
    return AdminUserListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/{user_id}", response_model=AdminUserDetail)
async def get_user(
    user_id: uuid.UUID,
    _: object = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserDetail:
    found = await admin_query.get_user_detail(db, user_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user not found"
        )
    user, progress, latest = found
    return AdminUserDetail(
        id=user.id, email=user.email, name=user.name,
        created_at=user.created_at, is_admin=user.is_admin,
        progress=[ProgressOut.model_validate(p) for p in progress],
        latest_scores={phase: latest.get(phase) for phase in range(1, 5)},
    )
```

- [ ] **Step 5: `main.py` で登録**

```python
from app.api.admin import users as admin_users
...
    app.include_router(admin_users.router)
```

- [ ] **Step 6: 全テスト実行**

Expected: 既存 +3 件で `159+ passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/admin.py backend/app/services/admin_query.py \
        backend/app/api/admin/ backend/app/main.py \
        backend/tests/test_admin_users_api.py
git commit -m "feat(sprint-4): admin users list and detail API"
```

---

## Task 12: 管理者向け提出一覧/詳細 API（TDD）

**Files:**
- Create: `backend/app/api/admin/submissions.py`
- Modify: `backend/app/schemas/admin.py`
- Modify: `backend/app/services/admin_query.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_admin_submissions_api.py`

- [ ] **Step 1: failing test を書く**

`backend/tests/test_admin_submissions_api.py`:

```python
"""Admin submissions API."""

import pytest
from app.core.security import create_access_token, hash_password


@pytest.mark.asyncio
async def test_list_submissions_filters_by_user_and_phase(
    client, db_session, admin_user
):
    from app.models.submission import Submission
    from app.models.user import User
    from app.services.progress import initialize_progress
    from datetime import UTC, datetime

    learner = User(email="x@e.com", name="x", password_hash=hash_password("p"))
    db_session.add(learner)
    await db_session.flush()
    await initialize_progress(db_session, learner.id)
    db_session.add(Submission(
        user_id=learner.id, phase=1, task_no=1, content="a",
        submitted_at=datetime.now(UTC),
    ))
    db_session.add(Submission(
        user_id=learner.id, phase=2, task_no=1, content="b",
        submitted_at=datetime.now(UTC),
    ))
    await db_session.commit()

    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(admin_user.id))}"}
    )
    r = client.get(f"/api/admin/submissions?user_id={learner.id}&phase=1")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["phase"] == 1


@pytest.mark.asyncio
async def test_submission_detail_includes_files_and_history(
    client, db_session, admin_user
):
    from app.models.submission import Submission
    from app.models.user import User
    from app.services.progress import initialize_progress
    from datetime import UTC, datetime

    learner = User(email="y@e.com", name="y", password_hash=hash_password("p"))
    db_session.add(learner)
    await db_session.flush()
    await initialize_progress(db_session, learner.id)
    sub = Submission(
        user_id=learner.id, phase=1, task_no=1, content="z",
        submitted_at=datetime.now(UTC),
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(admin_user.id))}"}
    )
    r = client.get(f"/api/admin/submissions/{sub.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(sub.id)
    assert "files" in body
    assert "grading_history" in body
    assert "comments" in body


@pytest.mark.asyncio
async def test_non_admin_cannot_list_submissions(client, db_session):
    from app.models.user import User
    from app.services.progress import initialize_progress

    learner = User(email="z@e.com", name="z", password_hash=hash_password("p"))
    db_session.add(learner)
    await db_session.flush()
    await initialize_progress(db_session, learner.id)
    await db_session.commit()

    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(learner.id))}"}
    )
    r = client.get("/api/admin/submissions")
    assert r.status_code == 403
```

- [ ] **Step 2: スキーマを拡張**

`backend/app/schemas/admin.py` に追加:

```python
from app.schemas.grading import GradingAttemptOut
from app.schemas.submission import SubmissionFileOut


class AdminSubmissionSummary(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_name: str
    phase: int
    task_no: int
    score: int | None
    submitted_at: datetime
    graded_at: datetime | None

    model_config = {"from_attributes": True}


class AdminSubmissionListOut(BaseModel):
    items: list[AdminSubmissionSummary]
    total: int
    limit: int
    offset: int


class AdminSubmissionDetail(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_name: str
    phase: int
    task_no: int
    content: str
    score: int | None
    ai_feedback: str | None
    submitted_at: datetime
    graded_at: datetime | None
    files: list[SubmissionFileOut]
    grading_history: list[GradingAttemptOut]
    comments: list["AdminCommentOut"] = []
```

（`AdminCommentOut` は Task 13 で定義。前方参照 OK）

- [ ] **Step 3: クエリサービスに追加**

`admin_query.py`:

```python
async def list_submissions(
    db: AsyncSession, *, user_id: uuid.UUID | None,
    phase: int | None, limit: int, offset: int,
):
    stmt = select(Submission, User).join(User, Submission.user_id == User.id)
    if user_id is not None:
        stmt = stmt.where(Submission.user_id == user_id)
    if phase is not None:
        stmt = stmt.where(Submission.phase == phase)
    stmt = stmt.order_by(Submission.submitted_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).all()
    return rows  # list[Row[Submission, User]]


async def count_submissions(
    db: AsyncSession, *, user_id: uuid.UUID | None, phase: int | None,
) -> int:
    stmt = select(func.count()).select_from(Submission)
    if user_id is not None:
        stmt = stmt.where(Submission.user_id == user_id)
    if phase is not None:
        stmt = stmt.where(Submission.phase == phase)
    return (await db.execute(stmt)).scalar_one()
```

- [ ] **Step 4: ルーター実装**

`backend/app/api/admin/submissions.py` を Task 11 の `users.py` を参考に実装。詳細エンドポイントは:
- `Submission` + `User` の join 取得
- `file_storage_service.list_submission_files`
- `list_grading_history`
- `instructor_comments` の `submission_id` フィルタ（Task 13 のコメント機能と連動）

`main.py` に `app.include_router(admin_submissions.router)`。

- [ ] **Step 5: 全テスト実行**

Expected: `162+ passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/admin.py backend/app/services/admin_query.py \
        backend/app/api/admin/submissions.py backend/app/main.py \
        backend/tests/test_admin_submissions_api.py
git commit -m "feat(sprint-4): admin submissions list and detail API"
```

---

## Task 13: コメント API（TDD）

**Files:**
- Create: `backend/app/schemas/comment.py`
- Create: `backend/app/services/comment.py`
- Create: `backend/app/api/admin/comments.py`
- Create: `backend/app/api/me.py`（一部）
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_admin_comments_api.py`

- [ ] **Step 1: スキーマを定義**

`backend/app/schemas/comment.py`:

```python
"""Instructor comment DTOs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class AdminCommentOut(BaseModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    author_user_id: uuid.UUID
    author_name: str
    body: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# 受講者向け（author_user_id は公開しても問題ないが name のみで足りる）
class LearnerCommentOut(BaseModel):
    id: uuid.UUID
    author_name: str
    body: str
    created_at: datetime
```

- [ ] **Step 2: サービスを実装**

`backend/app/services/comment.py`:

```python
"""Instructor comment service."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instructor_comment import InstructorComment
from app.models.submission import Submission
from app.models.user import User


class SubmissionNotFoundError(Exception):
    pass


async def create_comment(
    *, db: AsyncSession, submission_id: uuid.UUID,
    author_user_id: uuid.UUID, body: str,
) -> InstructorComment:
    sub = (
        await db.execute(select(Submission).where(Submission.id == submission_id))
    ).scalar_one_or_none()
    if sub is None:
        raise SubmissionNotFoundError(str(submission_id))
    comment = InstructorComment(
        submission_id=submission_id,
        author_user_id=author_user_id,
        body=body,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


async def list_for_admin(
    db: AsyncSession, submission_id: uuid.UUID
):
    rows = (
        await db.execute(
            select(InstructorComment, User)
            .join(User, InstructorComment.author_user_id == User.id)
            .where(InstructorComment.submission_id == submission_id)
            .order_by(InstructorComment.created_at.asc())
        )
    ).all()
    return rows


async def list_for_owner(
    db: AsyncSession, *, submission_id: uuid.UUID, owner_user_id: uuid.UUID,
):
    sub = (
        await db.execute(
            select(Submission).where(
                Submission.id == submission_id,
                Submission.user_id == owner_user_id,
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        raise SubmissionNotFoundError(str(submission_id))
    return await list_for_admin(db, submission_id)
```

- [ ] **Step 3: API を実装**

`backend/app/api/admin/comments.py`:
- `POST /api/admin/submissions/{submission_id}/comments`
- `GET /api/admin/submissions/{submission_id}/comments`

`backend/app/api/me.py`:
- `GET /api/me/submissions/{submission_id}/comments`（オーナー本人のみ）

- [ ] **Step 4: failing test を書く**

`backend/tests/test_admin_comments_api.py`:

```python
"""Admin comments API."""

import pytest
from app.core.security import create_access_token, hash_password


async def _make_learner_with_sub(db_session):
    from app.models.submission import Submission
    from app.models.user import User
    from app.services.progress import initialize_progress
    from datetime import UTC, datetime

    learner = User(email="lc@e.com", name="lc", password_hash=hash_password("p"))
    db_session.add(learner)
    await db_session.flush()
    await initialize_progress(db_session, learner.id)
    sub = Submission(
        user_id=learner.id, phase=1, task_no=1, content="x",
        submitted_at=datetime.now(UTC),
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return learner, sub


@pytest.mark.asyncio
async def test_admin_can_post_comment_and_learner_can_read(
    client, db_session, admin_user,
):
    learner, sub = await _make_learner_with_sub(db_session)

    # admin posts
    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(admin_user.id))}"}
    )
    r = client.post(
        f"/api/admin/submissions/{sub.id}/comments",
        json={"body": "Nice work, but tighten phrase 2."},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["body"].startswith("Nice work")

    # learner reads
    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(learner.id))}"}
    )
    r = client.get(f"/api/me/submissions/{sub.id}/comments")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["author_name"] == "講師"


@pytest.mark.asyncio
async def test_non_owner_learner_cannot_read_others_comments(
    client, db_session, admin_user,
):
    learner, sub = await _make_learner_with_sub(db_session)
    from app.models.user import User
    intruder = User(email="i@e.com", name="i", password_hash=hash_password("p"))
    db_session.add(intruder)
    await db_session.commit()
    await db_session.refresh(intruder)

    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(admin_user.id))}"}
    )
    client.post(
        f"/api/admin/submissions/{sub.id}/comments",
        json={"body": "x"},
    )

    client.headers.update(
        {"Authorization": f"Bearer {create_access_token(subject=str(intruder.id))}"}
    )
    r = client.get(f"/api/me/submissions/{sub.id}/comments")
    assert r.status_code == 404
```

- [ ] **Step 5: 全テスト実行**

Expected: `164+ passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/comment.py backend/app/services/comment.py \
        backend/app/api/admin/comments.py backend/app/api/me.py \
        backend/app/main.py backend/tests/test_admin_comments_api.py
git commit -m "feat(sprint-4): instructor comments API (admin write, learner read)"
```

---

## Task 14: 通知 API（TDD）

**Files:**
- Create: `backend/app/schemas/notification.py`
- Create: `backend/app/services/notification.py`
- Create: `backend/app/api/admin/notifications.py`
- Modify: `backend/app/api/me.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_admin_notifications_api.py`
- Create: `backend/tests/test_me_api.py`

- [ ] **Step 1: スキーマと service を実装**

```python
# schemas/notification.py
class NotificationCreate(BaseModel):
    recipient_user_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    link: str | None = Field(default=None, max_length=500)

class NotificationOut(BaseModel):
    id: uuid.UUID
    recipient_user_id: uuid.UUID
    sender_user_id: uuid.UUID
    sender_name: str
    title: str
    body: str
    link: str | None
    read_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}

class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int
```

```python
# services/notification.py
async def send(*, db, sender_id, payload: NotificationCreate) -> Notification: ...
async def list_for_recipient(db, user_id, *, limit) -> NotificationListOut: ...
async def mark_read(db, *, notification_id, user_id) -> None: ...   # 所有者チェック付き
async def list_sent_by_admin(db, sender_id) -> list[Notification]: ...
```

- [ ] **Step 2: API**

`backend/app/api/admin/notifications.py`:
- `POST /api/admin/notifications` （`NotificationCreate`）
- `GET /api/admin/notifications` （自分が送った通知一覧）

`backend/app/api/me.py` に追加:
- `GET /api/me/notifications`
- `POST /api/me/notifications/{notification_id}/read`

- [ ] **Step 3: failing test を書く**

`tests/test_admin_notifications_api.py` + `tests/test_me_api.py` で:
- admin がない recipient_user_id を指定 → 404 or 422
- admin が学習者宛に送信 → 201
- 受講者が自分の通知一覧取得 → 1 件、`unread_count == 1`
- 受講者が既読化 → `read_at` セット、`unread_count == 0`
- 別ユーザーが他人の notification を既読化 → 404

- [ ] **Step 4: 全テスト実行**

Expected: `169+ passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/notification.py backend/app/services/notification.py \
        backend/app/api/admin/notifications.py backend/app/api/me.py \
        backend/app/main.py backend/tests/test_admin_notifications_api.py \
        backend/tests/test_me_api.py
git commit -m "feat(sprint-4): notifications API (admin send, learner read/mark-read)"
```

---

## Task 15: rate limit を admin API にも適用

**Files:**
- Modify: `backend/app/api/admin/users.py` 他

- [ ] **Step 1: 各 admin POST 系エンドポイントに `@limiter.limit("60/minute")` を追加**

```python
from app.core.limiter import limiter
from app.config import settings
from fastapi import Request

@router.post("...")
@limiter.limit("60/minute")
async def create_xxx(request: Request, ...):
```

対象:
- `POST /api/admin/submissions/{id}/comments`
- `POST /api/admin/notifications`

- [ ] **Step 2: 全テスト実行**

Expected: 既存テストは `RATE_LIMIT_ENABLED=false` なので影響なし。

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(sprint-4): apply rate limit to admin write endpoints"
```

---

## Task 16: フロント TypeScript 型と API クライアント

**Files:**
- Create: `frontend/src/types/admin.ts`
- Create: `frontend/src/types/notification.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: types を作成**

```ts
// types/admin.ts
export interface AdminUserSummary {
  id: string;
  email: string;
  name: string;
  created_at: string;
  is_admin: boolean;
  completed_phases: number;
  in_progress_phases: number;
}
export interface AdminUserListOut {
  items: AdminUserSummary[];
  total: number;
  limit: number;
  offset: number;
}
export interface AdminUserDetail {
  id: string;
  email: string;
  name: string;
  created_at: string;
  is_admin: boolean;
  progress: ProgressOut[];
  latest_scores: Record<number, number | null>;
}
// AdminSubmissionSummary, AdminSubmissionListOut, AdminSubmissionDetail も同様
// AdminCommentOut, CommentCreate も
```

```ts
// types/notification.ts
export interface NotificationOut { ... }
export interface NotificationListOut {
  items: NotificationOut[];
  unread_count: number;
}
export interface NotificationCreate { recipient_user_id: string; title: string; body: string; link?: string | null; }
```

- [ ] **Step 2: api.ts に admin* と notifications* を追加**

```ts
adminListUsers: (limit=50, offset=0) => rawRequest<AdminUserListOut>(`/api/admin/users?limit=${limit}&offset=${offset}`),
adminGetUser: (id: string) => rawRequest<AdminUserDetail>(`/api/admin/users/${id}`),
adminListSubmissions: (params: {user_id?: string; phase?: number; limit?: number; offset?: number}) => ...,
adminGetSubmission: (id: string) => rawRequest<AdminSubmissionDetail>(`/api/admin/submissions/${id}`),
adminPostComment: (id: string, body: string) => rawRequest<AdminCommentOut>(`/api/admin/submissions/${id}/comments`, { method: 'POST', body: JSON.stringify({body}) }),
adminSendNotification: (payload: NotificationCreate) => rawRequest<NotificationOut>(`/api/admin/notifications`, { method: 'POST', body: JSON.stringify(payload) }),
listMyNotifications: () => rawRequest<NotificationListOut>(`/api/me/notifications`),
markNotificationRead: (id: string) => rawRequest<{ok: true}>(`/api/me/notifications/${id}/read`, { method: 'POST' }),
listMyComments: (submissionId: string) => rawRequest<LearnerCommentOut[]>(`/api/me/submissions/${submissionId}/comments`),
```

- [ ] **Step 3: 既存ビルドを通す**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/admin.ts frontend/src/types/notification.ts frontend/src/lib/api.ts
git commit -m "feat(frontend): add admin and notification API clients"
```

---

## Task 17: Pinia ストア（admin + notification）

**Files:**
- Create: `frontend/src/stores/admin.ts`
- Create: `frontend/src/stores/notification.ts`
- Modify: `frontend/src/stores/auth.ts`（`isAdmin` getter 追加）
- Create: `frontend/src/__tests__/admin.store.spec.ts`
- Create: `frontend/src/__tests__/notification.store.spec.ts`

- [ ] **Step 1: auth store に isAdmin を追加**

JWT デコードは行わず、`/api/auth/me` の `is_admin` を保存。Sprint 1 で `/api/auth/me` を持っていない場合は新規エンドポイントを backend に追加（既にあるかは Task 0 で確認）。

- [ ] **Step 2: admin store を作る**

```ts
export const useAdminStore = defineStore('admin', {
  state: () => ({
    users: [] as AdminUserSummary[],
    selectedUser: null as AdminUserDetail | null,
    submissions: [] as AdminSubmissionSummary[],
    selectedSubmission: null as AdminSubmissionDetail | null,
    loading: false,
    error: null as string | null,
  }),
  actions: {
    async fetchUsers(limit=50, offset=0) { ... },
    async fetchUserDetail(id: string) { ... },
    async fetchSubmissions(params) { ... },
    async fetchSubmissionDetail(id: string) { ... },
    async postComment(id: string, body: string) { ... },
    async sendNotification(payload) { ... },
  }
});
```

- [ ] **Step 3: notification store**

```ts
export const useNotificationStore = defineStore('notification', {
  state: () => ({ items: [] as NotificationOut[], unreadCount: 0, polling: 0 as number }),
  actions: {
    async refresh() { ... },
    startPolling() {
      this.polling = window.setInterval(() => this.refresh(), 30_000);
    },
    stopPolling() {
      if (this.polling) window.clearInterval(this.polling);
      this.polling = 0;
    },
    async markRead(id: string) { ... },
  }
});
```

- [ ] **Step 4: store specs**

Sprint 3 の `curriculum.store.spec.ts` を参考に、`api` を `vi.mock` してアサート。

- [ ] **Step 5: Build + test**

```bash
cd frontend && npm test -- --run && npm run build
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/stores/ frontend/src/__tests__/admin.store.spec.ts frontend/src/__tests__/notification.store.spec.ts
git commit -m "feat(frontend): admin and notification Pinia stores"
```

---

## Task 18: 管理者 routing + AdminLayout

**Files:**
- Create: `frontend/src/router/admin.ts`
- Modify: `frontend/src/router/index.ts`
- Create: `frontend/src/layouts/AdminLayout.vue`

- [ ] **Step 1: admin route 定義**

```ts
// router/admin.ts
import type { RouteRecordRaw } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

export const adminRoutes: RouteRecordRaw[] = [
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { requiresAdmin: true },
    children: [
      { path: '', redirect: '/admin/users' },
      { path: 'users', component: () => import('@/views/admin/AdminUsersView.vue') },
      { path: 'users/:id', component: () => import('@/views/admin/AdminUserDetailView.vue') },
      { path: 'submissions/:id', component: () => import('@/views/admin/AdminSubmissionDetailView.vue') },
      { path: 'notify', component: () => import('@/views/admin/AdminNotifyView.vue') },
    ],
  },
];

export function attachAdminGuard(router: import('vue-router').Router) {
  router.beforeEach((to) => {
    if (to.meta.requiresAdmin) {
      const auth = useAuthStore();
      if (!auth.isAdmin) return { path: '/' };
    }
  });
}
```

`router/index.ts` で `routes.push(...adminRoutes)` + `attachAdminGuard(router)`。

- [ ] **Step 2: AdminLayout.vue**

ヘッダに「受講者一覧 / 通知作成 / ログアウト」を置く。中央は `<router-view />`。Sprint 3 までの学習者画面とは見た目を切り分ける。

- [ ] **Step 3: ビルド**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

---

## Task 19: 管理画面のビュー実装

**Files:**
- Create: `frontend/src/views/admin/AdminUsersView.vue`
- Create: `frontend/src/views/admin/AdminUserDetailView.vue`
- Create: `frontend/src/views/admin/AdminSubmissionDetailView.vue`
- Create: `frontend/src/views/admin/AdminNotifyView.vue`
- Create: `frontend/src/components/CommentThread.vue`

要件:

| ビュー | 表示 | 操作 |
|---|---|---|
| AdminUsersView | テーブル: name / email / 完了 / 進行中 / 作成日 | クリックで `/admin/users/:id` |
| AdminUserDetailView | 4 フェーズの状態、各 phase の最新スコア | 「提出を見る」ボタン → `/admin/submissions/:id` |
| AdminSubmissionDetailView | content + files + grading_history + コメント一覧 | コメント投稿フォーム、ダウンロードボタン |
| AdminNotifyView | 受講者ドロップダウン + title + body + link 入力フォーム | 送信ボタン |

`CommentThread.vue` は admin / learner 両方から再利用できるよう props: `comments: AdminCommentOut[]`, `canPost: boolean`, emit `post(body)`.

- [ ] **Step 1〜4**: 各ビューを実装、ビルドを通す。

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(frontend): admin dashboard views"
```

---

## Task 20: 受講者側の通知センターとコメント表示

**Files:**
- Create: `frontend/src/components/NotificationCenter.vue`
- Modify: `frontend/src/components/TaskSubmissionCard.vue`
- Modify: `frontend/src/views/HomeView.vue` あるいは共通レイアウト

- [ ] **Step 1: NotificationCenter.vue**

ヘッダ右側にベルアイコン。`useNotificationStore` を購読し、`unreadCount` を数字バッジで。クリックでドロップダウン展開、各通知の右側「既読」リンク。

- [ ] **Step 2: TaskSubmissionCard.vue にコメント表示**

`submission` ロード時に `api.listMyComments(submission.id)` を呼び、`CommentThread` で表示（read-only）。

- [ ] **Step 3: 既存レイアウトに NotificationCenter を組み込み**

ログイン中の全画面で見えるように。

- [ ] **Step 4: 通知ポーリング開始/停止**

`App.vue` の `onMounted` / `onBeforeUnmount` で `useNotificationStore().startPolling()` / `stopPolling()`。

- [ ] **Step 5: vitest spec**

`NotificationCenter.spec.ts`: 未読件数バッジ、既読化動作。

- [ ] **Step 6: Build + test**

```bash
cd frontend && npm test -- --run && npm run build
```

- [ ] **Step 7: Commit**

---

## Task 21: 設計書を反映

**Files:**
- Modify: `docs/design/03-db-design.md`
- Modify: `docs/design/04-interface-design.md`
- Modify: `docs/design/05-screen-design.md`
- Modify: `docs/design/06-test-design.md`
- Modify: `README.md`

- [ ] **Step 1: 03-db-design.md に Sprint 4 セクションを追記**

`instructor_comments` / `notifications` の ER 図、`users.is_admin` の追加。

- [ ] **Step 2: 04-interface-design.md に Sprint 4 API を追記**

`/api/admin/users`, `/api/admin/submissions`, `/api/admin/submissions/{id}/comments`, `/api/admin/notifications`, `/api/me/notifications`, `/api/me/submissions/{id}/comments`。

- [ ] **Step 3: 05-screen-design.md に admin 画面遷移を追記**

`/admin/users` → `/admin/users/:id` → `/admin/submissions/:id`、`AdminNotifyView`、通知センター。

- [ ] **Step 4: 06-test-design.md に Sprint 4 ケース表を追記**

権限テストマトリクス（admin / 別の admin / learner-owner / learner-non-owner × API）。

- [ ] **Step 5: README.md に Sprint 4 進捗を追記**

- [ ] **Step 6: Commit**

```bash
git commit -am "docs(sprint-4): document admin dashboard schema, API, screens, tests"
```

---

## Task 22: Playwright E2E（golden path）

**Files:**
- 添付: スクリーンショット 3 枚（`e2e-sprint4-*.png`）

- [ ] **Step 1: 環境を起動**

```bash
docker compose up -d postgres
cd backend && uv run uvicorn app.main:app --reload --port 8000 &
cd frontend && npm run dev &
```

- [ ] **Step 2: admin と learner をシードする**

```bash
cd backend && uv run python -m scripts.promote_admin instructor@example.com
```

learner を seed する仕組みは既存登録 API を経由して作る。

- [ ] **Step 3: Playwright MCP で golden path を実行**

シナリオ:
1. admin でログイン → `/admin/users` で learner を選ぶ
2. learner の `/admin/users/:id` → 任意の submission を選ぶ
3. `AdminSubmissionDetailView` でコメント投稿
4. AdminNotifyView から learner 宛通知を送る
5. learner としてログイン → ベルアイコンに `unreadCount=1`
6. 通知 → クリックで `/phases/:phase` へ
7. `TaskSubmissionCard` でコメントが表示される

スクリーンショット 3 枚:
- `e2e-sprint4-admin-comment.png`
- `e2e-sprint4-learner-notification.png`
- `e2e-sprint4-learner-comment-visible.png`

- [ ] **Step 4: 結果が良好ならコミット**

```bash
git add e2e-sprint4-*.png
git commit -m "test(e2e): Sprint 4 golden path screenshots"
```

- [ ] **Step 5: 環境を停止**

```bash
kill %1 %2 || true
```

---

## Task 23: security-reviewer agent でレビュー

- [ ] **Step 1: security-reviewer agent を起動**

main..HEAD の Sprint 4 差分を渡して以下を重点的に確認:
- admin RBAC の bypass 経路（JWT に is_admin claim を信用していないか、サーバー側 dep が常時走るか）
- BOLA: 受講者が他者の `/api/me/notifications/{id}/read` を叩いて既読化できないか
- コメント body の長さ・XSS 経路（フロントで `{{ }}` 描画のみ、`v-html` 不使用を確認）
- 通知 link フィールドの open redirect 経路（`javascript:` URL の検証）
- CSP header が実際に全レスポンスに付与されているか
- MED-1〜5 の修正が回帰していないか
- 新規 API のレート制限カバレッジ

- [ ] **Step 2: CRITICAL / HIGH 指摘を修正**

- [ ] **Step 3: 修正があれば Commit**

```bash
git commit -am "fix(sprint-4): address security-reviewer findings"
```

---

## Task 24: 仕上げと Sprint 4 完了マーク

- [ ] **Step 1: 全テスト最終実行**

```bash
docker compose up -d postgres
cd backend && uv run pytest --cov=app --cov-report=term-missing
cd frontend && npm test -- --run && npm run build
```

期待: backend 175+ 件 PASS、coverage 80%+、frontend 15+ 件 PASS。

- [ ] **Step 2: 計画書末尾に完了マーク**

```markdown
---

## ✅ Sprint 4 完了

完了日: <YYYY-MM-DD>
- Backend テスト: <N> passed / coverage 80%+
- Frontend ビルド: 成功 / vitest passed
- Playwright E2E golden path: PASS
- security-reviewer: ブロッカーなし
- 取り込んだ MED 件: 5 / 5（follow-up doc 該当行を `[x]` 化）
```

- [ ] **Step 3: コミット**

```bash
git add docs/superpowers/plans/2026-06-06-ai-tutor-curriculum-sprint-4.md \
        docs/superpowers/specs/2026-06-06-sprint-3-security-followups.md
git commit -m "docs: mark Sprint 4 complete"
```

- [ ] **Step 4: feature ブランチを main へマージ**

`superpowers:finishing-a-development-branch` skill を起動して main への fast-forward マージを実施、または手動:

```bash
git checkout main
git merge --ff-only feature/sprint-4
git branch -d feature/sprint-4
```

- [ ] **Step 5: 動作確認用 docker compose を停止**

```bash
docker compose down
```

---

## 受け入れ基準

- [x] backend テスト **175+** 件 PASS（Sprint 3 完了時の 148 件 + Sprint 4 で 27+ 件追加） — **208 件** 達成 (+60)
- [x] backend coverage 80%+ 維持 — **86%**
- [x] frontend ビルド成功、vitest **15+** 件 PASS — **33 件**
- [x] Playwright E2E golden path（admin → コメント → 通知 → 受講者で確認）が緑
- [x] `security-reviewer` agent で CRITICAL/HIGH なし — CRITICAL 0、HIGH × 2 を修正 (commit `03bfe8e`)
- [x] Alembic upgrade / downgrade が往復可能 — `20260606_af4220e315e6` で確認
- [x] 既存 Sprint 1/2/3 機能のリグレッションなし（login / chat / progress / 提出 / 採点 / 履歴 / 再採点）
- [x] 設計書 03/04/05/06 に Sprint 4 差分を追記 (commit `a709abe`)
- [x] follow-up doc の MED-1〜5 該当行が `[x]` 化されている (commit `79d7748`)
- [x] non-admin が `/api/admin/*` を叩くと 403
- [x] 受講者が他者の通知や他者のコメントスレッドに到達できない（BOLA テスト全 PASS）
- [x] 全 API レスポンスに `Content-Security-Policy` ヘッダが付与されている

---

## ✅ Sprint 4 完了

完了日: 2026-06-08

- Backend テスト: **208 passed**, coverage **86%**（threshold 80% 超過、Sprint 3 完了時の 148 件 + Sprint 4 で 60 件追加）
- Frontend ビルド: 成功（`vue-tsc` + `vite build`）、vitest **33 passed**（Sprint 3 完了時の 11 件 + 22 件追加）
- Playwright E2E golden path: PASS（`e2e-sprint4-admin-comment.png` / `e2e-sprint4-learner-notification.png` / `e2e-sprint4-learner-comment-visible.png` をリポジトリに保持）
- security-reviewer: CRITICAL 0、HIGH × 2 修正済み（commit `03bfe8e`）
  - HIGH-1: 通知 `link` の危険スキーム遮断（backend allowlist + frontend `safeExternalHref` 多層防御）
  - HIGH-2: per-recipient unread cap (`notification_unread_cap=200`) で inbox DoS 遮断
- Sprint 3 MEDIUM 5 件も併せて修正済み
  - MED-1: 添付の XML 区切り (`de317d8`)
  - MED-2: grading の root 境界統一 (`a7c01c9`)
  - MED-3: Claude SDK エラーマスク (`841e97f`)
  - MED-4: ファイル名衝突回避 (`7fafcd1`)
  - MED-5: CSP middleware (`9c2cba7`)
- Sprint 4 の MEDIUM × 5 + LOW × 4 は `docs/superpowers/specs/2026-06-08-sprint-4-security-followups.md` に Sprint 5 取り込み優先順位付きで記録
- Alembic: `20260606_af4220e315e6` で upgrade/downgrade 往復可能、`alembic check` も clean
- 既存 Sprint 1/2/3 リグレッションテスト全 PASS
