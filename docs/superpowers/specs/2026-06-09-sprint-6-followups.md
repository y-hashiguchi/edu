# Sprint 6 レビュー — MEDIUM / LOW フォローアップ

**作成日:** 2026-06-09
**作成者:** Claude Code（code-reviewer + security-reviewer の Sprint 6 指摘を反映）
**起点コミット:** `7ddd63a fix(sprint-6): address review HIGH findings`
**前提:** Sprint 6 完了時に CRITICAL 0 / HIGH × 3 修正済み（Sec MED-2 = LearnerCommentOut の `is_admin_authored` 追加、Sec HIGH-1 = Notification fanout を `notification_service.send` 経由化、Code HIGH-1 = `create_comment` の commit 責務を caller へ）。

本書は **未修正の MEDIUM × 2 + LOW × 2** を後続スプリントへ引き継ぐためのチケット集。残:
- MED-2 (bulk weakness 閾値の明文化) — 判断保留
- MED-6 (admin-on-admin dashboard threat model) — 判断保留
- LOW-4 (vitest CVE upgrade)
- LOW-5 (Sprint 5 INFRA carry-over)

| ID | 状態 | コミット |
|---|---|---|
| HIGH-3 | ✅ 完了 | `1c36856 fix(sprint-6): tree-wide fanout + CTE depth cap + self-loop guard (HIGH-3, MED-1)` |
| MED-1 | ✅ 完了 | `1c36856`（HIGH-3 と同梱） |
| MED-3 / MED-4 / MED-5 | ✅ 完了 | `89ca06f fix(sprint-6): batch follow-ups (MED-3/4/5 + LOW-1/2/3)` |
| MED-2 / MED-6 | 未着手（判断保留） | — |
| LOW-1 / LOW-2 / LOW-3 | ✅ 完了 | `89ca06f` |
| LOW-4 / LOW-5 | 未着手 | — |

---

## 取り扱い方針

Sprint 4 / Sprint 5 follow-up doc と同じ運用:
- **HIGH**: Sprint 7 着手時の前提タスクとして取り込み必須。
- **MEDIUM**: Sprint 7 計画書の前提タスクとして取り込む。
- **LOW**: Sprint 8 以降または保守タスクとしてバックログ。

各チケット項目: 観点 / 該当ファイル:行 / リスク / 推奨修正 / テスト方針 / 想定コスト (S=半日, M=1〜2日, L=3日以上)。

---

## HIGH

### HIGH-3 (code-review): Notification fanout は ancestor のみ traversal、sibling 枝の admin に届かない

- **観点:** 設計の正確性 / UX 一貫性
- **該当:** `backend/app/services/comment.py:142-160`（`_thread_admin_authors`）
- **現状:** CTE は `parent_id` を辿って先祖だけを訪問。スレッドが分岐し、admin A が trunk、admin B が trunk へ直接返信し、その後学習者が trunk に返信した場合、admin B は学習者の返信から見ると ancestor ではないため通知されない。docstring 上の「参加している admin 全員」と齟齬。
- **リスク:** 複数 admin が参加するスレッドで一部の通知漏れ。現在の運用 (主に線形スレッド) では実害なし。
- **推奨修正:** thread の root を求め、root から descendant traversal で全 admin author を集める CTE に書き換える:
  ```sql
  WITH RECURSIVE root_finder AS (
    SELECT id, parent_id, author_user_id FROM instructor_comments WHERE id = :start
    UNION ALL
    SELECT c.id, c.parent_id, c.author_user_id
    FROM instructor_comments c JOIN root_finder r ON c.id = r.parent_id
  ),
  root AS (SELECT id FROM root_finder WHERE parent_id IS NULL LIMIT 1),
  thread AS (
    SELECT id, parent_id, author_user_id FROM instructor_comments WHERE id = (SELECT id FROM root)
    UNION ALL
    SELECT c.id, c.parent_id, c.author_user_id
    FROM instructor_comments c JOIN thread t ON c.parent_id = t.id
  )
  SELECT DISTINCT t.author_user_id FROM thread t JOIN users u ON u.id = t.author_user_id
  WHERE u.is_admin = TRUE
  ```
