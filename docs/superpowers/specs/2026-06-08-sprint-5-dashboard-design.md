# Sprint 5 設計書 — 受講者ダッシュボード（弱点分析 + レコメンド + AI 一言）

**作成日:** 2026-06-08
**作成者:** Claude Code（superpowers:brainstorming セッション）
**起点コミット:** `bbee660 docs(sprint-4): mark MED-1..5 security follow-ups as completed`（main、Sprint 4 + follow-up MED 完了状態）
**位置づけ:** Sprint 4 計画書の「後続 Sprint」として挙げられていた「学習プラン / 弱点分析 / レコメンド」を Sprint 5 として具体化したもの。`docs/superpowers/plans/2026-06-08-ai-tutor-curriculum-sprint-5.md`（後続で writing-plans により作成）の上位仕様。

---

## 目的とサクセスクライテリア

**目的:** ログイン直後のホーム画面を、受講者本人の学習データに基づいた**個別最適化ダッシュボード**に進化させる。Sprint 1〜4 で蓄積されている `submissions / grading_attempts` を初めて受講者本人にフィードバックし、「次に何をすればよいか」を AI が示す。

**サクセスクライテリア:**

1. ログイン直後のホーム（`/`）に、その受講者の「もう一押しの分野（弱点）」「次にやるべきタスク 3 件」「AI からの一言」「進捗サマリ」が表示される。
2. 提出 3 件以上の受講者には弱点上位 3 タグが**説明可能な根拠**（平均スコア、提出数）と共に提示される。
3. レコメンドは既存 RAG（Sprint 2 で導入）を再利用して**未提出タスク**を 3 件まで提示し、各件がどの弱点タグに対応しているか明示される。
4. AI 一言は **Lazy 生成 + 24h キャッシュ**で、100 active users / 日でも LLM コストが $0.01/日 程度に収まる。
5. 提出が 3 件未満の受講者は「データ不足」状態として明示され、コールドスタート用の固定アドバイスが表示される。
6. Sprint 1〜4 と同水準（backend 80%+ カバレッジ、TDD 厳格、Playwright E2E 1 本）のテストが揃う。

---

## スコープ境界

### 含む（Sprint 5）

- `app/data/curriculum.py`（or 同等）の Task 構造に `skill_tags: list[str]` を追加し、**12 タスクすべてに 1〜2 タグを手動付与**。
- 新規テーブル `user_nudges`（PK=user_id、AI 一言の 24h キャッシュ）。Alembic マイグレーション 1 リビジョン。
- backend サービス 5 つ:
  - `services/weakness.py`
  - `services/recommendation.py`
  - `services/nudge.py`
  - `services/progress_summary.py`
  - `services/dashboard.py`（orchestrator、4 サービスを呼んで集約）
- API: `GET /api/me/dashboard` 1 本のみ。
- frontend:
  - 既存 `HomeView.vue` をダッシュボード化（フェーズ一覧 UI は下部に保持）
  - `stores/dashboard.ts`（新規）
  - `components/NudgeBanner.vue`（または `AiNudgeCard.vue`）、`ProgressSummaryCard.vue`、`WeaknessCard.vue`、`RecommendationsCard.vue`
- テスト一式: backend 9 ファイル前後、frontend 5 ファイル前後、Playwright E2E 1 本
- README 更新（Sprint 5 完了マーク）

### 含まない（後続スプリント）

| 候補 | 送り先 | 理由 |
|---|---|---|
| 採点の非同期化（バックグラウンドジョブ） | Sprint 6 候補 | インフラ依存（worker / queue）が重く、独立した Sprint 軸 |
| コメント返信（受講者 → 講師、スレッド化） | Sprint 6 候補 | Sprint 4 admin の拡張、Sprint 5 は受講者本人体験に集中 |
| broadcast 通知 | 別途 | 監査・誤送リスク設計が独立 |
| リアルタイム通知（SSE/WS） | Sprint 7+ | インフラ刷新タイミング |
| Sprint 4 follow-up LOW-2/3/4 | Sprint 6 候補 | 独立 S サイズ。同梱せず本スプリントは受講者体験に集中 |
| Sprint 4 follow-up LOW-1（Cookie 化） | 認証刷新 Sprint | 影響範囲大 |
| audit log テーブル | 本番化 Sprint | 監査要件未定義 |
| AI 一言の履歴保持 | 後続 | YAGNI、1 行で十分 |
| nudge のリアルタイム再生成（提出時 push） | 後続 | Lazy + 24h で UX 十分 |
| 講師向け admin ダッシュボード強化 | 別スプリント | Sprint 4 admin の拡張、独立 |

