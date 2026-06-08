# Sprint 4 セキュリティレビュー — MEDIUM / LOW フォローアップ

**作成日:** 2026-06-08
**作成者:** Claude Code（security-reviewer agent の Sprint 4 指摘を反映）
**起点コミット:** `03bfe8e fix(sprint-4): address security-reviewer HIGH findings`
**前提:** Sprint 4 完了時に CRITICAL 0 / HIGH × 2 は修正済み。本書は **MEDIUM × 5 + LOW × 4** を後続スプリントへ引き継ぐためのチケット集。

**MEDIUM 5 件のステータス（2026-06-08 更新）:** すべて `feature/sprint-4-security-followups` ブランチで対応済み。下記の各チケットに完了コミットを脚注として追記。

| ID | 状態 | コミット |
|---|---|---|
| MED-1 | ✅ 完了 | `425b2cc fix(sprint-4): block notification links to admin-only routes (MED-1)` |
| MED-2 | ✅ 完了 | `a960426 fix(sprint-4): mask learner email in promote_admin CLI output (MED-2)` |
| MED-3 | ✅ 完了 | `163d172 fix(sprint-4): list_for_admin 404 on missing submission (MED-3)` |
| MED-4 | ✅ 完了 | `21f6505 fix(sprint-4): rate-limit POST /api/me/notifications/{id}/read (MED-4)` |
| MED-5 | ✅ 完了 | `b820ea1 refactor(sprint-4): consolidate router guards into one beforeEach (MED-5)` |

---

## 取り扱い方針

Sprint 3 follow-up doc と同じ運用:
- **MEDIUM**: ~~Sprint 5 着手時に「Sprint 5 計画書」の前提タスクとして取り込む。~~ → main マージ前に独立ブランチで早期完了。
- **LOW**: Sprint 6 以降または保守タスクとしてバックログ。

各チケット項目: 観点 / 該当ファイル:行 / 攻撃シナリオ・リスク / 推奨修正 / テスト方針 / 想定コスト (S=半日, M=1〜2日, L=3日以上)。

---

## MEDIUM

### MED-1: `router.push(link)` で admin route に飛ばせる

- **観点:** UX 攻撃 / 視覚的なフラッシュ (CWE-601 系)
- **該当:** `frontend/src/components/NotificationCenter.vue:60-64`
- **現状:** `onItemClick` の `if (isInternalLink(link)) router.push(link)` は内部 SPA パスを無条件で受け取る。admin が `link="/admin/users"` を含む通知を送ると、受講者がクリックした瞬間 admin route に遷移しようとし、`attachAdminGuard` が `/` に弾く挙動。最終的な権限昇格は起きないが、admin layout が一瞬見える可能性と UX 混乱がある。
- **推奨修正:** `router.resolve(link)` で解決結果の `meta.requiresAdmin` を確認:
  ```ts
  if (isInternalLink(link)) {
    const resolved = router.resolve(link);
    if (!resolved.meta?.requiresAdmin) {
      void router.push(link);
    }
  }
  ```
- **テスト方針:** `link="/admin/users"` の通知を作って、内部リンク扱いだが `router.push` は呼ばれないことを vitest で確認。
- **想定コスト:** S

### MED-2: `promote_admin.py` が email を平文 print

- **観点:** 運用ログ経由の PII 漏洩 (CWE-532)
- **該当:** `backend/scripts/promote_admin.py:31, 34, 38`
- **現状:** `print(f"user not found: {email}", ...)` 等で受講者 email を stdout/stderr にそのまま出す。CloudWatch / Datadog 等にログ集約された場合、DB より広い read access の場所に PII が転記される。
- **推奨修正:** マスク関数を追加してログ用に縮める:
  ```python
  def _mask(email: str) -> str:
      local, _, domain = email.partition("@")
      return f"{local[:2]}***@{domain}"
  print(f"promoted: {_mask(email)}")
  ```
- **テスト方針:** マスク済み文字列に `@` 後半ドメインは残るが、ローカル部最初の 2 文字以外が `*` になることを assert。
- **想定コスト:** S

### MED-3: `list_for_admin` が submission 存在チェックなし

- **観点:** 情報整合性 / UX 一貫性
- **該当:** `backend/app/services/comment.py:46-63`
- **現状:** admin の `GET /api/admin/submissions/{id}/comments` は不正な UUID に対して `[]` を返す（404 にしない）。BOLA リスクは admin が submission 全件を見られるためゼロだが、`/api/admin/submissions/{id}` 詳細とのレスポンス整合性が崩れる。
- **推奨修正:**
  ```python
  async def list_for_admin(db, submission_id) -> list[...]:
      exists = (await db.execute(
          select(Submission.id).where(Submission.id == submission_id)
      )).scalar_one_or_none()
      if exists is None:
          raise SubmissionNotFoundError(str(submission_id))
      ...
  ```
- **テスト方針:** 存在しない UUID で 404 を返すケースを追加。
- **想定コスト:** S

### MED-4: `POST /api/me/notifications/{id}/read` にレート制限なし