- **テスト方針:** sibling 枝シナリオを追加（admin A trunk + admin B が trunk へ直接返信 + 学習者 trunk へ返信 → 通知 2 件、admin A と admin B 両方）。
- **想定コスト:** S

---

## MEDIUM

### MED-1 (code-review + sec): WITH RECURSIVE CTE に depth cap と cycle guard なし

- **観点:** DoS / 防御的設計 (CWE-834)
- **該当:** `backend/app/services/comment.py:122-160`（`_ancestor_has_admin` と `_thread_admin_authors`）
- **現状:** `UNION ALL` のみで、depth カウンタや `CYCLE` 句なし。FK の CASCADE で構造的サイクルは作れないが、深いスレッド（1000 級）が現れたら時間 O(depth) で劣化、cycle が DB 直操作で生まれたら無限再帰の可能性。
- **推奨修正:**
  1. Alembic 1 リビジョンで CHECK 制約追加: `CHECK (parent_id IS NULL OR parent_id != id)`
  2. CTE に depth カウンタを追加し `WHERE depth < 50` で制限
  3. API 層で深いスレッドを reject (`MAX_THREAD_DEPTH = 10` を `app.config` に)
- **テスト方針:** 11 階層のスレッドを post → POST `/api/me/.../comments` が 400/422 を返す（API 層キャップ）
- **想定コスト:** S

### MED-2 (code-review): `compute_top_weakness_tags_bulk` は `MIN_TAG_SUBMISSIONS` を緩く扱う、Sprint 5 `compute_weakness` との非対称

- **観点:** UX 一貫性
- **該当:** `backend/app/services/weakness.py:102-165`
- **現状:** Sprint 5 `compute_weakness` は 3 件未満を suppress、2 件未満タグを除外。Bulk 版は 2 件以上タグを優先するが空のとき 1 件タグも返す fallback あり。受講者の dashboard では「データ不足」、admin の一覧では「AI協調」と表示される非対称が起きうる。
- **推奨修正:** `BULK_MIN_SUBMISSIONS` 定数を `app.services.weakness` に追加、明示的に「a」「b」のどちらの基準で動くか宣言。`compute_top_weakness_tags_bulk` の docstring に Sprint 5 との差分を明示。fallback 経路 (1 件タグ) を残すかは方針判断、本 follow-up で結論を出す。
- **想定コスト:** S

### MED-3 (code-review): `CommentThreadNode` 再帰コンポーネントに depth cap なし

- **観点:** UX 崩壊
- **該当:** `frontend/src/components/CommentThreadNode.vue:83`
- **現状:** `padding-left: depth * 16px` をそのまま積む。20 階層で 320px、50 階層で 800px、サーバ側 cap が入るまで UI レイアウトが崩壊。
- **推奨修正:** `:style="{ paddingLeft: \`${Math.min(depth, 6) * 16}px\` }"` で表示インデントを 6 階層で頭打ちに。深いノードは「︙ N 件の返信」サマライズボタンの後ろに収納（後続スプリント）。
- **想定コスト:** S

### MED-4 (code-review): `fetchUserDashboard` がエラーを silently 飲み込む

- **観点:** UX デバッガビリティ
- **該当:** `frontend/src/stores/admin.ts:144-150`
- **現状:** catch ブロックが null を返すだけで store.error は設定されない。admin が dashboard セクションの欠落を「データなし」と誤認する。
- **推奨修正:** catch 内で `this.error = '受講者ダッシュボードの読み込みに失敗しました'` をセット、view 側で expose。または専用 `dashboardError` フィールドを追加して既存 store.error と区別。
- **想定コスト:** S

### MED-5 (code-review): 返信投稿時に busy state なし、二重 submit 可能

