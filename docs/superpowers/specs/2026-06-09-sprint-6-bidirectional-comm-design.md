# Sprint 6 設計書 — 受講者×講師の双方向コミュニケーション

**作成日:** 2026-06-09
**作成者:** Claude Code（superpowers:brainstorming セッション）
**起点コミット:** `842070d docs(sprint-5): mark LOW-3/4/5 as completed in follow-up doc`（main、Sprint 5 + follow-up 完了状態）
**位置づけ:** Sprint 5 計画書の「後続 Sprint」として挙げられていた「コメント返信（受講者→講師、スレッド化）」と「講師向け admin ダッシュボード強化」を Sprint 6 として統合した上位仕様。`docs/superpowers/plans/2026-06-09-ai-tutor-curriculum-sprint-6.md`（後続で writing-plans により作成）の根拠。

---

## 目的とサクセスクライテリア

**目的:** Sprint 4 で構築した admin → 受講者の単方向コメント/通知を **双方向化** し、Sprint 5 で受講者本人にだけ可視化された弱点分析・推奨を **講師側からも参照できる** ようにする。教育の対話的フィードバックループを成立させる。

**サクセスクライテリア:**

1. admin が投稿したコメントに対し、受講者が返信できる。受講者の返信に対し admin がさらに返信できる（任意深さのスレッド）。
2. 受講者の返信が投稿されると、スレッドに参加している admin (trunk 投稿者および中間返信者) 全員の Sprint 4 既存通知センターに新規通知が届く。
3. admin が AdminLayout 内で受講者と同じ NotificationCenter ベルアイコンを使い、返信を見落とさない動線が成立する。
4. admin が任意の受講者の詳細画面で、その受講者の Sprint 5 ダッシュボード（弱点・推奨・進捗）と同等のビューを参照できる（AI 一言は受講者プライベートとして除外）。
5. admin の受講者一覧画面で、各受講者の「弱点 1 位タグ」が 1 列として表示される。N 名分の集計が 1 回の SELECT で完結し、N+1 を起こさない。
6. Sprint 1〜5 と同水準のテスト（backend 80%+ カバレッジ、TDD 厳格、MCP 駆動の手動 E2E 1 シナリオ）が揃う。

---

## スコープ境界

### 含む（Sprint 6）

- `InstructorComment.parent_id` カラム（self-FK、nullable、CASCADE）+ Alembic 1 リビジョン
- `services/comment.py` 拡張: `post_reply / _ancestor_has_admin / _thread_admin_authors`
- 既存 `services/notification.py` 経由で返信時の admin 宛 Notification 自動生成
- `services/weakness.py` 拡張: `compute_top_weakness_tags_bulk(user_ids) -> dict[UUID, str | None]`
- API:
  - 新規 `POST /api/me/submissions/{id}/comments` — 受講者から返信投稿
  - 新規 `GET /api/admin/users/{user_id}/dashboard` — admin が任意受講者の dashboard を取得
  - 既存 admin/learner comments API レスポンスに `parent_id` 追加
  - 既存 `GET /api/admin/users` レスポンスに `top_weakness_tag` 追加
  - 既存 `POST /api/admin/submissions/{id}/comments` で `parent_id` を任意で受付
- Frontend:
  - `CommentThread.vue` ツリー表示拡張 + 返信投稿 UI（再帰描画ノード `CommentThreadNode.vue` 新設）
  - `TaskSubmissionCard.vue` 受講者側返信ボタン統合
  - `AdminLayout.vue` に既存 `NotificationCenter.vue` を統合
  - `AdminUsersView.vue` に top_weakness_tag column
  - `AdminUserDetailView.vue` に受講者 dashboard セクション（既存 ProgressSummaryCard / WeaknessCard / RecommendationsCard を再利用、nudge セクション無し）
  - `stores/admin.ts` に `fetchUserDashboard(userId)` 追加
- テスト一式: backend 新規 7 ファイル、frontend 新規/拡張 4 ファイル、MCP 駆動 E2E 1 シナリオ
- README 更新（Sprint 6 完了マーク）、設計書 03/04/05/06 への Sprint 6 セクション追記

### 含まない（後続スプリント）

