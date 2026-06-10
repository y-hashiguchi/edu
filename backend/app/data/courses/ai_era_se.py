"""ai-era-se course definition (Sprint 7).

Pilot scope: Phase 1 only (8 weekly tasks). AI usage rules from the
syllabus are injected literally into the system prompt of every phase
so the tutor consistently reinforces the same 5 rules. Phase 2-4 are
deferred (see follow-up doc)."""

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


AI_ERA_SE_COURSE = CourseData(
    id=uuid.UUID("00000000-0000-4000-8000-000000000002"),
    slug="ai-era-se",
    title="AI時代SE育成カリキュラム",
    description=(
        "12 ヶ月のSE育成カリキュラム。Phase 1（8 課題）は土台づくり。"
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
    ),
)
