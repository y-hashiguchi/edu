# 06 テスト設計書

**版:** 1.0
**作成日:** 2026-06-02

---

## 1. テスト方針

### 1.1 方針

- TDD（Red-Green-Refactor）を全タスクで適用
- バックエンド：実 Postgres を起動し pytest で単体・統合を実行（モックは Anthropic SDK と時刻のみ）
- フロントエンド：vitest で単体テスト、Playwright で E2E（Sprint 1 では critical path 1 本）
- カバレッジ目標：バックエンド **80% 以上**、フロントエンド **70% 以上**

### 1.2 テスト分類

| カテゴリ | 範囲 | フレームワーク |
|---|---|---|
| バックエンド単体 | 関数・クラス（DB アクセスを含む） | pytest + pytest-asyncio |
| バックエンド統合 | エンドポイント単位（FastAPI + DB + モック AI） | pytest + httpx AsyncClient |
| フロントエンド単体 | ストアアクション、ユーティリティ | vitest |
| フロントエンド E2E | ログイン → チャット送信 → 完了 → 次フェーズ解放 | Playwright |

### 1.3 テスト DB

- DB: `ai_tutor_test`（`docker-compose` 初回起動時に `db-init/01-create-test-db.sql` で作成）
- スキーマ生成：テストセッション開始時に `Base.metadata.drop_all` → `create_all`
- データクリア：各テスト開始前に `TRUNCATE <全テーブル> RESTART IDENTITY CASCADE`
- BCRYPT_ROUNDS=4 / JWT_SECRET_KEY=test-secret を `conftest.py` で固定

### 1.4 共通フィクスチャ（conftest.py）

| フィクスチャ | スコープ | 説明 |
|---|---|---|
| `_setup_db` | session | テーブル作成・破棄 |
| `db_session` | function | 各テスト前に TRUNCATE、AsyncSession を yield |
| `client` | function | httpx AsyncClient（FastAPI ASGITransport） |
| `auth_user` | function | テストユーザを作成（progress も seed） |
| `auth_token` | function | `auth_user` の JWT |
| `auth_client` | function | `client` に `Authorization` ヘッダーを付与 |
| `fake_claude` | function | `AsyncMock` で SDK を差し替え |

---

## 2. バックエンドテストケース

### 2.1 `tests/test_security.py`

| ID | テスト名 | 検証内容 |
|---|---|---|
| SEC-01 | `test_hash_then_verify_returns_true` | ハッシュ後に同じ平文で検証→True |
| SEC-02 | `test_verify_returns_false_for_wrong_password` | 異なる平文→False |
| SEC-03 | `test_hash_outputs_differ_for_same_input` | 同じ平文を 2 回ハッシュしてソルトが異なる→出力も異なる |
| SEC-04 | `test_create_then_decode_returns_subject` | `create_access_token` → `decode_access_token` で `sub` が一致 |
| SEC-05 | `test_decode_raises_on_invalid_signature` | 改竄トークンで `JWTError` |
| SEC-06 | `test_decode_raises_on_expired_token` | `expires_min=-1` で発行 → `JWTError` |
| SEC-07 | `test_decode_raises_on_missing_sub` | `sub` 無しの JWT を直接生成 → `JWTError` |

### 2.2 `tests/test_api_auth.py`

| ID | テスト名 | 検証 |
|---|---|---|
| AUTH-01 | `test_register_creates_user_and_progress` | 201 / `users` 1行 / `progress` 4行（Phase 1=in_progress、他=locked） |
| AUTH-02 | `test_register_password_is_hashed_not_plain` | DB の `password_hash` が平文と一致しない |
| AUTH-03 | `test_register_returns_409_on_duplicate_email` | 同 email 2 回目で 409 |
| AUTH-04 | `test_register_returns_422_on_short_password` | password=`abc` で 422 |
| AUTH-05 | `test_register_returns_422_on_invalid_email` | email=`foo` で 422 |
| AUTH-06 | `test_login_returns_token_on_valid_credentials` | 正しい資格で 200 + `access_token` |
| AUTH-07 | `test_login_returns_401_on_wrong_password` | パスワード不一致で 401 |
| AUTH-08 | `test_login_returns_401_on_unknown_email` | 存在しない email で 401（同じ文言） |
| AUTH-09 | `test_me_returns_current_user` | 有効トークンで 200 / user 情報 |
| AUTH-10 | `test_me_returns_401_without_token` | ヘッダー無しで 401 |
| AUTH-11 | `test_me_returns_401_with_expired_token` | `exp` 過去のトークンで 401 |
| AUTH-12 | `test_me_returns_401_with_invalid_signature` | 改竄トークンで 401 |