| 候補 | 送り先 | 理由 |
|---|---|---|
| 採点の非同期化（queue + worker） | Sprint 7 候補 | インフラ追加が独立して重い |
| broadcast 通知（コホート全員宛） | Sprint 7 候補 | 監査・誤送リスク設計が独立 |
| リアルタイム通知（SSE/WS） | Sprint 8+ | インフラ刷新タイミング |
| コホート集計（全受講者の弱点分布等） | Sprint 7 候補 | 集計指標・UI 設計が単独 sprint 相当 |
| curriculum 編集機能（admin GUI） | 別 sprint | 完全新ドメイン、LOW-6 同時対応 |
| Playwright headless 本セット（INFRA-1） | Sprint 7 候補 | E2E は Sprint 4/5 同様 MCP 駆動継続 |
| audit log テーブル | 本番化 sprint | 監査要件未定義 |
| スレッドの depth 制限 | Sprint 6 では制限なし | UX 上問題が出てから対処 (YAGNI) |
| 返信通知のユーザー側 disable 設定 | 後続 | 必要性が出てから |

---

## 主要意思決定（Sprint 6 計画時点）

| # | 判断項目 | 選択 | 理由 |
|---|---|---|---|
| 1 | 主軸 | 受講者×講師の双方向コミュニケーション | Sprint 4/5 資産の自然な拡張、UX レバレッジ高 |
| 2 | スコープ | コメント返信 + admin NotificationCenter + admin 受講者 dashboard + 弱点 column | コホート集計は Sprint 7 へ |
| 3 | スレッド構造 | `parent_id` self-FK、depth 制限なし、CASCADE | YAGNI、自然なツリー |
| 4 | 受講者の権限 | trunk 投稿不可、admin author を辿れる先祖を持つ comment にのみ返信 | スレッド hijack 防止 |
| 5 | 通知 | 既存 Notification を双方向に再利用、新規テーブル無し | Sprint 4 資産再利用 |
| 6 | admin 受講者 dashboard の nudge | 含めない（受講者プライベートな AI アドバイス） | プライバシー配慮 |
| 7 | 弱点 column の集計 | リクエスト時 bulk SELECT + Python 集計（1 クエリ） | N+1 回避、Sprint 5 ロジック再利用 |
| 8 | bulk 集計のしきい値 | `MIN_TAG_SUBMISSIONS` 適用なし、提出 0 件のみ null | 一覧で見える機会を最大化 |
| 9 | レート制限 | 既存 `me_write_rate_limit` (60/min) 再利用 | 設定追加なし、Sprint 5 と一貫 |
| 10 | UI 文言 | 「弱点」ではなく「もう一押し」 | Sprint 5 と一貫 |
| 11 | テスト戦略 | TDD 厳格 + MCP 駆動 E2E 1 シナリオ | Sprint 4/5 と同水準維持 |
| 12 | INFRA-1 同梱 | しない（Sprint 7 候補） | スコープ純化 |
| 13 | LOW-6 同梱 | しない（curriculum 編集と同タイミング、別 sprint） | スコープ純化 |
| 14 | Notification 重複 | 1 つの返信で複数 admin が候補なら全員に送信 | UX 上の確実性 |
| 15 | スレッド hijack 防御の SQL | WITH RECURSIVE CTE で先祖に admin が居るか確認 | 1 クエリで完結 |

---

## アーキテクチャ全体像