---

## 主要意思決定（Sprint 5 計画時点）

| # | 判断項目 | 選択 | 理由 |
|---|---|---|---|
| 1 | スコープの軸 | 受講者体験（弱点 + レコメンド + ダッシュボード + AI 一言） | UX のレバレッジが最大 |
| 2 | アーキテクチャ | 集約 API 1 本（`GET /api/me/dashboard`） | 状態管理シンプル、ドメイン整合性高い |
| 3 | 弱点の軸 | curriculum タスクへの手動 skill_tags（5〜10 種） | 12 タスクに対して粒度が適切、追加コスト低 |
| 4 | 弱点の定義 | submission ごとの最新 graded attempt の score をタグで平均、低い上位 3 | データ集計のみ、ユーザーに説明可能 |
| 5 | コールドスタート閾値 | `MIN_SUBMISSION_THRESHOLD = 3` | 1〜2 件では信頼性のある弱点判定不能 |
| 6 | タグ別最低提出数 | `MIN_TAG_SUBMISSIONS = 2` | 1 件提出で弱点認定はノイズ |
| 7 | レコメンド | 弱点 1 位タグをクエリに、curriculum_task に絞った新規 RAG 関数 `search_curriculum_tasks` で類似タスク → 未提出フィルタ → 上位 3 | 既存 Embedding テーブルと埋め込みパイプラインは再利用、検索面だけ新規追加 |
| 8 | AI 一言 | Lazy 生成 + 24h cache + signature による入力変化検知 | コスト最小、運用シンプル、鮮度確保 |
| 9 | nudge ストレージ | `user_nudges` テーブル、PK=user_id（履歴なし、最新 1 行のみ） | YAGNI、24h cache に履歴は不要 |
| 10 | nudge LLM モデル | `claude-haiku-4-5`（80 文字制約、temperature=0.5） | コスト・速度・揺れの抑制 |
| 11 | nudge コンカレンシー | 同 user 同時 fetch で `SELECT FOR UPDATE` 行ロック、後発は再 SELECT | 二重生成によるコストブレ防止 |
| 12 | nudge コールドスタート | 提出 3 件未満では LLM を呼ばず static 固定文 | API キー消費を 0 にする、UX 連続性 |
| 13 | UI 文言 | 「弱点」ではなく「もう一押しの分野」 | 受講者モチベ低下回避 |
| 14 | 動線 | 既存 HomeView をダッシュボード化、フェーズ一覧 UI も下部に保持 | 「タスクをカリキュラム順に確認したい」要求も維持 |
| 15 | API 形状 | dashboard レスポンスは 4 セクション固定の単一 envelope。サブ系統別 API は作らない | フロント分岐 1 箇所、ポーリング不要 |
| 16 | エラー時挙動 | nudge 生成失敗 → stale を返す（cache 上書きしない）。RAG 失敗 → recommendations=[]。1 つの失敗で全体は 500 にしない | 部分失敗でもダッシュボードは見える |
| 17 | Sprint 4 LOW 同梱 | 同梱しない | スコープを「受講者体験」に純化、レビュー可能単位を保つ |
| 18 | テスト戦略 | Sprint 1〜4 と同水準（TDD 厳格 + Playwright E2E 1 本） | 既存基準維持 |

---

## アーキテクチャ全体像

```
┌────────────────────────────────────────────────────────────────┐
│  Frontend (HomeView.vue → ダッシュボード化)                    │
│  ├─ NudgeBanner.vue           (AI 一言 + generated_at)         │
│  ├─ DashboardGrid                                              │
│  │    ├─ ProgressSummaryCard  (完了 N / 平均スコア)            │
│  │    ├─ WeaknessCard         (タグ別平均 worst-3)             │
│  │    └─ RecommendationsCard  (未提出 × 弱点タグ × RAG top-3)  │
│  └─ PhaseListSection          (既存フェーズ一覧、下部に保持)   │
└────────────────────────────────────────────────────────────────┘
           ▲
           │  GET /api/me/dashboard (1 fetch)
           ▼
┌────────────────────────────────────────────────────────────────┐
│  Backend                                                       │
│  app/api/me_dashboard.py                                       │
│    └─ services/dashboard.py    (orchestrator)                  │
│         ├─ services/weakness.py        (タグ別平均)            │
│         ├─ services/recommendation.py  (未提出 × 弱点 RAG)     │
│         ├─ services/nudge.py           (Lazy + 24h cache)      │
│         └─ services/progress_summary.py                        │
│              ↓                                                 │
│  models                                                        │
│    ├─ data/curriculum.py    Modify: Task に skill_tags         │
│    └─ user_nudge.py         Create: PK=user_id, 24h TTL        │
└────────────────────────────────────────────────────────────────┘
```