- **観点:** DB 負荷 DoS / 既存リソースの abuse
- **該当:** `backend/app/api/me.py:86-122`
- **現状:** mark-read はレート制限なし。1 呼び出しごとに `SELECT Notification + SELECT User` で 2 クエリ。冪等なので state 破壊は無いが、攻撃者は自分のトークンで自分のリソースを無制限に叩ける。
- **推奨修正:** Sprint 3 admin write と同じ `@limiter.limit(lambda: settings.admin_write_rate_limit)` または独立した `me_write_rate_limit` 設定（`60/minute` per IP）。
- **テスト方針:** 既存 admin rate limit テストと同じパターン（5/minute に絞って 7 回突き、429 検出）。
- **想定コスト:** S

### MED-5: router guard 2 系統の暗黙的な順序依存

- **観点:** リファクタ時の事故防止 / 設計の明確化
- **該当:** `frontend/src/router/index.ts:24-44` + `frontend/src/router/admin.ts:48-59`
- **現状:** `attachAdminGuard` が `auth.isAdmin` を読む時点で先行 guard の `await auth.fetchMe()` が解決していることに依存。Vue Router は `beforeEach` を登録順で実行するため現実装は安全だが、将来 `attachAdminGuard` を `router/admin.ts` に集中させたまま順序を入れ替えると admin の bypass / 二重 redirect を起こしうる。
- **推奨修正:** 2 つの guard を 1 つに統合:
  ```ts
  router.beforeEach(async (to) => {
    const auth = useAuthStore();
    if (auth.token && !auth.user) {
      try { await auth.fetchMe(); } catch { auth.logout(); }
    }
    if (to.meta.public !== true && !auth.isAuthenticated) return { name: 'login' };
    if (to.name === 'login' && auth.isAuthenticated) return { name: 'home' };
    if (to.meta.requiresAdmin && !auth.isAdmin) return { name: 'home' };
    return true;
  });
  ```
  `admin.ts` から `attachAdminGuard` を export しなくする。
- **テスト方針:** 既存 `admin.router.spec.ts` の 3 ケースは変更不要。
- **想定コスト:** S

---

## LOW

### LOW-1: admin JWT が localStorage に同居 — blast radius 拡大

- **観点:** XSS による token 窃取
- **該当:** `frontend/src/stores/auth.ts:49-51`
- **現状:** Sprint 3 から続く既知の妥協（LOW-1）。Sprint 4 で admin token も同じ key に保存され、admin 権限を含むトークンが SPA origin の XSS 一発で抜かれる。
- **推奨修正:** httpOnly cookie + SameSite=Strict への移行。実装影響範囲が広いため、認証アーキテクチャ刷新スプリントで扱う。
- **想定コスト:** L

### LOW-2: admin read API にレート制限なし

- **観点:** 流出帯域の制限
- **該当:** `backend/app/api/admin/users.py:23-51`, `backend/app/api/admin/submissions.py:24-55`
- **現状:** `GET /api/admin/users` / `GET /api/admin/submissions` は無制限。`limit=200` まで取得可能なため、stolen admin token があれば全データを高速 export できる。
- **推奨修正:** `@limiter.limit("120/minute")` 程度の緩い読み取り制限を付与。
- **想定コスト:** S

### LOW-3: `cors_allow_origins` のデフォルト値が `localhost:5173`

- **観点:** 構成ハイジン / 本番 misconfiguration 早期発見
- **該当:** `backend/app/config.py:14`
- **現状:** env 未設定でも `http://localhost:5173` が cors_origin として通る。本番では絶対に明示すべき値だが、デフォルトがあるため deployment checklist で気付かないリスク。
- **推奨修正:** デフォルトを外して必須環境変数化:
  ```python
  cors_allow_origins: str  # 必須、デフォルトなし
  ```
- **テスト方針:** 既存 `.env.example` に値があるので開発体験は無変更。本番デプロイで `cors_allow_origins` 未設定だと起動失敗する挙動を確認。
- **想定コスト:** S

### LOW-4: `mark_my_notification_read` で `scalar_one()` の None 未ガード

- **観点:** 防御的コーディング
- **該当:** `backend/app/api/me.py:110-111`
- **現状:** 既読化後の sender 名取得で `.scalar_one()` を使用。FK に `ondelete='RESTRICT'` があるため通常は None にならないが、将来 RESTRICT を緩めたり migration が環境間で異なると `NoResultFound` で 500 になる。
- **推奨修正:** `.scalar_one_or_none()` に変えて、None の場合は `sender_name="(削除済み)"` フォールバック。
- **想定コスト:** S

---

## Sprint 5 取り込み時の優先順位（推奨）

1. ~~**MED-4**（me/notifications/read のレート制限）— DoS 経路を塞ぐ、設定追加だけで完了。~~ → `21f6505` で完了
2. ~~**MED-1**（router.push の admin route 防御）— UX 混乱を引き起こすため、admin ダッシュボード本格運用前に。~~ → `425b2cc` で完了
3. ~~**MED-3**（list_for_admin の 404 整合）— admin 詳細との不整合を直す。~~ → `163d172` で完了
4. ~~**MED-2**（promote_admin のマスク）— 運用前に。~~ → `a960426` で完了
5. ~~**MED-5**（guard 統合）— Sprint 4 リファクタの余裕枠で。~~ → `b820ea1` で完了
6. **LOW-2, LOW-3, LOW-4** — Sprint 6 以降。
7. **LOW-1**（Cookie 化）— 認証刷新タイミングまで保留。