### 2.3 `tests/test_progress_service.py`

| ID | テスト名 | 検証 |
|---|---|---|
| SVC-01 | `test_initialize_progress_seeds_four_rows` | 4 行作成、Phase 1=in_progress、他=locked |
| SVC-02 | `test_initialize_phase1_has_started_at` | Phase 1 の `started_at` が NOT NULL |
| SVC-03 | `test_list_progress_orders_by_phase` | 返り値が phase 昇順 |
| SVC-04 | `test_is_phase_unlocked_true_for_in_progress` | True |
| SVC-05 | `test_is_phase_unlocked_false_for_locked` | False |
| SVC-06 | `test_complete_phase_updates_status_and_timestamp` | `completed`、`completed_at` セット |
| SVC-07 | `test_complete_phase_unlocks_next_phase` | Phase n+1 が `locked → in_progress` |
| SVC-08 | `test_complete_phase_returns_next_unlocked` | tuple の 2 要素目が Phase n+1 |
| SVC-09 | `test_complete_last_phase_returns_none_for_next` | Phase 4 完了で `next_unlocked is None` |
| SVC-10 | `test_complete_already_completed_is_idempotent` | 200、`next_unlocked is None`（既に解放済） |
| SVC-11 | `test_complete_locked_phase_raises_phase_locked` | `PhaseLockedError` |
| SVC-12 | `test_complete_unknown_phase_raises_not_found` | `PhaseNotFoundError` |

### 2.4 `tests/test_api_progress.py`

| ID | テスト名 | 検証 |
|---|---|---|
| PROG-01 | `test_list_returns_four_phases` | GET /api/progress で 4 件 |
| PROG-02 | `test_list_requires_auth` | 401 without token |
| PROG-03 | `test_complete_returns_200_with_next_unlocked` | POST /api/progress/1/complete で Phase 2 解放 |
| PROG-04 | `test_complete_last_phase_no_next_unlocked` | Phase 4 完了で `next_unlocked: null` |
| PROG-05 | `test_complete_returns_403_for_locked_phase` | Phase 2 を Phase 1 未完で完了試行 → 403 |
| PROG-06 | `test_complete_returns_422_for_phase_out_of_range` | phase=99 で 422 |
| PROG-07 | `test_complete_requires_auth` | 401 without token |
| PROG-08 | `test_complete_only_affects_caller` | 別ユーザの progress に影響しない |

### 2.5 `tests/test_api_curriculum.py`（Sprint 0 から拡張）

| ID | テスト名 | 検証 |
|---|---|---|
| CURR-01 | `test_list_phases_requires_auth` | 401 without token（Sprint 0 から変更） |
| CURR-02 | `test_list_phases_returns_four_phases_with_locked_flags` | 4 件、Phase 1 locked=False、他 locked=True |
| CURR-03 | `test_list_phases_reflects_progress_status` | 完了後の取得で status が反映される |

### 2.6 `tests/test_chat_store.py`（Sprint 0 から書き換え）

| ID | テスト名 | 検証 |
|---|---|---|
| STORE-01 | `test_get_history_returns_empty_initially` | 空配列 |
| STORE-02 | `test_append_then_get_in_order` | 挿入順で返る |
| STORE-03 | `test_history_isolated_per_user` | 別ユーザの履歴は混在しない |
| STORE-04 | `test_history_isolated_per_phase` | 別フェーズの履歴は混在しない |
| STORE-05 | `test_persists_across_sessions` | 別セッションで同じ user/phase を SELECT しても見える |

### 2.7 `tests/test_claude_client.py`（async 移行）

| ID | テスト名 | 検証 |
|---|---|---|
| CL-01 | `test_complete_returns_assistant_text` | AsyncMock で固定応答を返す |
| CL-02 | `test_complete_passes_model_and_system` | `messages.create` 呼出引数を検証 |
| CL-03 | `test_complete_propagates_sdk_errors` | SDK が例外を投げると伝播 |

### 2.8 `tests/test_api_chat.py`（auth 統合）