---

## データモデル

### `app/data/curriculum.py`（既存ファイルの拡張）

**現状（Sprint 0〜4）:** `CURRICULUM: Mapping[int, PhaseData]` で各 phase に `tasks: list[str]`（タスク説明文の単純リスト）を保持。`task_no = リスト index + 1` という暗黙の対応関係で `submissions.task_no` と紐づく。

**変更内容:**

1. `tasks: list[str]` を `list[TaskItem]` に置き換える。`TaskItem` は新規 TypedDict:

   ```python
   class TaskItem(TypedDict):
       title: str             # 既存の文字列をそのまま入れる
       skill_tags: list[str]  # Sprint 5 で追加、必須
   ```

2. PhaseData は `tasks: list[TaskItem]` に変更。

3. lookup ヘルパー `get_task_skill_tags(phase_no: int, task_no: int) -> list[str]` を追加（1-indexed の task_no を想定）。範囲外は KeyError。

4. 既存 API レスポンス（`GET /api/curriculum`）の後方互換性を維持するため、`PhaseSummary.tasks: list[str]` は変えず、サーバ側で `[item["title"] for item in phase["tasks"]]` に射影する。**フロント側の互換性は破壊しない**。

5. タグ語彙は短い日本語名（例: `データ構造` / `アルゴリズム` / `型システム` / `関数型` / `テスト` / `デバッグ` / `設計` / `IO` / `並行性` / `セキュリティ` の 10 種前後）。Task 0 で語彙を確定し、12 タスク全件に 1〜2 タグずつ付与。

```python
# 変更後イメージ
CURRICULUM: Mapping[int, PhaseData] = MappingProxyType({
    1: {
        "title": "開発環境の近代化",
        ...
        "tasks": [
            {"title": "Gitでブランチを切り、Pythonスクリプトを...", "skill_tags": ["IO", "設計"]},
            {"title": "...", "skill_tags": ["デバッグ"]},
            # ... 各 phase 7 タスク前後
        ],
    },
    # ...
})
```

**既存テストへの影響:**

- `test_curriculum_data.py` の `test_each_phase_has_at_least_three_tasks` は要素数のみ検査するため pass。
- `test_curriculum_data.py` の `test_system_prompt_mentions_phase_label` 等は文字列検査のため pass。
- 既存テストで `tasks[i]` を str として直接扱っている箇所があれば、`tasks[i]["title"]` に書き換える（Task 0 で grep して洗い出す）。
- API レスポンス互換は維持されるためフロントテストは無影響。

### `app/models/user_nudge.py`（新規）

```python
class UserNudge(Base):
    __tablename__ = "user_nudges"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    input_signature: Mapped[str] = mapped_column(String(16), nullable=False)
```

- **PK = user_id**: 1 ユーザー 1 行（履歴は持たない、YAGNI）。
- **CASCADE on user delete**: ユーザー削除時に nudge も消える。
- `input_signature` は弱点タグ + 推奨 1 位タスク id + 提出数 から SHA-256 を取った先頭 16 文字。
  24h 経過していなくても入力が変化したら再生成するための鍵。
- Alembic 1 リビジョン（`20260608_<rev>_sprint5_user_nudges.py`）で追加。

---

## API 仕様

### `GET /api/me/dashboard`

**Auth:** Bearer JWT（既存 `get_current_user` dependency）。
**Rate limit:** なし（read-only、結果は 1 オブジェクト、ポーリングしない）。
**所有権:** 自分のダッシュボードのみ取得可能（user_id を JWT から取る、URL に id を取らない）。

**Response 200:**

