# Sprint 5 レビュー — MEDIUM / LOW フォローアップ

**作成日:** 2026-06-09
**作成者:** Claude Code（code-reviewer + security-reviewer の Sprint 5 指摘を反映）
**起点コミット:** `c5d49b3 fix(sprint-5): address review HIGH findings`
**前提:** Sprint 5 完了時に CRITICAL 0 / HIGH × 3 は修正済み。本書は **未修正の MEDIUM × 1 + LOW × 6** を後続スプリントへ引き継ぐためのチケット集。

加えて、Sprint 5 で本来予定していた **Playwright E2E 1 本** はインフラ未導入のため実施せず、本書末尾の「インフラ tickets」に記載する。

**ステータス（2026-06-09 更新）:**

| ID | 状態 | コミット |
|---|---|---|
| MED-2 | ✅ 完了 | `e2fbf87 fix(sprint-5): transitional-state guard prevents LLM hallucination (MED-2)` |
| LOW-2 | ✅ 完了 | `9c01c69 fix(sprint-5): invalidate dashboard after successful regrade (LOW-2)` |
| MED-1 | 未着手 | — |
| LOW-1, 3〜6 | 未着手 | — |
| INFRA-1, 2 | 未着手 | — |

**更新履歴:**
- 2026-06-09 初版（code-reviewer / security-reviewer 指摘の MEDIUM × 1 + LOW × 6 + INFRA × 2 を記録）
- 2026-06-09 追記: ローカル動作確認で **MED-2**（コールドスタート脱出直後の LLM ハルシネート）を発見、チケット化
- 2026-06-09 **MED-2 完了**: `feature/sprint-5-followup-med-2` ブランチで transitional state ガード追加、4 件テスト追加、main マージ
- 2026-06-09 **LOW-2 完了**: `feature/sprint-5-followup-low-2` ブランチで regrade 成功時の `dashboard.invalidate()` 追加、2 件テスト追加（graded で invalidate / failed で no-op）、main マージ

---

## 取り扱い方針

Sprint 3 / Sprint 4 follow-up doc と同じ運用:
- **MEDIUM**: Sprint 6 着手時に「Sprint 6 計画書」の前提タスクとして取り込む。
- **LOW**: Sprint 7 以降または保守タスクとしてバックログ。
- **インフラ**: 本番化 Sprint で扱う。

各チケット項目: 観点 / 該当ファイル:行 / リスク / 推奨修正 / テスト方針 / 想定コスト (S=半日, M=1〜2日, L=3日以上)。

---

## MEDIUM

### MED-2: コールドスタート脱出直後の空コンテキストで LLM がハルシネート

- **観点:** UX / LLM コスト無駄打ち
- **該当:** `backend/app/services/nudge.py:140-168`（`get_or_generate` の cold-start 判定〜LLM 呼び出し）, `backend/app/services/nudge.py:71-93`（`_build_prompt`）
- **現状:** `submission_count >= MIN_SUBMISSION_THRESHOLD` だが `weakness_tags=[]` AND `recommendation_titles=[]` の中間状態に入る学習者が存在する。具体的には、Phase 1 の 3 タスクをそれぞれ違うタグ（Git/GitHub / 開発環境 / API基礎）で 1 件ずつ提出した直後がこれに該当する：weakness service は `MIN_TAG_SUBMISSIONS=2` でタグを除外し `top_weaknesses=[]`、recommendation service は `top_weakness_tags=[]` で空配列を返す。

  この状態で `_build_prompt` は:
  ```
  <weakness>（まだ十分なデータがありません）</weakness>
  <recommendations>- （該当なし）</recommendations>
  ```
  という実質コンテキストゼロのプロンプトを Haiku に投げ、LLM が curriculum と無関係な「タスク4：基礎文法の動詞活用」のようなテキストをハルシネートする（2026-06-09 ローカル検証で実際に確認）。