| ID | テスト名 | 検証 |
|---|---|---|
| CHAT-01 | `test_chat_requires_auth` | 401 without token |
| CHAT-02 | `test_chat_returns_reply_and_persists_history` | 200 / DB に 2 行（user + assistant）|
| CHAT-03 | `test_chat_carries_history_across_calls` | 2 回目の `claude.complete` の messages に過去の 2 件が含まれる |
| CHAT-04 | `test_chat_rejects_invalid_phase_via_validation` | phase=99 で 422 |
| CHAT-05 | `test_chat_rejects_locked_phase_with_403` | Phase 2 へ送信 → 403 |
| CHAT-06 | `test_chat_isolated_per_user` | user A の履歴に user B のメッセージが混入しない |
| CHAT-07 | `test_chat_propagates_502_on_claude_error` | SDK が例外 → 502、DB に履歴が残らない |
| CHAT-08 | `test_chat_uses_current_user_not_request_field` | リクエストに余分な user_id を入れても無視（または 422） |

### 2.9 `tests/test_api_chat_history.py`

| ID | テスト名 | 検証 |
|---|---|---|
| HIST-01 | `test_get_history_returns_empty_array_initially` | 空配列 |
| HIST-02 | `test_get_history_returns_ordered_messages` | 挿入順 |
| HIST-03 | `test_get_history_requires_auth` | 401 |
| HIST-04 | `test_get_history_returns_403_for_locked_phase` | 403 |
| HIST-05 | `test_get_history_isolated_per_user` | 別ユーザの履歴は含まない |

### 2.10 `tests/test_health.py`（既存維持）

| ID | テスト名 | 検証 |
|---|---|---|
| HLT-01 | `test_healthz_returns_ok` | 200 / `{"status":"ok"}` |

### 2.11 `tests/test_curriculum_data.py`（既存維持）

Sprint 0 のテスト 6 件を継承。変更なし。

---

## 3. フロントエンドテストケース

### 3.1 vitest 単体

| ID | 対象 | 検証 |
|---|---|---|
| FE-AUTH-01 | `stores/auth.login` | fetch モックで 200 → state.token / state.user 反映 |
| FE-AUTH-02 | `stores/auth.login` | 401 → state.token=null、エラー伝播 |
| FE-AUTH-03 | `stores/auth.register` | 201 → 自動 login |
| FE-AUTH-04 | `stores/auth.logout` | state クリア + router push not tested here |
| FE-API-01 | `lib/api.request` | Authorization ヘッダーが付与される |
| FE-API-02 | `lib/api.request` | 401 受信で `authStore.logout()` + リダイレクト呼出 |
| FE-CURR-01 | `stores/curriculum.fetchPhasesWithProgress` | phases + progress を並列取得しマージ |
| FE-CURR-02 | `stores/curriculum.completePhase` | API 成功で progress 更新 |
| FE-CURR-03 | `stores/curriculum.loadHistory` | 履歴を `chatLogs[phase]` に格納 |
| FE-CURR-04 | `stores/curriculum.sendChat` | 履歴に user→assistant が追加される |

### 3.2 Playwright E2E（1 本）

**シナリオ:** `e2e/login-to-complete.spec.ts`

```
1. /login にアクセス
2. 新規登録タブで alice / password123 を登録
3. ログインタブに切替、同じ資格でログイン
4. / に遷移し、Phase 1 が「進行中」、Phase 2-4 が「ロック」で表示
5. 「AIチューターと対話する」をクリック
6. /phases/1 に遷移、チャット入力欄が表示
7. 「Hello」を送信（モック AI が固定応答を返す）
8. ChatLog に user / assistant が表示される
9. 「このフェーズを完了する」→確認ダイアログ→「完了する」
10. / に戻り、Phase 1 が「完了」、Phase 2 が「進行中」表示
11. ログアウト → /login に遷移
```

E2E では Anthropic API を直接呼ばず、テスト用にバックエンドを `ANTHROPIC_API_KEY=fake` で起動し、リクエストを横取りするテストハンドラ（または Playwright の `page.route` でモック）を使う。具体実装は Sprint 1 完了時に決定。

---

## 4. テストデータ

| 名前 | email | password | name | 用途 |
|---|---|---|---|---|
| alice | alice@example.com | password123 | アリス | 標準テストユーザ |
| bob | bob@example.com | password456 | ボブ | 隔離検証用 |

---

## 5. 受入基準（Sprint 1 完了条件）

### 5.1 機能要件