- **観点:** UX / データ整合
- **該当:** `frontend/src/components/TaskSubmissionCard.vue:75-86` と `frontend/src/components/CommentThreadNode.vue:108`
- **現状:** `onReply` が in-flight でも `reply-submit` ボタンが押せ、ダブルタップで 2 件投稿。さらに `commentsError` を先頭でクリアしないため stale エラーが残る。
- **推奨修正:**
  1. `commentsError.value = null` を `onReply` 先頭に追加
  2. `replyBusy` ref を CommentThread → CommentThreadNode へ prop ドリル、submit ボタンに `:disabled="replyBusy"`
- **想定コスト:** S

### MED-6 (sec): admin が他 admin の dashboard を見られる

- **観点:** プライバシー / threat model 整理
- **該当:** `backend/app/api/admin/user_dashboard.py:38`
- **現状:** `user_id` の `is_admin` チェックなし。admin A が admin B の dashboard を見られる。現実的には admin の submission は通常ないので空 dashboard が返るだけだが、threat model 上は意図的か明示すべき。
- **推奨修正:** 仕様判断 — 現状維持で「admin はトラスト」と明文化するか、`user.is_admin == True` のときは 404 を返すか。後続スプリントで決定。
- **想定コスト:** S（実装は 3 行、判断に時間）

---

## LOW

### LOW-1 (code-review): `InvalidParentError` の定義位置が usage より後

- **該当:** `backend/app/services/comment.py:44`（raise）vs `114`（class）
- **現状:** Python は call time に解決するため動作上問題ないが、慣習上 exception クラスは module top に配置すべき。
- **推奨修正:** `InvalidParentError` と `UnauthorizedThreadError` を `SubmissionNotFoundError` の隣 (ファイル冒頭) に移す。
- **想定コスト:** S

### LOW-2 (code-review): `NotificationCenter.vue` の JSDoc が古い

- **該当:** `frontend/src/components/NotificationCenter.vue:3`
- **現状:** 「for logged-in learners」とあるが Sprint 6 で admin layout でも使われるようになった。
- **推奨修正:** コメントを「for both learners and admin instructors」に更新。
- **想定コスト:** S

### LOW-3 (code-review): `api/me.py` 中の inline import `from sqlalchemy import select`

- **該当:** `backend/app/api/me.py:170` 付近
- **現状:** 他は top-level import なのに inline 1 箇所だけ残っている（Sprint 5 以前から）。
- **推奨修正:** top-level に移動。
- **想定コスト:** S

### LOW-4 (sec): vitest CRITICAL CVE (GHSA-5xrq-8626-4rwp)

- **該当:** `frontend/package.json` vitest dev dep
- **現状:** dev tool 専用、本番ビルドには含まれない。`vitest --ui` 実行時のローカル攻撃面のみ。
- **推奨修正:** vitest の非破壊的パッチリリースに upgrade。CI で `npm audit --audit-level=critical` を回す。
- **想定コスト:** S

### LOW-5 (existing): Sprint 5 INFRA-1 (Playwright headless) と INFRA-2 (動作確認) は依然残

- **観点:** 引き継ぎ
- **現状:** Sprint 5 follow-up doc に既出、Sprint 6 でも未着手。
- **推奨修正:** Sprint 7 か Sprint 8 で同梱を判断。

---

## Sprint 7 取り込み時の優先順位（推奨）

1. ~~**MED-1**（CTE depth cap + cycle guard）~~ → `1c36856` で完了
2. ~~**HIGH-3**（Notification fanout を tree-wide 化）~~ → `1c36856` で完了
3. **MED-2**（bulk weakness 閾値の明文化）— Sprint 5 との非対称解消
4. **MED-4**（dashboard fetch エラー surface）— admin UX
5. **MED-5**（reply busy state + commentsError クリア）— 受講者 UX
6. **MED-3**（CommentThreadNode 表示 cap）— UI 崩壊回避
7. **MED-6**（admin-on-admin dashboard 仕様判断）— threat model
8. **LOW-1, LOW-2, LOW-3** — まとめてリファクタ
9. **LOW-4**（vitest upgrade）
10. **LOW-5**（Sprint 5 INFRA tickets）