- **リスク:** UX の信頼性低下（curriculum に存在しないタスクを推奨）+ 1 ユーザーあたり最大 1 回/日の無駄な Haiku 呼び出し。コスト影響は小さいが、UX 影響は visible で本番想定では複数学習者に同じ現象が出る。
- **推奨修正:** `get_or_generate` の cold-start チェック直後に **transitional state** チェックを追加し、LLM を呼ばずに static テキストを返す:

  ```python
  TRANSITIONAL_BODY = (
      "提出が貯まり始めましたね。"
      "同じタグのタスクを 2 件以上こなすと、あなた専用の分析が始まります。"
      "まずは Phase 1 を進めてみましょう。"
  )

  async def get_or_generate(...):
      if submission_count < MIN_SUBMISSION_THRESHOLD:
          return NudgeResult(body=COLD_START_BODY, ...)
      # MED-2: weakness と recommendations が両方空 = 集計に足るタグ提出が
      # まだない transitional state。LLM はコンテキストなしでハルシネートする
      # ので呼ばずに transitional テキストを返す。
      if not weakness_tags and not (recommendation_titles or []):
          return NudgeResult(
              body=TRANSITIONAL_BODY,
              generated_at=datetime.now(UTC),
              is_fresh=True,
          )
      # ...以降は既存通り
  ```

  `is_fresh=True` で返し、DB には保存しない（cold-start と同じ扱い）。学習者が同タグの 2 件目を提出した瞬間に weakness が出始め、本来の LLM パスに復帰する。
- **テスト方針:** `test_nudge_service.py` に 2 ケース追加:
  1. `submission_count=5` + `weakness_tags=[]` + `recommendation_titles=[]` で TRANSITIONAL_BODY が返り、`claude.complete` が呼ばれず、`user_nudges` 行が作られないこと。
  2. 既存の `test_cache_miss_generates_and_persists` がカバーしている「weakness と recommendations のいずれかが非空」のケースは引き続き LLM 経路に行くこと（回帰防止）。
- **想定コスト:** S（コア 1 ブランチ + テスト 2 件 + コミット 1 本）
- **優先度:** Sprint 6 最初のタスク候補。実装が小さく、UX 影響が直接的。

### MED-1: RAG クエリ長のガード未実装

- **観点:** リソース枯渇 (CWE-400)
- **該当:** `backend/app/services/rag.py:106-108`, `backend/app/services/recommendation.py:51`
- **現状:** `search_curriculum_tasks` の `query` 引数は呼び出し元で構築される文字列。Sprint 5 ではすべて curriculum.py 由来の固定タグから組まれるため実害なし。ただし、将来 curriculum を admin 編集可能にした場合、長大なクエリで fastembed の推論時間を引き延ばし、`asyncio.to_thread` プールを占有できる。
- **推奨修正:** `search_curriculum_tasks` および `search_context` 入口で `query = query[:MAX_EMBED_QUERY_CHARS]` を適用。`MAX_EMBED_QUERY_CHARS = 512` を `app.config` に。
- **テスト方針:** 600 文字超の query を投げ、エラーなく 512 にトランケートされた結果が返ることを確認。
- **想定コスト:** S

---

## LOW

### LOW-1: `ProgressSummaryCard.belowThreshold` が `computed` でなく素の boolean

- **観点:** Vue 反応性の潜在バグ
- **該当:** `frontend/src/components/ProgressSummaryCard.vue:6`
- **現状:** `belowThreshold` は setup 時に 1 回計算されるだけ。HomeView が `v-if="dashboard.data"` で再マウントする現アーキテクチャでは問題なし。ただし将来このカードを別箇所で `data` を mutate しながら使い回すと hint が古い状態を表示する。
- **推奨修正:** `const belowThreshold = computed(() => props.data.submission_count < COLD_START_THRESHOLD)`
- **想定コスト:** S

### LOW-2: `regradeSubmission` で dashboard.invalidate() を呼ばない

- **観点:** UI 一貫性
- **該当:** `frontend/src/stores/curriculum.ts:124`
- **現状:** 再採点でスコアが変動すると弱点タグや平均スコアが動くが、`regradeSubmission` は `dashboard.invalidate()` を呼ばないため、画面遷移を挟むまで古い dashboard を見せる。`submitTask` 側は対応済み。
- **推奨修正:** `regradeSubmission` の `attempt.status === 'graded'` 分岐内で `useDashboardStore().invalidate()` を呼ぶ。
- **想定コスト:** S

### LOW-3: `source_ref` の split が `maxsplit` 指定なし