```jsonc
{
  "progress_summary": {
    "completed_tasks": 7,
    "total_tasks": 12,
    "average_score": 76.4,        // submission_count < 3 のとき null
    "submission_count": 9
  },
  "weakness": {
    "has_enough_data": true,      // submission_count >= 3
    "top_weaknesses": [           // 最大 3 件、低スコア順、空配列もあり
      { "tag": "データ構造", "average_score": 58.0, "submission_count": 3 },
      { "tag": "アルゴリズム", "average_score": 64.5, "submission_count": 2 },
      { "tag": "型システム", "average_score": 71.0, "submission_count": 4 }
    ]
  },
  "recommendations": {
    "items": [                    // 最大 3 件、空配列もあり
      {
        "phase": 2,
        "task_no": 3,
        "title": "二分探索木の実装",
        "skill_tags": ["データ構造", "アルゴリズム"],
        "match_tag": "データ構造", // どの弱点タグ由来か（null もあり）
        "rag_score": 0.78
      }
    ]
  },
  "nudge": {
    "body": "データ構造の課題で伸び悩んでいるようですね。まずは Phase 2 の二分探索木に挑戦してみると、フェーズ全体の見通しが立ちます。",
    "generated_at": "2026-06-08T07:00:00Z",
    "is_fresh": true              // 24h 以内なら true、stale なら false
  }
}
```

**エラー応答**

- 401: 未認証
- 500: orchestrator 自体の予期せぬ失敗のみ。サブサービス（nudge LLM, RAG）の失敗はサイレントに握りつぶし、対応セクションを fallback で返す。

---

## 弱点 (weakness) アルゴリズム

```python
# services/weakness.py
MIN_SUBMISSION_THRESHOLD = 3
MIN_TAG_SUBMISSIONS = 2

async def compute_weakness(db, user_id) -> WeaknessResult:
    # 1. submission ごとに最新 graded attempt の score を取得
    rows = await _latest_graded_scores(db, user_id)
    if len(rows) < MIN_SUBMISSION_THRESHOLD:
        return WeaknessResult(has_enough_data=False, top_weaknesses=[])

    # 2. submission.phase + submission.task_no で curriculum lookup
    tag_scores: dict[str, list[float]] = defaultdict(list)
    for sub_id, score, phase, task_no in rows:
        for tag in get_task_skill_tags(phase, task_no):
            tag_scores[tag].append(score)

    # 3. 提出 2 件未満のタグは除外
    averages = [
        TagAverage(tag=t, average_score=mean(scores),
                   submission_count=len(scores))
        for t, scores in tag_scores.items()
        if len(scores) >= MIN_TAG_SUBMISSIONS
    ]

    # 4. 低い順に 3 件
    averages.sort(key=lambda a: a.average_score)
    return WeaknessResult(has_enough_data=True, top_weaknesses=averages[:3])
```

**SQL（`_latest_graded_scores`）**

```sql
SELECT DISTINCT ON (s.id)
    s.id, ga.score, s.phase, s.task_no
FROM submissions s
JOIN grading_attempts ga ON ga.submission_id = s.id
WHERE s.user_id = :user_id AND ga.status = 'graded'
ORDER BY s.id, ga.created_at DESC;
```

**同点 average_score のソート安定性:** PostgreSQL の結果ソートに依存しない（Python `list.sort` は安定）。同点時の表示順は「先に挿入されたタグが先」。テストで検証。

---

## レコメンド (recommendation) アルゴリズム

### 既存 RAG の構造と Sprint 5 での扱い

Sprint 2 で導入された `app/services/rag.py` の `search_context(...)` は、**会話中に文脈を注入する用途**（user_id 必須、phase 必須）の関数で、戻り値は `RagHit(source_type, content, score)` のみ。phase / task_no を直接持たない。

`Embedding` テーブルでは curriculum_task の埋め込みが以下の形式で seed されている（`scripts/seed_embeddings.py`）:

- `source_type = "curriculum_task"`
- `source_ref = "phase:{phase_no}:task:{i}"` （`i` は `tasks` リストの 0-indexed 位置 = `task_no - 1` に対応）
- `phase = phase_no`
- `content` = タスクの本文文字列

Sprint 5 では:

