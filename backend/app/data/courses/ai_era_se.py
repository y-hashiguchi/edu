"""ai-era-se course definition (Sprint 7 + follow-up LOW-1).

All four phases from the 12-month syllabus. AI usage rules are injected
into every phase system prompt."""

import uuid

from app.data.courses.types import CourseData, PhaseData, TaskItem


AI_USAGE_RULES = (
    "【AI 活用ルール】\n"
    "1. AIに聞いた内容は必ず自分の言葉で再説明できること（コピペ禁止）\n"
    "2. AIが生成したコードは理解してから使うこと（動けばOKは禁止）\n"
    "3. プロンプトはバージョン管理すること（Gitで管理、改善履歴を残す）\n"
    "4. AIが見逃した問題を自分で探す習慣を付けること\n"
    "5. 「AIに任せた場面」と「自分で判断した場面」を毎週の作業ログに記録すること"
)


_SE_TUTOR_BASE = (
    "あなたは AI 時代の SE 育成を担う AI チューターです。\n"
    "対象は初級エンジニア（プログラミング経験 1 年未満）で、業務プロジェクト"
    "（MFRS / Nichinichi Anshin / IES）を題材に学びます。\n"
    f"\n{AI_USAGE_RULES}\n"
)


_PHASE_1_EVAL = (
    "\n【Phase 1 評価基準】\n"
    "- Gitの基本操作（clone・branch・commit・push）が一人でできる\n"
    "- HTTP・APIの仕組みを口頭で説明できる\n"
    "- SQLで基本的なSELECT・JOINが書ける\n"
    "- Dockerで開発環境を起動できる"
)

_PHASE_2_EVAL = (
    "\n【Phase 2 評価基準】\n"
    "- FastAPIでCRUD APIを設計・実装できる\n"
    "- 既存コード（Laravel・CakePHP）を読んで処理を説明できる\n"
    "- pytestで自動テストが書ける\n"
    "- 「AIに任せる部分」と「自分で判断する部分」を意識して説明できる"
)

_PHASE_3_EVAL = (
    "\n【Phase 3 評価基準】\n"
    "- セキュリティ脆弱性の種類と対策を説明できる\n"
    "- Claude APIを使ったAI機能を実装できる\n"
    "- プロンプトをバージョン管理して品質改善できる\n"
    "- DBバージョンアップの影響調査・検証ができる\n"
    "- CI/CDパイプラインを構築できる"
)

_PHASE_4_EVAL = (
    "\n【Phase 4 評価基準】\n"
    "- 要件定義から設計書・実装・テスト・ドキュメントまで一人で完結できる\n"
    "- 技術選定の根拠を論理的に説明できる\n"
    "- AIをどう活用し、何を自分で判断したかを明示できる\n"
    "- 技術記事として他者に価値ある情報を発信できる"
)


_PHASE_1_TASKS: tuple[TaskItem, ...] = (
    TaskItem(
        task_no=1,
        week_label="第1週",
        title="Git・ターミナル・VS Code 基礎",
        description=(
            "3プロジェクトのリポジトリをcloneしてブランチを切る。"
            "コミット・プッシュを体験する"
        ),
        deliverable="Git操作が一人でできる",
        skill_tags=("Git/GitHub", "開発環境"),
    ),
    TaskItem(
        task_no=2,
        week_label="第2週",
        title="PHPフレームワーク比較",
        description=(
            "Phalcon・Laravel・Yiiが1プロジェクト内に共存する理由を調査し、"
            "設計思想の違いを比較表にまとめる"
        ),
        deliverable="比較レポート1枚 / AIで調査→自分の言葉で要約",
        skill_tags=("AI協調", "業務応用"),
    ),
    TaskItem(
        task_no=3,
        week_label="第3週",
        title="HTTP・API・DBの仕組み",
        description=(
            "センサーデータ（温度・湿度・人感）がDBに届くまでの経路を"
            "図に起こす。curlでAPIレスポンスを確認する"
        ),
        deliverable="データフロー図 / 用語不明点をAIに質問",
        skill_tags=("API基礎",),
    ),
    TaskItem(
        task_no=4,
        week_label="第4週",
        title="業務DB読解",
        description=(
            "IES 96テーブルから受注関連主要テーブルを特定し、"
            "「予定注文→確定注文→案件→完了計上」のER図を手書きで作成する"
        ),
        deliverable="ER図（手書きOK） / テーブル定義の読み方をAIで確認",
        skill_tags=("DB基礎",),
    ),
    TaskItem(
        task_no=5,
        week_label="第5週",
        title="Docker・ローカル環境構築",
        description=(
            "3プロジェクトそれぞれのDocker Compose環境を立ち上げ、"
            "動作確認する。エラーが出たら自力で解決する"
        ),
        deliverable="3環境が起動できる / エラーログをAIに貼って解決練習",
        skill_tags=("開発環境",),
    ),
    TaskItem(
        task_no=6,
        week_label="第6週",
        title="AWSインフラ概念",
        description=(
            "MFRSのAWS構成（ALB→EC2→RDS）を図に起こす。"
            "ALB・ターゲットグループ・セキュリティグループの役割を説明できるようにする"
        ),
        deliverable="AWS構成図 / 各サービスの役割をAIで補足確認",
        skill_tags=("インフラ",),
    ),
    TaskItem(
        task_no=7,
        week_label="第7週",
        title="SQL実践 (SELECT・JOIN)",
        description=(
            "IESのテスト環境（ekap_test）で受注データを実際にSELECTし、"
            "受注件数・委託先別集計などのクエリを書く"
        ),
        deliverable="SQLクエリ5本以上 / クエリの書き方をAIと一緒に考える",
        skill_tags=("DB基礎",),
    ),
    TaskItem(
        task_no=8,
        week_label="第8週",
        title="フェーズ1振り返り発表",
        description=(
            "学んだことを1枚のスライドにまとめて社内ミニ発表。"
            "「AIを使った場面・使わなかった場面」を必ず含める"
        ),
        deliverable="発表スライド1枚 / メンター1on1",
        skill_tags=("発信",),
    ),
)