- **観点:** 防御的コーディング
- **該当:** `backend/app/services/rag.py:129`
- **現状:** `r.source_ref.split(":")` は固定 4 セグメントを期待しているが、将来タスクタイトル等にコロンが入った形式が混入したら静かにドロップされる（現状の curriculum titles には `:` なしのため実害なし）。
- **推奨修正:** `parts = r.source_ref.split(":")` の後 `if len(parts) != 4 or parts[0] != "phase": continue` で長さチェック。
- **想定コスト:** S

### LOW-4: `_build_signature` で weakness_tags を二重 cap

- **観点:** コード可読性
- **該当:** `backend/app/services/nudge.py:58`
- **現状:** `compute_weakness` が `averages[:3]` を返し、`_build_signature` でも `weakness_tags[:3]` を切る。実害ゼロだが、読者に「ここでも 3 件超を受ける可能性がある」誤読を招く。
- **推奨修正:** コメントで「コール側で top 3 に絞られている前提。冗長カットは defensive copy」と明示する、または slice を削除。
- **想定コスト:** S

### LOW-5: `ix_user_nudges_generated_at` インデックスが未使用

- **観点:** データ最小化 (CWE-200)
- **該当:** `backend/app/models/user_nudge.py:22`, migration line 34
- **現状:** 現状クエリで使われていない。`pg_indexes` 読取権限のあるアナリティクス DB ユーザが学習者のアクティビティ時間を統計から推測できる潜在リスク。
- **推奨修正:** インデックスを削除するか、利用予定のクエリパターンをコメントで残す。
- **想定コスト:** S

### LOW-6: nudge の prompt injection 構造的ギャップ

- **観点:** Prompt injection (CWE-94) の将来リスク
- **該当:** `backend/app/services/nudge.py:64-91`
- **現状:** `_build_prompt` は recommendation `title` を XML 文字列連結している。現在 title は curriculum.py の静的データのため実害なし。将来 admin が title を編集可能になると `</recommendations><system>Ignore previous</system>` のような payload で LLM 挙動を破壊できる。
- **推奨修正:** title を JSON エンコードしてプロンプトに埋め込む、または許可文字リストで sanitize。今は `_build_prompt` のすぐ上に「curriculum 編集可能化したらここを再評価」のコメントを残す。
- **想定コスト:** M（curriculum 編集機能着手時に同梱）

---

## インフラ tickets

### INFRA-1: Playwright E2E の本セットアップ

- **観点:** End-to-end 自動回帰
- **現状:** Sprint 4 までは MCP 駆動の手動 screenshot で代用してきた。Sprint 5 計画書では Playwright E2E 1 本を予定していたが、`frontend/package.json` に Playwright がまだ無いため見送り。
- **推奨セットアップ:**
  - `npm i -D @playwright/test`
  - `npx playwright install --with-deps chromium`
  - `playwright.config.ts` を `frontend/` に追加
  - `frontend/e2e/` ディレクトリ + dashboard ゴールデンパステスト 1 本（新規登録 → 3 件提出 → ダッシュボード描画 → リロード後 cache hit）
- **想定コスト:** M

### INFRA-2: Sprint 5 のローカル動作確認（手動 MCP）

- **観点:** Sprint 5 完了条件
- **現状:** dashboard 機能のローカルでの一気通貫確認（新規ユーザー → 3 件提出 → 弱点表示 → AI 一言）は本セッションでは未実施。
- **推奨アクション:** 次セッション開始時にローカル `docker compose up` で動作確認を実施。Sprint 4 と同様に `e2e-sprint5-*.png` スクリーンショットを残す。
- **想定コスト:** S

---

## Sprint 6 取り込み時の優先順位（推奨）

1. ~~**MED-2**（コールドスタート脱出直後 transitional state の static 文）— UX 影響が直接 visible、ローカル検証で実害確認済み、実装 S~~ → `e2fbf87` で完了
2. ~~**LOW-2**（regrade invalidate）— UX 一貫性、submit 側と同じ修正で済む~~ → `9c01c69` で完了
3. **LOW-1**（computed 化）— Vue 反応性のベストプラクティス
4. **MED-1**（RAG クエリ長ガード）— curriculum 編集機能と同時に必要になる前提
5. **LOW-3, LOW-4, LOW-5** — 保守として S サイズ
6. **LOW-6**（prompt injection 防御）— curriculum 編集機能着手と同タイミング
7. **INFRA-1**（Playwright）— Sprint 6 か Sprint 7 で本セット
8. **INFRA-2**（手動確認）— 次セッション開始直後に実施
