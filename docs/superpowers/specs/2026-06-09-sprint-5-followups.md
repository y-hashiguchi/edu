# Sprint 5 レビュー — MEDIUM / LOW フォローアップ

**作成日:** 2026-06-09
**作成者:** Claude Code（code-reviewer + security-reviewer の Sprint 5 指摘を反映）
**起点コミット:** `c5d49b3 fix(sprint-5): address review HIGH findings`
**前提:** Sprint 5 完了時に CRITICAL 0 / HIGH × 3 は修正済み。本書は **未修正の MEDIUM × 1 + LOW × 6** を後続スプリントへ引き継ぐためのチケット集。

加えて、Sprint 5 で本来予定していた **Playwright E2E 1 本** はインフラ未導入のため実施せず、本書末尾の「インフラ tickets」に記載する。

---

## 取り扱い方針

Sprint 3 / Sprint 4 follow-up doc と同じ運用:
- **MEDIUM**: Sprint 6 着手時に「Sprint 6 計画書」の前提タスクとして取り込む。
- **LOW**: Sprint 7 以降または保守タスクとしてバックログ。
- **インフラ**: 本番化 Sprint で扱う。

各チケット項目: 観点 / 該当ファイル:行 / リスク / 推奨修正 / テスト方針 / 想定コスト (S=半日, M=1〜2日, L=3日以上)。

---

## MEDIUM

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

1. **MED-1**（RAG クエリ長ガード）— curriculum 編集機能と同時に必要になる前提
2. **LOW-2**（regrade invalidate）— UX 一貫性、submit 側と同じ修正で済む
3. **LOW-1**（computed 化）— Vue 反応性のベストプラクティス
4. **LOW-3, LOW-4, LOW-5** — 保守として S サイズ
5. **LOW-6**（prompt injection 防御）— curriculum 編集機能着手と同タイミング
6. **INFRA-1**（Playwright）— Sprint 6 か Sprint 7 で本セット
7. **INFRA-2**（手動確認）— 次セッション開始直後に実施