_PHASE_2_TASKS: tuple[TaskItem, ...] = (
    TaskItem(
        task_no=1,
        week_label="第9週",
        title="LaravelのMVC構造を読む",
        description=(
            "日程かえるくんの予約登録処理（Controller→Model→DB）を"
            "コードで追い、処理フロー図を作成する"
        ),
        deliverable="処理フロー図",
        skill_tags=("業務応用", "コードリーディング"),
    ),
    TaskItem(
        task_no=2,
        week_label="第10週",
        title="REST API設計",
        description=(
            "予約登録APIをFastAPIで設計する。エンドポイント・"
            "リクエスト/レスポンス定義・バリデーション要件を設計書に書く"
        ),
        deliverable="API設計書 / たたき台をAIに生成させ自分で修正",
        skill_tags=("API基礎", "AI協調"),
    ),
    TaskItem(
        task_no=3,
        week_label="第11週",
        title="FastAPI実装（基本CRUD）",
        description=(
            "予約登録・一覧取得・更新・削除のAPIを実装しDockerで動かす。"
            "SwaggerUIで動作確認する"
        ),
        deliverable="動くAPI（Swagger確認済）",
        skill_tags=("API基礎",),
    ),
    TaskItem(
        task_no=4,
        week_label="第12週",
        title="Pythonデータ処理",
        description=(
            "センサーCSVをpandasで読み込み、日別・時間帯別の温度・湿度・"
            "在室状況を集計する。異常値（急激な変化）の検知ロジックを実装する"
        ),
        deliverable="集計スクリプト＋異常検知ロジック",
        skill_tags=("データ処理",),
    ),
    TaskItem(
        task_no=5,
        week_label="第13週",
        title="可視化ダッシュボード",
        description=(
            "集計データをグラフ表示するFastAPI＋Vue.jsのミニダッシュボードを"
            "実装する。異常発生時のアラート表示も含める"
        ),
        deliverable="動くダッシュボード / AIにコードレビューを依頼する練習",
        skill_tags=("フロントエンド", "AI協調"),
    ),
    TaskItem(
        task_no=6,
        week_label="第14週",
        title="CakePHP読解",
        description=(
            "IESの確定注文登録処理をCakePHP 3.xコードで読み解き、"
            "処理の流れをコメント付きで説明できるようにする"
        ),
        deliverable="コード解説メモ / CakePHP記法をAIで調べながら読む",
        skill_tags=("コードリーディング", "業務応用"),
    ),
    TaskItem(
        task_no=7,
        week_label="第15週",
        title="業務ロジック再実装",
        description=(
            "確定注文登録の核心ロジック（利益率計算・委託先割当）を"
            "FastAPIで再実装する。IESのビジネスロジックを正確に再現する"
        ),
        deliverable="再実装API（テスト付き）",
        skill_tags=("API基礎", "業務応用"),
    ),
    TaskItem(
        task_no=8,
        week_label="第16週",
        title="テスト設計入門",
        description=(
            "実装したAPIに対してテスト仕様書を書き、pytestで自動テストを"
            "実装する。正常系・異常系・境界値を網羅する"
        ),
        deliverable="テスト仕様書＋自動テスト / テストケース漏れをAIに指摘させる",
        skill_tags=("テスト", "AI協調"),
    ),
    TaskItem(
        task_no=9,
        week_label="第17〜18週",
        title="ミニプロジェクト統合",
        description=(
            "Phase 2で作った3つの成果物（予約API・ダッシュボード・"
            "IES再実装）を整理し、GitHubのREADMEとして説明を書く"
        ),
        deliverable="README3本・Dockerで全部起動できる",
        skill_tags=("ドキュメント",),
    ),
    TaskItem(
        task_no=10,
        week_label="第19〜20週",
        title="フェーズ2発表",
        description=(
            "3つの成果物を動かしながら発表。「設計で迷った点」"
            "「AIに頼った場面と自分で判断した場面」を必ず言語化する"
        ),
        deliverable="発表15分＋メンター評価",
        skill_tags=("発信",),
    ),
)