1. **`scripts/seed_embeddings.py` を改修**: `tasks[i]` が文字列から `TaskItem` 辞書に変わるため、`task["title"]` から content を取る形に変更。
2. **`make seed-embeddings` を再実行する必要性を README に明記**（既存 row は `source_ref` 同一で upsert される）。
3. **新規 RAG 関数を追加**: `search_curriculum_tasks(db, client, query, limit)` を `services/rag.py` に新設。`source_type == "curriculum_task"` でフィルタし、`source_ref` を parse して phase / task_no を復元。戻り値は新規 `CurriculumTaskHit(phase: int, task_no: int, score: float)` のみ（content は使わないため返さない）。

```python
# services/rag.py に追加
@dataclass(frozen=True)
class CurriculumTaskHit:
    phase: int
    task_no: int  # 1-indexed
    score: float


async def search_curriculum_tasks(
    db: AsyncSession, client: EmbeddingClient,
    *, query: str, limit: int = 8,
) -> list[CurriculumTaskHit]:
    if not query.strip():
        return []
    qvec = (await client.embed([query]))[0]
    stmt = (
        select(
            Embedding.source_ref,
            Embedding.phase,
            Embedding.embedding.cosine_distance(qvec).label("distance"),
        )
        .where(Embedding.source_type == "curriculum_task")
        .order_by("distance")
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    out: list[CurriculumTaskHit] = []
    for r in rows:
        # source_ref = "phase:{p}:task:{i}" を parse
        try:
            _, p_str, _, i_str = r.source_ref.split(":")
            phase = int(p_str); task_no = int(i_str) + 1
        except (ValueError, AttributeError):
            continue
        out.append(CurriculumTaskHit(phase=phase, task_no=task_no,
                                     score=1.0 - float(r.distance)))
    return out
```

### Recommendation サービス本体

```python
# services/recommendation.py
async def compute_recommendations(
    db, client, user_id, top_weakness_tags: list[str],
) -> list[Recommendation]:
    if not top_weakness_tags:
        return []

    # 1. 未提出タスク（受講者の提出済み phase × task_no を除外）
    submitted = await _user_submitted_phase_task_pairs(db, user_id)
    unsubmitted_keys: set[tuple[int, int]] = {
        (p, n) for p, n in iter_all_phase_task_pairs() if (p, n) not in submitted
    }
    if not unsubmitted_keys:
        return []

    # 2. 弱点 1 位タグでクエリ（2 位以下は使わない、シンプルさ優先）
    primary = top_weakness_tags[0]
    hits = await search_curriculum_tasks(
        db, client, query=f"{primary} を扱うタスク", limit=8,
    )

    # 3. 未提出フィルタ + 重複除去で上位 3 件
    seen: set[tuple[int, int]] = set()
    out: list[Recommendation] = []
    for hit in hits:
        key = (hit.phase, hit.task_no)
        if key not in unsubmitted_keys or key in seen:
            continue
        seen.add(key)
        tags = get_task_skill_tags(hit.phase, hit.task_no)
        title = get_task_title(hit.phase, hit.task_no)
        out.append(Recommendation(
            phase=hit.phase, task_no=hit.task_no, title=title,
            skill_tags=tags,
            match_tag=primary if primary in tags else None,
            rag_score=hit.score,
        ))
        if len(out) == 3:
            break

    return out
```

`get_task_title(phase, task_no)` も `curriculum.py` に追加（既存の `tasks[i]` 直接アクセスを禁じ、ヘルパー経由で必ず TaskItem 構造を意識させる）。

- RAG クエリは「弱点 1 位タグ」のみで生成。
- `match_tag` が null になる recommendation も許容（別角度の推奨）。
- 結果が 3 未満になることもある（未提出が少ない／RAG ヒットが少ない場合）。仕様。

---

## AI 一言 (nudge) 詳細

### Lazy 生成のフロー

```
GET /api/me/dashboard
  ↓
services/nudge.get_or_generate(db, user_id, weakness, recommendations, submission_count)
  ↓
1. user_nudges を PK で取得（FOR UPDATE で行ロック）
2. キャッシュヒット判定:
     row != null  AND
     (now - generated_at) < 24h  AND
     row.input_signature == expected_signature
   ↓ HIT → row.body, generated_at, is_fresh=True
   ↓ MISS → 3 へ
3. submission_count < 3 → static fallback テキストを返す（DB には保存しない）
4. Claude API 呼び出し（同期、claude-haiku-4-5、max_tokens=200, temperature=0.5）
5. 成功 → upsert（PK=user_id）、is_fresh=True
6. 失敗:
     既存 row あり → row.body, row.generated_at, is_fresh=False（stale-while-error）
     既存 row なし → static fallback テキスト（DB には保存しない）
```