- [ ] `make test` で全テスト PASS（バックエンド + フロントエンド）
- [ ] `make dev` で 3 サービスが起動し、ブラウザから登録 → ログイン → チャット → 完了 → 次フェーズ解放まで一気通貫
- [ ] DB を `docker compose down` で破棄し、再度 `make dev` してもマイグレーションが自動適用される
- [ ] フェーズロックを迂回しようとした不正リクエスト（直接 POST）に 403 を返す
- [ ] JWT 期限切れトークンでアクセスすると 401 → フロントで `/login` 強制遷移

### 5.2 非機能要件

- [ ] バックエンドカバレッジ ≥ 80%（`pytest --cov`）
- [ ] フロントエンドカバレッジ ≥ 70%（`vitest --coverage`）
- [ ] `ruff check app tests` がエラー無し
- [ ] `npm run lint` がエラー無し
- [ ] `vue-tsc` でフロントの型エラー無し
- [ ] OpenAPI（`/docs`）が正しく生成され、認証エンドポイントは Lock マークが表示される

### 5.3 ドキュメント

- [ ] README の Sprint 1 を `[x]` 完了マーク
- [ ] 本設計書群（01〜06）と差分が無い（差異があれば版を上げる）

---

## 6. テスト実行コマンド

| シーン | コマンド |
|---|---|
| Postgres 起動（テスト用） | `docker compose up -d postgres` |
| バックエンド全テスト | `cd backend && uv run pytest -v` |
| カバレッジ込み | `cd backend && uv run pytest --cov=app --cov-report=term-missing` |
| 単一テスト | `uv run pytest tests/test_api_auth.py::test_login_returns_token_on_valid_credentials -v` |
| フロントエンド単体 | `cd frontend && npm run test` |
| フロントエンド E2E | `cd frontend && npx playwright test` |

---

## 7. CI（参考）

Sprint 1 ではローカル実行のみ。Sprint 4 で GitHub Actions に統合する想定。

```yaml
# .github/workflows/ci.yml （参考）
services:
  postgres:
    image: pgvector/pgvector:pg16
    env:
      POSTGRES_PASSWORD: postgres
    ports: ["5432:5432"]
    options: --health-cmd pg_isready --health-interval 5s

steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with: { python-version: "3.12" }
  - run: pip install uv && cd backend && uv sync --extra dev
  - run: cd backend && uv run pytest --cov=app
```

---

## 8. リスクと対応

| リスク | 検証/緩和 |
|---|---|
| 既存 Sprint 0 テストが認証統合で全て書き換え | `auth_client` フィクスチャでヘッダー付与の重複を避ける |
| Postgres + asyncpg + Alembic の組合せで詰まる | Task 3 完了時に `alembic current` が走ることを確認してから先へ |
| bcrypt が CI で遅い | `BCRYPT_ROUNDS=4` をテスト環境変数で強制 |
| Playwright が CI 上で重い | Sprint 1 では E2E は手動またはローカルのみ。CI 統合は Sprint 4 |
| フロント 401 ハンドリングのループ | `lib/api` で `/login` 自身からのリクエストは除外する |

## Sprint 3 追加

### バックエンドテスト

- `test_file_storage.py` — sanitize / 拡張子 / MIME / パストラバーサル
- `test_file_storage_service.py` — persist_uploads / clear_existing_files / 上限超過
- `test_models_sprint3.py` — SubmissionFile / GradingAttempt / CHECK 制約
- `test_claude_client.py` — `complete_multimodal` の image/PDF base64 整形
- `test_grading_service.py` — multimodal blocks / status-typed GradingResult
- `test_submission_service.py` — files + grading_attempts + regrade（cooldown）
- `test_api_submissions_sprint3.py` — multipart, regrade, 429 cooldown, owner-scope, file download

### フロントエンドテスト (vitest + @vue/test-utils + jsdom)

- `FileUploadInput.spec.ts` — 拡張子・サイズ・件数バリデーション
- `GradingHistoryAccordion.spec.ts` — toggle / failed 表示 / empty
- `curriculum.store.spec.ts` — regradeSubmission（success / 429）

### E2E（Playwright）

ファイル提出 → 採点成功 → 再採点 → クールダウン → 履歴展開 → ファイルダウンロードの golden path 1 本。

### カバレッジ目標

バックエンド 80%+ を維持。フロントは vitest による論理層カバレッジを開始。E2E は golden path のみ。