_PHASE_3_TASKS: tuple[TaskItem, ...] = (
    TaskItem(
        task_no=1,
        week_label="第21〜22週",
        title="セキュリティ基礎（脆弱性の種類）",
        description=(
            "MFRE-add-01（SameSite属性）・MFRE-web-03（XSS対策）の"
            "詳細設計書を読み、「なぜ危険なのか」を一般人向けに説明できるよう整理する"
        ),
        deliverable="脆弱性解説ドキュメント / 「なぜ危険？」をAIと深掘り",
        skill_tags=("セキュリティ", "AI協調"),
    ),
    TaskItem(
        task_no=2,
        week_label="第23〜24週",
        title="セキュリティ修正実装",
        description=(
            "MFRE-web-01（workId認可チェック）を実際に修正し、"
            "修正前後のコードと影響範囲をドキュメント化する。"
            "AIレビューで見逃しがないか確認する"
        ),
        deliverable="修正コード＋テスト仕様書 / AIが見逃した脆弱性を自力で探す",
        skill_tags=("セキュリティ", "テスト"),
    ),
    TaskItem(
        task_no=3,
        week_label="第25〜26週",
        title="Claude API基礎・プロンプト設計",
        description=(
            "センサーデータをClaude APIに渡し「今日の利用者サマリー（家族向け）」を"
            "自動生成する。プロンプトをバージョン管理し品質を改善していく"
        ),
        deliverable="自動生成サンプル10件 / プロンプトを仕様書として管理する習慣を付ける",
        skill_tags=("AI協調", "API基礎"),
    ),
    TaskItem(
        task_no=4,
        week_label="第27〜28週",
        title="LINE Webhook連携",
        description=(
            "生成したサマリーをLINE Webhookで家族へ自動送信する機能を実装する。"
            "送信失敗時のリトライ・エラーハンドリングも実装する"
        ),
        deliverable="LINE通知の動作確認",
        skill_tags=("API基礎", "インフラ"),
    ),
    TaskItem(
        task_no=5,
        week_label="第29〜30週",
        title="MySQL 8.4移行：調査フェーズ",
        description=(
            "MySQL 8.0→8.4の変更点を調査し、IESへの影響箇所をリストアップする。"
            "既存のテスト仕様書・報告書を読んで理解を深める"
        ),
        deliverable="影響調査レポート / 変更点の技術的背景をAIで深掘り",
        skill_tags=("DB基礎", "AI協調"),
    ),
    TaskItem(
        task_no=6,
        week_label="第31〜32週",
        title="MySQL 8.4移行：Docker検証",
        description=(
            "ローカルDocker環境（mysql:8.4）でIESを動かし、テストを実行する。"
            "FAIL項目を調査して原因と対応方針をまとめる"
        ),
        deliverable="検証報告書（PASS/FAIL一覧）",
        skill_tags=("DB基礎", "開発環境"),
    ),
    TaskItem(
        task_no=7,
        week_label="第33〜34週",
        title="CI/CD・コード品質管理",
        description=(
            "GitHub Actionsでテスト自動実行パイプラインを構築する。"
            "linter（flake8/eslint）とテストカバレッジレポートも含める"
        ),
        deliverable="CI/CDパイプライン稼働 / YAMLの書き方をAIと一緒に作成",
        skill_tags=("CI/CD", "AI協調"),
    ),
    TaskItem(
        task_no=8,
        week_label="第35〜36週",
        title="フェーズ3発表",
        description=(
            "セキュリティ対応・AI連携・MySQL移行の3テーマを発表。"
            "「どこをAIに任せ、どこを自分で判断したか」を具体的に示す"
        ),
        deliverable="発表20分＋メンター評価",
        skill_tags=("発信",),
    ),
)