### プロンプト

**system:**
```
あなたは個別最適化されたアドバイザーです。
受講者の弱点と進捗を踏まえて、次の一歩を 80 文字以内・1 文で示してください。
励ましの言葉は不要。具体的なタスク名や数値を含めてください。
```

**user:**
```
<progress>完了: 7/12 タスク、平均スコア: 76.4</progress>
<weakness>
1. データ構造 (平均 58 / 3 件)
2. アルゴリズム (平均 64 / 2 件)
</weakness>
<recommendations>
- Phase 2 タスク 3「二分探索木の実装」(未着手)
- Phase 3 タスク 1「クイックソートの最悪計算量」(未着手)
</recommendations>
```

**Sprint 4 で導入済みの XML 区切り（MED-1 対応）と同じ形式で受講者データを構造化**。Prompt injection への一貫した防御。

### input_signature

```python
def _signature(weakness_tags: list[str], top_recommendation_key: str | None,
               submission_count: int) -> str:
    payload = (
        f"{','.join(weakness_tags[:3])}|{top_recommendation_key or ''}"
        f"|{submission_count}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
```

24h 以内でも `submission_count` が増えるか弱点上位 3 タグが変化すれば signature が変わり再生成される。

### コールドスタート専用テキスト（DB 非保存）

```
「まずは Phase 1 のタスクから始めてみましょう。3 件提出するとあなた専用のアドバイスが出るようになります。」
```

- LLM を呼ばない、`generated_at = now()`、`is_fresh = True`
- DB には書かない（コールドスタート脱出時に古い row が残らないように）

### コスト試算と設定

- 1 ユーザー = 1 日最大 1 回 = 約 60 input tokens + 80 output tokens
- claude-haiku-4-5 で約 $0.0001/呼び出し
- 100 active users / 日 → $0.01 / 日

### 必要な設定追加 (`app/config.py`)

```python
# Nudge (Sprint 5) — 採点と別モデルにできるよう独立した設定
nudge_model: str = "claude-haiku-4-5"
nudge_cache_ttl_hours: int = 24
nudge_max_output_tokens: int = 200
nudge_temperature: float = 0.5
```

`anthropic_model`（既存、grading で使う Sonnet 4.5）には触らない。`.env.example` にも対応する 4 行を追加。

---

## Frontend 設計

### 既存 HomeView の改造

```vue
<template>
  <div class="home">
    <NudgeBanner v-if="dash.data?.nudge" :nudge="dash.data.nudge" />
    <DashboardGrid v-if="dash.data">
      <ProgressSummaryCard :data="dash.data.progress_summary" />
      <WeaknessCard :data="dash.data.weakness" />
      <RecommendationsCard :items="dash.data.recommendations.items"
                           @select="onRecommendationClick" />
    </DashboardGrid>
    <PhaseListSection :phases="curriculum.phases" />
  </div>
</template>
```

**重要:** 既存のフェーズ一覧 UI は **下部に保持**。ダッシュボード（上）+ フェーズ一覧（下）の縦並びにする。

### 新規 store

```typescript
// stores/dashboard.ts
export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    data: null as DashboardResponse | null,
    loading: false,
    error: null as string | null,
  }),
  actions: {
    async fetch() {
      this.loading = true; this.error = null;
      try { this.data = await api.getMyDashboard(); }
      catch (e) { this.error = '読み込みに失敗しました'; }
      finally { this.loading = false; }
    },
    invalidate() { this.data = null; },
  },
});
```

`invalidate()` は提出または再採点完了時に呼ぶ。`TaskSubmissionCard` の onSubmitted callback に追加。

### コールドスタート分岐

各カード内で表示文言を切り替える。フロント側のロジックは「`has_enough_data` / `items.length === 0` / `submission_count < 3`」を見るだけ。

### a11y / UX

- カードは `<section role="region" aria-labelledby="...">`
- UI 文言は「もう一押しの分野」「次のおすすめ」「あなたの進捗」「今日のアドバイス」のように受講者の自己評価を下げない表現
- 内部 API のキー名は `weakness`（コードの一貫性のため）、ただし `<h2>` のテキストは中立的に

---

## テスト戦略

### Backend テスト（新規 9 ファイル前後）