```
┌────────────────────────────────────────────────────────────────────┐
│  Frontend                                                          │
│  ├─ 受講者側                                                       │
│  │   ├─ TaskSubmissionCard.vue                                     │
│  │   │   └─ CommentThread.vue (Modify: 返信ツリー + 返信ボタン)    │
│  │   └─ NotificationCenter (既存、変更なし)                        │
│  └─ admin 側                                                       │
│      ├─ AdminLayout.vue (Modify: NotificationCenter 統合)          │
│      ├─ AdminUsersView.vue (Modify: 弱点 1 位 column 追加)         │
│      └─ AdminUserDetailView.vue (Modify: 受講者ダッシュ section)   │
└────────────────────────────────────────────────────────────────────┘
                            ▲
                            │
┌────────────────────────────────────────────────────────────────────┐
│  Backend                                                           │
│  ├─ models/instructor_comment.py (Modify: parent_id self-FK)       │
│  ├─ services/                                                      │
│  │   ├─ comment.py (Modify: reply 用関数 + notification 自動生成)  │
│  │   ├─ weakness.py (Modify: compute_top_weakness_tags_bulk)       │
│  │   └─ dashboard.py (既存、admin から user_id 指定で再利用)       │
│  ├─ api/                                                           │
│  │   ├─ me.py (Modify: POST /api/me/submissions/{id}/comments)     │
│  │   ├─ admin/comments.py (Modify: parent_id 受付/返却)            │
│  │   ├─ admin/users.py (Modify: 一覧 response に top_weakness_tag) │
│  │   └─ admin/user_dashboard.py (Create: admin 用 dashboard API)   │
│  └─ alembic: parent_id カラム追加 (1 リビジョン)                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## データモデル

### `app/models/instructor_comment.py`（既存ファイルの拡張）

```python
class InstructorComment(Base):
    # 既存カラム + 以下:
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("instructor_comments.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
```

- `parent_id` NULL = trunk（admin 発の最上位コメント）
- `parent_id` 非 NULL = 返信
- self-FK CASCADE: trunk 削除で子返信も連鎖削除
- 既存データ: 全て `parent_id = NULL` で互換性維持
- Alembic マイグレーション: `ALTER TABLE instructor_comments ADD COLUMN parent_id UUID NULL REFERENCES instructor_comments(id) ON DELETE CASCADE` + index 作成

---

## API 仕様

### 受講者向け新規 API

#### `POST /api/me/submissions/{submission_id}/comments`

**Auth:** Bearer JWT (`get_current_user`).
**Rate limit:** `me_write_rate_limit` (60/min) 再利用。

**Request:**
```jsonc
{
  "parent_id": "uuid",   // 必須、admin が辿れる先祖を持つ comment id
  "body": "string"       // max 2000 chars
}
```

**Response 201:**
```jsonc
{
  "id": "uuid",
  "submission_id": "uuid",
  "author_user_id": "uuid",
  "author_name": "受講者名",
  "parent_id": "uuid",
  "body": "string",
  "created_at": "iso8601",
  "updated_at": "iso8601"
}
```

**エラー応答:**
- 400 `parent_id` が同じ submission に属さない
- 403 親 comment の先祖を辿っても admin author が居ない（スレッド hijack 防止）
- 404 submission が存在しないまたは他人の submission（BOLA、404 で統一）
- 422 `parent_id` 欠落 / body 制約違反

**副作用:**
- スレッド参加 admin (trunk 投稿者 + 中間 admin 返信者) 全員宛に Notification 自動生成
  - sender_user_id = 学習者
  - title = "返信が届きました"
  - body = 学習者コメント本文の先頭 120 文字
  - link = `/admin/submissions/{submission_id}`

### admin API 変更

#### `GET /api/admin/submissions/{submission_id}/comments`

レスポンスの各 item に `parent_id: uuid | null` 追加。それ以外は既存通り。

#### `POST /api/admin/submissions/{submission_id}/comments`

リクエストに optional `parent_id: uuid | null` を追加。
- `parent_id` null または欠落 → trunk
- `parent_id` 設定 → 親 comment が同 submission に属することを検証

#### `GET /api/admin/users`

レスポンスの各 item に `top_weakness_tag: string | null` 追加。既存 `AdminUserSummary` のフィールド（`completed_phases`, `in_progress_phases` 等）はそのまま。

```jsonc
{
  "items": [
    {
      "id": "uuid",
      "email": "string",
      "name": "string",
      "is_admin": false,
      "created_at": "iso8601",
      "completed_phases": 0,        // 既存
      "in_progress_phases": 1,      // 既存
      "top_weakness_tag": "AI協調"  // 追加、提出 0 件なら null
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

#### `GET /api/admin/users/{user_id}/dashboard`（新規）

**Auth:** Bearer JWT + admin 権限 (`get_current_admin`).
**所有権:** admin は任意の受講者の dashboard を見られる。404 は user_id 不在のみ。

**Response 200:**
```jsonc
{
  "progress_summary": { /* Sprint 5 と同形式 */ },
  "weakness": { /* Sprint 5 と同形式 */ },
  "recommendations": { /* Sprint 5 と同形式 */ }
  // nudge セクションは含めない (受講者プライベート)
}
```

サーバ実装方針:

- 既存 `compose_dashboard(db, *, claude, embedding_client, user_id)` のシグネチャは変えない
- 新規 wrapper `compose_dashboard_for_admin(db, *, embedding_client, user_id) -> AdminDashboardData` を `services/dashboard.py` に追加
- `compose_dashboard_for_admin` は internal で progress_summary / weakness / recommendation の 3 サブサービスを直接呼び、`nudge.get_or_generate` は呼ばない
- 既存サブサービス関数は何も変更しない
- `AdminDashboardData` は `DashboardData` から `nudge` を除いた frozen dataclass を新規定義

これにより既存 `/api/me/dashboard` 経路は影響なし、admin 経路は独立した orchestrator を持つ。

---

## コメントスレッドのアルゴリズム

### バリデーション順序（受講者投稿時）

```python
async def post_reply(db, *, submission_id, learner_user_id, parent_id, body):
    # 1. 親 comment が同じ submission に属するか
    parent = await db.execute(
        select(InstructorComment).where(InstructorComment.id == parent_id)
    )
    parent = parent.scalar_one_or_none()
    if parent is None or parent.submission_id != submission_id:
        raise InvalidParentError()  # → 400

    # 2. submission の所有者が学習者本人か (BOLA fence)
    sub = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    sub = sub.scalar_one_or_none()
    if sub is None or sub.user_id != learner_user_id:
        raise SubmissionNotFoundError()  # → 404

    # 3. 先祖を辿って admin author が居るか
    if not await _ancestor_has_admin(db, parent_id):
        raise UnauthorizedThreadError()  # → 403

    # 4. comment 作成
    reply = InstructorComment(
        submission_id=submission_id,
        author_user_id=learner_user_id,
        parent_id=parent_id,
        body=body,
    )
    db.add(reply)
    await db.flush()

    # 5. Notification 自動生成 (スレッド参加 admin 全員)
    admin_ids = await _thread_admin_authors(db, parent_id)
    for admin_id in admin_ids:
        db.add(Notification(
            recipient_user_id=admin_id,
            sender_user_id=learner_user_id,
            title="返信が届きました",
            body=body[:120],
            link=f"/admin/submissions/{submission_id}",
        ))
    await db.commit()
    return reply
```

### 先祖チェック（WITH RECURSIVE CTE）

```python
async def _ancestor_has_admin(db, comment_id: UUID) -> bool:
    stmt = text("""
        WITH RECURSIVE ancestors AS (
            SELECT id, parent_id, author_user_id
            FROM instructor_comments WHERE id = :start
            UNION ALL
            SELECT c.id, c.parent_id, c.author_user_id
            FROM instructor_comments c
            JOIN ancestors a ON c.id = a.parent_id
        )
        SELECT 1 FROM ancestors a
        JOIN users u ON u.id = a.author_user_id
        WHERE u.is_admin = TRUE LIMIT 1
    """)
    result = await db.execute(stmt, {"start": comment_id})
    return result.first() is not None


async def _thread_admin_authors(db, parent_comment_id: UUID) -> set[UUID]:
    # 同じスレッドの全 admin author を返す (重複なし)
    stmt = text("""
        WITH RECURSIVE ancestors AS (
            SELECT id, parent_id, author_user_id
            FROM instructor_comments WHERE id = :start
            UNION ALL
            SELECT c.id, c.parent_id, c.author_user_id
            FROM instructor_comments c
            JOIN ancestors a ON c.id = a.parent_id
        )
        SELECT DISTINCT a.author_user_id FROM ancestors a
        JOIN users u ON u.id = a.author_user_id
        WHERE u.is_admin = TRUE
    """)
    rows = (await db.execute(stmt, {"start": parent_comment_id})).all()
    return {r.author_user_id for r in rows}
```

---

## Bulk 弱点集計（admin users 一覧用）

```python
# services/weakness.py に追加
async def compute_top_weakness_tags_bulk(
    db: AsyncSession,
    user_ids: list[uuid.UUID],
) -> dict[uuid.UUID, str | None]:
    """1 クエリで全 user の latest graded scores を取得し、user 別に
    タグ平均を計算して上位 1 つを返す。N+1 を回避する。"""
    if not user_ids:
        return {}

    stmt = (
        select(
            Submission.user_id, Submission.id,
            GradingAttempt.score, Submission.phase, Submission.task_no,
        )
        .join(GradingAttempt, GradingAttempt.submission_id == Submission.id)
        .where(
            Submission.user_id.in_(user_ids),
            GradingAttempt.status == "graded",
        )
        .order_by(Submission.user_id, Submission.id,
                  GradingAttempt.created_at.desc())
        .distinct(Submission.user_id, Submission.id)
    )
    rows = (await db.execute(stmt)).all()

    by_user: dict[uuid.UUID, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for user_id, _sub_id, score, phase, task_no in rows:
        try:
            tags = get_task_skill_tags(phase, task_no)
        except KeyError:
            continue
        for tag in tags:
            by_user[user_id][tag].append(float(score))

    out: dict[uuid.UUID, str | None] = {}
    for uid in user_ids:
        tag_scores = by_user.get(uid, {})
        # MIN_TAG_SUBMISSIONS は適用しない (column の見える機会を最大化)
        if not tag_scores:
            out[uid] = None
            continue
        worst = min(
            tag_scores.items(),
            key=lambda kv: (mean(kv[1]), kv[0]),
        )
        out[uid] = worst[0]
    return out
```

**性能想定:** 100 名 × 平均 5 件提出 = 500 行返却。Python 集計は ms オーダー。SELECT 1 回で完了するため admin users 一覧 API の追加コストは無視できる。

---

## Frontend 設計

### CommentThread.vue（拡張）

flat な `comments` 配列を `parent_id` で tree 構造に組み立て、再帰描画。新規 `CommentThreadNode.vue` で各ノードをレンダリング。

- 受講者側: admin author を先祖に持つコメントの末端にのみ「返信」ボタンを表示
- admin 側: 全ノードに「返信」ボタン、加えて trunk 投稿ボタン

depth インデント: `padding-left: depth * 16px`。3 階層を超える深いネストは右寄せでまとめ、UX 上の混乱を抑制。

### TaskSubmissionCard.vue（拡張）

既存「コメント (N)」セクションを `CommentThread` の新インターフェイス対応に差し替え。

```vue
<CommentThread
  :comments="comments"
  :can-reply="true"
  :can-post-trunk="false"
  @reply="onReply"
/>
```

`onReply` は新規 `api.postMyReply(submissionId, parentId, body)` を呼ぶ。

### AdminLayout.vue（拡張）

```vue
<template>
  <header>
    <h1>管理者ダッシュボード</h1>
    <NotificationCenter />  <!-- 既存実装をそのまま埋め込み -->
    <UserMenu />
  </header>
  <RouterView />
</template>
```

`NotificationCenter` は `recipient_user_id = current_user.id` で受信箱が絞られるため、admin が見ても問題なし。Sprint 4 MED-1 の admin route 防御も既に効いている。

### AdminUsersView.vue（拡張）

既存テーブルに 1 列追加（既存の名前 / メール / 完了フェーズ / 進行中フェーズ などはそのまま）:

```vue
<th>もう一押し</th>
...
<td>
  <span v-if="u.top_weakness_tag" class="tag">{{ u.top_weakness_tag }}</span>
  <span v-else class="muted">—</span>
</td>
```

文言は Sprint 5 と一貫させて「もう一押し」。実装時点の既存テンプレ（テーブルかカードか）に合わせて配置を判断する。

### AdminUserDetailView.vue（拡張）

既存の受講者詳細に 1 セクション追加:

```vue
<section v-if="dashboardData">
  <h2>受講者のダッシュボード</h2>
  <ProgressSummaryCard :data="dashboardData.progress_summary" />
  <WeaknessCard :data="dashboardData.weakness" />
  <RecommendationsCard :items="dashboardData.recommendations.items" />
  <!-- nudge セクションは API 応答に含まれないため表示しない -->
</section>
```

Sprint 5 のカード 3 つを再利用、新規実装ゼロ。

### stores/admin.ts（拡張）

```typescript
async fetchUserDashboard(userId: string): Promise<AdminDashboardResponse> {
  return api.getAdminUserDashboard(userId);
}
```

---

## Notification 生成ルール（双方向）

| トリガー | 送信者 | 受信者 | title | link |
|---|---|---|---|---|
| admin が trunk 投稿（既存） | admin | submission 所有者の受講者 | 講師からコメントが届きました | `/phases/{phase}` |
| **受講者が返信（新規）** | **受講者** | **スレッド参加 admin 全員** | **返信が届きました** | **`/admin/submissions/{id}`** |
| **admin が返信に返信（新規）** | **admin** | **submission 所有者の受講者** | **講師から返信が届きました** | **`/phases/{phase}`** |

---

## テスト戦略

### Backend テスト（新規 7 ファイル前後）

| ファイル | 観点 |
|---|---|
| `test_models_sprint6.py` | InstructorComment.parent_id round-trip / self-FK CASCADE / parent_id NULL = trunk |
| `test_comment_thread_service.py` | post_reply happy path / parent 別 submission で 400 / 親が他人スレッドで 403 / 先祖に admin が無いと 403 / parent_id 必須 |
| `test_comment_notification_side_effect.py` | 受講者返信時に admin 宛 Notification 生成 / 複数 admin 参加時に複数生成 / link が正しい URL |
| `test_weakness_bulk.py` | 0 件 user は null / 提出ある user は top タグ返却 / 同点はタグ名タイブレーク / 全 user 一括取得が 1 クエリで完結 |
| `test_admin_user_dashboard_api.py` | 認証 401 / 非 admin 403 / 不在 user_id で 404 / 通常応答 (nudge 含まれない) |
| `test_admin_users_api_sprint6.py` | 既存 users 一覧テスト拡張: top_weakness_tag が null か str / cold-start user は null |
| `test_me_reply_api.py` | 受講者返信 happy path / parent 必須 422 / 他人 submission 403 / レート制限 |

### Frontend テスト（新規/拡張 4 ファイル）

| ファイル | 観点 |
|---|---|
| `CommentThread.spec.ts`（拡張） | flat → tree 展開 / depth インデント / canReply 制御 / 返信投稿 emit |
| `AdminUsersView.spec.ts`（新規/拡張） | top_weakness_tag column 表示 / null のとき `—` 表示 |
| `AdminUserDetailView.spec.ts`（拡張） | dashboard セクション表示 / nudge セクション非描画 |
| `admin.store.spec.ts`（拡張） | fetchUserDashboard 成功・失敗 |

### MCP 駆動 E2E（Sprint 4/5 同様）

```
シナリオ: 受講者×講師の往復コミュニケーション
1. admin でログイン → /admin/submissions/{id} へ
2. trunk コメント投稿 → 受講者宛 Notification 生成
3. 受講者でログイン → ベル通知に 1 件
4. 通知クリック → /phases/X へ、コメント表示
5. 受講者が返信 → admin 宛 Notification 生成
6. admin に戻る → admin の NotificationCenter に 1 件
7. 通知クリック → admin で返信表示、admin がさらに返信
8. AdminUsersView を開き、当該受講者の top_weakness_tag が表示確認
9. AdminUserDetailView で dashboard セクション描画確認
```

スクリーンショット 4-5 枚。

### モック戦略

- Claude 呼び出しは AsyncMock（Sprint 5 と同じ）
- RAG 呼び出しは monkeypatch
- `compute_top_weakness_tags_bulk` は実 DB で動作、conftest 拡張で複数受講者をシードする helper（`seed_multiple_learners_with_submissions`）追加

### カバレッジ目標

- backend 80%+
- frontend vitest カバレッジ未強制（既存方針）

---

## ファイル構造（差分のみ）

```
edu/
├── README.md                                              # Modify: Sprint 6 完了マーク
├── backend/
│   ├── app/
│   │   ├── models/instructor_comment.py                   # Modify: parent_id self-FK
│   │   ├── schemas/comment.py                             # Modify: parent_id 追加
│   │   ├── schemas/admin.py                               # Modify: top_weakness_tag 追加
│   │   ├── schemas/dashboard.py                           # Modify: admin 用 (nudge 無し) variant
│   │   ├── services/
│   │   │   ├── comment.py                                 # Modify: post_reply + helpers
│   │   │   ├── weakness.py                                # Modify: compute_top_weakness_tags_bulk
│   │   │   └── dashboard.py                               # Modify: compose_dashboard_for_admin wrapper
│   │   ├── api/
│   │   │   ├── me.py                                      # Modify: POST /api/me/submissions/{id}/comments
│   │   │   ├── admin/comments.py                          # Modify: parent_id 受付/返却
│   │   │   ├── admin/users.py                             # Modify: top_weakness_tag
│   │   │   └── admin/user_dashboard.py                    # Create: admin 用 dashboard API
│   │   └── main.py                                        # Modify: admin/user_dashboard router 登録
│   ├── alembic/versions/
│   │   └── 20260609_<rev>_sprint6_comment_parent_id.py    # Create
│   └── tests/
│       ├── conftest.py                                    # Modify: seed_multiple_learners helper
│       ├── test_models_sprint6.py                         # Create
│       ├── test_comment_thread_service.py                 # Create
│       ├── test_comment_notification_side_effect.py       # Create
│       ├── test_weakness_bulk.py                          # Create
│       ├── test_admin_user_dashboard_api.py               # Create
│       ├── test_admin_users_api_sprint6.py                # Create
│       └── test_me_reply_api.py                           # Create
└── frontend/
    └── src/
        ├── types/comment.ts                               # Modify: parent_id 追加
        ├── types/admin.ts                                 # Modify: top_weakness_tag 追加
        ├── lib/api.ts                                     # Modify: postMyReply / getAdminUserDashboard
        ├── stores/admin.ts                                # Modify: fetchUserDashboard
        ├── components/
        │   ├── CommentThread.vue                          # Modify: ツリー + 返信 UI
        │   ├── CommentThreadNode.vue                      # Create: 再帰ノード
        │   └── TaskSubmissionCard.vue                     # Modify: 返信ハンドラ
        ├── layouts/AdminLayout.vue                        # Modify: NotificationCenter 統合
        ├── views/admin/
        │   ├── AdminUsersView.vue                         # Modify: 弱点 column
        │   └── AdminUserDetailView.vue                    # Modify: dashboard section
        └── __tests__/
            ├── CommentThread.spec.ts                      # Modify
            ├── AdminUsersView.spec.ts                     # Create/Modify
            ├── AdminUserDetailView.spec.ts                # Modify
            └── admin.store.spec.ts                        # Modify
```

---

## リスクと対策

| リスク | 影響 | 対策 |
|---|---|---|
| スレッド深さが暴走（無限ネスト） | UI 崩れ、SQL CTE 重い | UX 警告のみ、SQL は適切な LIMIT、UI は 3 階層以降を右寄せ |
| Notification の重複大量送信 | admin の通知箱が荒れる | _thread_admin_authors で重複排除 (DISTINCT) |
| 受講者が他人 submission を巻き込む試み | BOLA 失敗、403/404 | Sprint 4 と同様、404 で統一 |
| bulk クエリの性能 | admin users 一覧が遅くなる | distinct ON + 1 クエリ、テストで query count 監視 |
| 既存 CommentThread の挙動破壊 | 既存表示が崩れる | flat → tree 変換を段階的に、既存テスト維持 + 拡張 |
| 既存 NotificationCenter の admin 動線 | admin が学習者通知も見えてしまう | recipient_user_id = current_user.id で絞られているため影響なし |
| compose_dashboard の nudge スキップ実装 | 既存挙動を壊す | wrapper 関数 `compose_dashboard_for_admin` を別出しして既存と分離 |
| 再帰 CTE のパフォーマンス | スレッドが深いと遅くなる | テストで 5 階層以下を確認、超えたら index ヒント検討（後続） |

---

## 完了条件

- [ ] backend テスト全件パス（既存 268 + 新規）、coverage 80%+
- [ ] frontend テスト全件パス（既存 54 + 新規）
- [ ] frontend build 成功
- [ ] MCP 駆動 E2E ゴールデンパス 1 シナリオが手動で通る + スクリーンショット保存
- [ ] `docker compose up` でローカル動作確認: admin → 受講者 → admin の 3 ターン会話、admin 受講者 dashboard 表示、弱点 column 表示
- [ ] README に Sprint 6 完了マーク
- [ ] 設計書 03/04/05/06 への Sprint 6 セクション追加
- [ ] code-reviewer / security-reviewer の CRITICAL/HIGH 指摘を 0 件、MEDIUM 以下は follow-up doc にチケット化

---

## 次のステップ

この spec に基づき、`superpowers:writing-plans` skill により Sprint 6 実装計画書（`docs/superpowers/plans/2026-06-09-ai-tutor-curriculum-sprint-6.md`）を作成する。