_PHASE_4_TASKS: tuple[TaskItem, ...] = (
    TaskItem(
        task_no=1,
        week_label="第37〜38週",
        title="卒業課題テーマ選定・設計",
        description=(
            "A（MFRSサポートAIボット）・B（Nichinichi Weeklyレポート）・"
            "C（IES案件管理AI）から1つ選択し、要件定義→設計書を作成する"
        ),
        deliverable="設計書（レビュー通過） / 設計書たたき台をAIに生成させ修正",
        skill_tags=("プロダクト設計", "AI協調"),
    ),
    TaskItem(
        task_no=2,
        week_label="第39〜42週",
        title="卒業課題：実装フェーズ",
        description=(
            "設計書に基づき実装を進める。週1回進捗報告（詰まった点・"
            "AIを使った場面を必ず含める）。メンターはコードレビューのみ行い答えは教えない"
        ),
        deliverable="週次進捗レポート4本",
        skill_tags=("AI協調",),
    ),
    TaskItem(
        task_no=3,
        week_label="第43〜44週",
        title="テスト・品質確認",
        description=(
            "自動テスト・手動テストを実施し、テスト結果報告書を作成する。"
            "セキュリティ・個人情報の取り扱いについても設計を見直す"
        ),
        deliverable="テスト報告書",
        skill_tags=("テスト", "セキュリティ"),
    ),
    TaskItem(
        task_no=4,
        week_label="第45〜46週",
        title="ドキュメント整備・技術発信",
        description=(
            "README・設計書・操作マニュアルを整備する。"
            "社内ブログ or Zennに「学んだことと気づき」を1本書く"
        ),
        deliverable="ドキュメント一式＋技術記事1本",
        skill_tags=("ドキュメント", "発信"),
    ),
    TaskItem(
        task_no=5,
        week_label="第47〜48週",
        title="卒業発表・振り返り",
        description=(
            "動くプロダクトを見せながら30分発表。技術選定の根拠・"
            "AIをどう活用したか・次に取り組みたいことを説明できること"
        ),
        deliverable="発表30分＋全員レビュー / 1年間の学習ポートフォリオ",
        skill_tags=("発信",),
    ),
)


AI_ERA_SE_COURSE = CourseData(
    id=uuid.UUID("00000000-0000-4000-8000-000000000002"),
    slug="ai-era-se",
    title="AI時代SE育成カリキュラム",
    description=(
        "12 ヶ月のSE育成カリキュラム（4 フェーズ・31 課題）。"
        "MFRS / Nichinichi Anshin / IES を題材にする。"
    ),
    sort_order=1,
    phases=(
        PhaseData(
            phase=1,
            title="土台づくり",
            goal="開発環境・業務の仕組み・AIとの最初の対話を体感する",
            tasks=_PHASE_1_TASKS,
            system_prompt=(
                _SE_TUTOR_BASE
                + "\n現在のフェーズ：Phase 1「土台づくり」（第1〜8週）。\n"
                "指導方針：\n"
                "- 用語が新しい受講者を前提に、専門語を必ず噛み砕く\n"
                "- 「答えを返す」より「次の問いを立てさせる」\n"
                "- 3〜5文程度で日本語で返答する"
                + _PHASE_1_EVAL
            ),
        ),
        PhaseData(
            phase=2,
            title="実践力の習得",
            goal="小さくても動くものを設計〜実装まで作り切る体験をする",
            tasks=_PHASE_2_TASKS,
            system_prompt=(
                _SE_TUTOR_BASE
                + "\n現在のフェーズ：Phase 2「実践力の習得」（第9〜20週）。\n"
                "指導方針：\n"
                "- 設計と実装の両方を手を動かして進める\n"
                "- 既存フレームワークのコードリーディングを重視する\n"
                "- 3〜5文程度で日本語で返答する"
                + _PHASE_2_EVAL
            ),
        ),
        PhaseData(
            phase=3,
            title="AI活用・協働",
            goal="AIを相棒として使いこなし、生産性と品質を同時に上げる",
            tasks=_PHASE_3_TASKS,
            system_prompt=(
                _SE_TUTOR_BASE
                + "\n現在のフェーズ：Phase 3「AI活用・協働」（第21〜36週）。\n"
                "指導方針：\n"
                "- セキュリティとAI連携の両立を意識させる\n"
                "- プロンプト改善のPDCAを習慣化させる\n"
                "- 3〜5文程度で日本語で返答する"
                + _PHASE_3_EVAL
            ),
        ),
        PhaseData(
            phase=4,
            title="自律・発信",
            goal="チームに貢献し、後輩を教えられるSEになる",
            tasks=_PHASE_4_TASKS,
            system_prompt=(
                _SE_TUTOR_BASE
                + "\n現在のフェーズ：Phase 4「自律・発信」（第37〜48週）。\n"
                "指導方針：\n"
                "- 卒業課題の自律推進を支援し、答えは直接教えない\n"
                "- 技術選定の根拠を言語化させる\n"
                "- 3〜5文程度で日本語で返答する"
                + _PHASE_4_EVAL
            ),
        ),
    ),
)