| ファイル | 観点 |
|---|---|
| `test_models_sprint5.py` | UserNudge round-trip / PK制約 / CASCADE on user delete |
| `test_curriculum_skill_tags.py` | 12 タスク全部に skill_tags あり、`get_task(phase, task_no).skill_tags` が動く |
| `test_weakness_service.py` | コールドスタート / 通常パス上位 3 / MIN_TAG_SUBMISSIONS フィルタ / 同点時の安定ソート |
| `test_recommendation_service.py` | 未提出フィルタ / RAG モック並び順 / 弱点空時 = [] / 未提出 < 3 のとき結果 < 3 |
| `test_nudge_service.py` | cache miss → 生成 / 24h hit / signature 変化で再生成 / LLM 例外 → stale / コールドスタート → static |
| `test_progress_summary_service.py` | average_score 集計 / submission_count < 3 で null |
| `test_dashboard_service.py` | orchestrator: 4 サブを mock して response shape / nudge 例外時に全体が落ちない |
| `test_me_dashboard_api.py` | 認証 401 / コールドスタートレスポンス / 通常レスポンス / 他ユーザーのは取れない |
| `conftest.py` 拡張 | `seed_graded_submission` helper |

### Frontend テスト（新規 5 ファイル前後）

| ファイル | 観点 |
|---|---|
| `dashboard.store.spec.ts` | fetch 成功/失敗 / invalidate |
| `WeaknessCard.spec.ts` | コールドスタート文言 / 上位 3 表示 / 空配列 |
| `RecommendationsCard.spec.ts` | items 表示 / クリックで navTo emit / 空時 CTA |
| `NudgeBanner.spec.ts` | body 表示 / generated_at / is_fresh=false の見た目 |
| `HomeView.spec.ts` | ダッシュボード 4 カード + フェーズ一覧の同居 / 提出後 invalidate |

### E2E（Playwright、1 本）

```
シナリオ: 新規受講者がダッシュボードを育てる
1. 新規登録 → ダッシュボードがコールドスタート表示
2. Phase 1 タスク 1〜3 を提出（採点モック） → ダッシュボード再フェッチ
3. 4 件目で weakness セクションが現れる
4. nudge が表示される、再ロードしても 24h 以内は同じ内容
5. 別ユーザーでログインしても 1 のユーザーのダッシュボードは見えない（BOLA）
```

### モック戦略

- `nudge_service` 内の Claude 呼び出しは pytest fixture でモック
- `recommendation_service` 内の RAG 呼び出しは関数モック
- E2E でも `ANTHROPIC_*` は test key、固定レスポンス

### カバレッジ

- backend 80%+
- frontend は vitest カバレッジ未強制（既存方針）

---

## ファイル構造（差分のみ）

```
edu/
├── README.md                                                       # Modify: Sprint 5 完了マーク + seed-embeddings 再実行注記
├── .env.example                                                    # Modify: nudge_* 設定 4 行追加
├── backend/
│   ├── app/
│   │   ├── data/
│   │   │   └── curriculum.py                                       # Modify: tasks を list[TaskItem] へ、skill_tags 付与、get_task_skill_tags / get_task_title / iter_all_phase_task_pairs 追加
│   │   ├── schemas/
│   │   │   ├── curriculum.py                                       # Modify: API レスポンス互換のため title 射影
│   │   │   └── dashboard.py                                        # Create: DashboardResponse 系
│   │   ├── models/
│   │   │   ├── __init__.py                                         # Modify: import 追加
│   │   │   └── user_nudge.py                                       # Create
│   │   ├── services/
│   │   │   ├── rag.py                                              # Modify: search_curriculum_tasks + CurriculumTaskHit 追加
│   │   │   ├── weakness.py                                         # Create
│   │   │   ├── recommendation.py                                   # Create
│   │   │   ├── nudge.py                                            # Create
│   │   │   ├── progress_summary.py                                 # Create
│   │   │   └── dashboard.py                                        # Create: orchestrator
│   │   ├── api/
│   │   │   ├── curriculum.py                                       # Modify: 新 TaskItem 構造から title だけ射影して既存レスポンス互換
│   │   │   └── me_dashboard.py                                     # Create
│   │   ├── config.py                                               # Modify: nudge_model / nudge_cache_ttl_hours / nudge_max_output_tokens / nudge_temperature
│   │   └── main.py                                                 # Modify: dashboard router 追加
│   ├── alembic/versions/
│   │   └── 20260608_<rev>_sprint5_user_nudges.py                   # Create
│   ├── scripts/
│   │   └── seed_embeddings.py                                      # Modify: task が TaskItem 辞書になったので task["title"] を渡す
│   └── tests/
│       ├── test_models_sprint5.py                                  # Create
│       ├── test_curriculum_skill_tags.py                           # Create
│       ├── test_weakness_service.py                                # Create
│       ├── test_recommendation_service.py                          # Create
│       ├── test_nudge_service.py                                   # Create
│       ├── test_progress_summary_service.py                        # Create
│       ├── test_dashboard_service.py                               # Create
│       ├── test_me_dashboard_api.py                                # Create
│       └── conftest.py                                             # Modify: seed_graded_submission helper
└── frontend/
    └── src/
        ├── stores/
        │   └── dashboard.ts                                        # Create
        ├── lib/api.ts                                              # Modify: getMyDashboard
        ├── types/
        │   └── dashboard.ts                                        # Create
        ├── views/
        │   └── HomeView.vue                                        # Modify: ダッシュボード化
        ├── components/
        │   ├── NudgeBanner.vue                                     # Create
        │   ├── ProgressSummaryCard.vue                             # Create
        │   ├── WeaknessCard.vue                                    # Create
        │   └── RecommendationsCard.vue                             # Create
        └── __tests__/
            ├── dashboard.store.spec.ts                             # Create
            ├── WeaknessCard.spec.ts                                # Create
            ├── RecommendationsCard.spec.ts                         # Create
            ├── NudgeBanner.spec.ts                                 # Create
            └── HomeView.spec.ts                                    # Create
```

---

## リスクと対策

| リスク | 影響 | 対策 |
|---|---|---|
| skill_tags の語彙設計が浅い | 弱点・レコメンドの説得力低下 | Task 0 で 5〜10 タグを定め、PR レビューで語彙妥当性を検証 |
| RAG が弱点タグと無関係なタスクを返す | recommendations の質低下 | `match_tag` を nullable で返し、null 多発なら Sprint 6 でアルゴリズム調整 |
| LLM の出力が 80 文字を大幅に超える | UI 崩れ | max_tokens=200 + フロントでの文字数制限スタイル + サーバ側で truncate（500 文字 cap）|
| LLM 出力に prompt injection 紛れ込み | UI 経由の XSS | nudge.body は HTML 非解釈、`{{ nudge.body }}` でテキスト出力のみ |
| 同 user の同時 dashboard fetch で nudge 二重生成 | LLM コスト 2 倍 | `SELECT FOR UPDATE` 行ロック、後発は再 SELECT |
| 既存テストへの影響 | Sprint 1〜4 のテスト 212 件が落ちる | curriculum 拡張は既存 Task 構造に追加するだけ。既存テストが skill_tags 必須前提を持たない限り影響なし。Task 0 で全件確認 |
| HomeView 改造で既存 E2E が壊れる | 既存 Playwright スクリーンショット差分 | Sprint 4 までの E2E ファイルは保持、Sprint 5 では新規 E2E のみ追加 |

---

## 完了条件

- [ ] backend テスト全件パス（既存 212 + 新規）、coverage 80%+
- [ ] frontend テスト全件パス（既存 34 + 新規）
- [ ] frontend build 成功
- [ ] Playwright E2E（Sprint 5 新規 1 本）パス
- [ ] `make seed-embeddings` を再実行し、curriculum_task 行が新しい title 文字列で再投入されていることを SQL で確認
- [ ] `docker compose up` でローカル動作確認: 新規ユーザー → 3 件提出 → 弱点表示 → nudge 表示
- [ ] README に Sprint 5 完了マーク、`make seed-embeddings` の再実行手順を「マイグレーション」セクションに追記
- [ ] code-reviewer / security-reviewer の指摘 CRITICAL/HIGH を 0 件にし、MEDIUM 以下は follow-up doc にチケット化

---

## 次のステップ

この spec に基づき、`superpowers:writing-plans` skill により Sprint 5 実装計画書（`docs/superpowers/plans/2026-06-08-ai-tutor-curriculum-sprint-5.md`）を作成する。計画書では本 spec の各セクションを Task に分解し、TDD ワークフロー（RED→GREEN→REFACTOR）に沿って Step-by-step に展開する。
