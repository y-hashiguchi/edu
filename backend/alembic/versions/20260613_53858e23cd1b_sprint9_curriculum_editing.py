"""sprint9_curriculum_editing

Revision ID: 53858e23cd1b
Revises: a1b2c3d4e5f6
Create Date: 2026-06-13 13:37:57.441056

Sprint 9: introduce curriculum_phases + curriculum_tasks tables for
admin-editable curriculum content. Each row holds both the published
column and a `draft_*` overlay (NULL = unedited).

Initial seed is written by **literal dict copy** of the source-of-truth
Python dataclass course definitions at migration authoring time. Doing
the copy here (instead of importing the in-memory registry) freezes the
seed so future Python edits do NOT retroactively change this migration's
behaviour — important for `alembic downgrade -1 && upgrade head`
reproducibility on production.
"""
import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '53858e23cd1b'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


AI_DRIVEN_DEV_UUID = uuid.UUID("00000000-0000-4000-8000-000000000001")
AI_ERA_SE_UUID = uuid.UUID("00000000-0000-4000-8000-000000000002")


# ---------------------------------------------------------------------------
# Frozen seed payload — copied verbatim from the ai-driven-dev course
# definition at migration authoring time (Sprint 9). DO NOT import the
# in-memory registry; the literal dict is the source of truth here.
# ---------------------------------------------------------------------------

_AI_DRIVEN_DEV_PHASES = [
    {
        "phase_no": 1,
        "title": "開発環境の近代化",
        "goal": "AIツールを使いこなすための「土台」を固める",
        "system_prompt": (
            "あなたはAI駆動型開発を教える教育AIチューターです。\n"
            "対象はJava/Python基礎・HTML/CSS/JS・DB基礎修了済みの研修生です。\n"
            "現在のフェーズ：Phase1「開発環境の近代化」。\n"
            "Git・VSCode・REST APIの基礎を教えます。\n"
            "指導方針：\n"
            "- 既存の知識（Java/Python）と紐付けて説明する\n"
            "- 手を動かさせることを重視する\n"
            "- 答えをすぐ教えず、まず考えさせる\n"
            "- 3〜5文程度で日本語で返答する"
        ),
        "tasks": [
            {
                "task_no": 1,
                "title": "Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成",
                "description": "Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成",
                "skill_tags": ["Git/GitHub"],
                "deliverable": None,
                "week_label": None,
            },
            {
                "task_no": 2,
                "title": "VSCode拡張（GitLens・REST Client・GitHub Copilot）の導入と動作確認",
                "description": "VSCode拡張（GitLens・REST Client・GitHub Copilot）の導入と動作確認",
                "skill_tags": ["開発環境"],
                "deliverable": None,
                "week_label": None,
            },
            {
                "task_no": 3,
                "title": "curlでREST APIを叩き、JSONレスポンス構造をまとめる",
                "description": "curlでREST APIを叩き、JSONレスポンス構造をまとめる",
                "skill_tags": ["API基礎"],
                "deliverable": None,
                "week_label": None,
            },
        ],
    },
    {
        "phase_no": 2,
        "title": "AIツール活用マスター",
        "goal": "「AIと一緒にコードを書く」体験を積む",
        "system_prompt": (
            "あなたはAI駆動型開発を教える教育AIチューターです。\n"
            "対象はJava/Python基礎・HTML/CSS/JS・DB基礎修了済みの研修生です。\n"
            "現在のフェーズ：Phase2「AIツール活用マスター」。\n"
            "Cursor IDE・GitHub Copilot・Claudeの実践的な使い方を指導します。\n"
            "指導方針：\n"
            "- プロンプトの良し悪しを具体例で教える\n"
            "- AIを鵜呑みにしない批判的思考を育てる\n"
            "- 実際に手を動かさせる課題を出す\n"
            "- 3〜5文程度で日本語で返答する"
        ),
        "tasks": [
            {
                "task_no": 1,
                "title": "Cursor IDEで顧客管理API（CRUD）をゼロから作成。AIとのやり取りログを記録",
                "description": "Cursor IDEで顧客管理API（CRUD）をゼロから作成。AIとのやり取りログを記録",
                "skill_tags": ["AI協調", "API基礎"],
                "deliverable": None,
                "week_label": None,
            },
            {
                "task_no": 2,
                "title": "同機能をGitHub Copilotでも実装し、2つのAIの違いをまとめる",
                "description": "同機能をGitHub Copilotでも実装し、2つのAIの違いをまとめる",
                "skill_tags": ["AI協調", "開発環境"],
                "deliverable": None,
                "week_label": None,
            },
            {
                "task_no": 3,
                "title": "ClaudeにコードレビューさせてPDCA",
                "description": "ClaudeにコードレビューさせてPDCA",
                "skill_tags": ["AI協調", "コードレビュー"],
                "deliverable": None,
                "week_label": None,
            },
        ],
    },
    {
        "phase_no": 3,
        "title": "AI協調型開発ワークフロー",
        "goal": "実際の開発タスクにAIを組み込む",
        "system_prompt": (
            "あなたはAI駆動型開発を教える教育AIチューターです。\n"
            "対象はJava/Python基礎・HTML/CSS/JS・DB基礎修了済みの研修生です。\n"
            "現在のフェーズ：Phase3「AI協調型開発ワークフロー」。\n"
            "AIペアプログラミング・コードレビュー・テスト自動生成を教えます。\n"
            "指導方針：\n"
            "- AIの出力を検証する習慣をつけさせる\n"
            "- 開発品質の観点（セキュリティ・テスト・可読性）を意識させる\n"
            "- ソクラテス式で深く考えさせる\n"
            "- 3〜5文程度で日本語で返答する"
        ),
        "tasks": [
            {
                "task_no": 1,
                "title": "Phase2で作ったAPIをAIにレビューさせ、セキュリティ・パフォーマンス・可読性の観点で整理",
                "description": "Phase2で作ったAPIをAIにレビューさせ、セキュリティ・パフォーマンス・可読性の観点で整理",
                "skill_tags": ["コードレビュー", "AI協調"],
                "deliverable": None,
                "week_label": None,
            },
            {
                "task_no": 2,
                "title": "仕様書（箇条書き）からテストコードを自動生成し、不足ケースを3つ指摘",
                "description": "仕様書（箇条書き）からテストコードを自動生成し、不足ケースを3つ指摘",
                "skill_tags": ["テスト", "AI協調"],
                "deliverable": None,
                "week_label": None,
            },
            {
                "task_no": 3,
                "title": "AIとペアで新機能（検索機能など）を実装。会話ログも提出",
                "description": "AIとペアで新機能（検索機能など）を実装。会話ログも提出",
                "skill_tags": ["AI協調", "設計"],
                "deliverable": None,
                "week_label": None,
            },
        ],
    },
    {
        "phase_no": 4,
        "title": "AIアプリ開発実践",
        "goal": "「AIを使う」から「AIを組み込む」へ",
        "system_prompt": (
            "あなたはAI駆動型開発を教える教育AIチューターです。\n"
            "対象はJava/Python基礎・HTML/CSS/JS・DB基礎修了済みの研修生です。\n"
            "現在のフェーズ：Phase4「AIアプリ開発実践」。\n"
            "Claude/OpenAI API連携・RAG・PythonでのAIツール開発を教えます。\n"
            "指導方針：\n"
            "- 実装の具体的な手順をステップで示す\n"
            "- RAGの概念をわかりやすく説明する\n"
            "- 企画力・提案力も育てる\n"
            "- 3〜5文程度で日本語で返答する"
        ),
        "tasks": [
            {
                "task_no": 1,
                "title": "Claude APIでチャットボット作成（会話履歴保持・システムプロンプト設定）",
                "description": "Claude APIでチャットボット作成（会話履歴保持・システムプロンプト設定）",
                "skill_tags": ["LLM活用"],
                "deliverable": None,
                "week_label": None,
            },
            {
                "task_no": 2,
                "title": "RAGデモ作成（Python + ChromaDB + Claude API）",
                "description": "RAGデモ作成（Python + ChromaDB + Claude API）",
                "skill_tags": ["RAG/ベクトル検索", "LLM活用"],
                "deliverable": None,
                "week_label": None,
            },
            {
                "task_no": 3,
                "title": "業務課題を解決するAIツールの企画書作成（課題・解決策・技術構成・効果試算）",
                "description": "業務課題を解決するAIツールの企画書作成（課題・解決策・技術構成・効果試算）",
                "skill_tags": ["業務応用", "設計"],
                "deliverable": None,
                "week_label": None,
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Frozen seed payload — copied verbatim from
# app/data/courses/ai_era_se.py at migration authoring time (Sprint 9).
# The helper constants `_SE_TUTOR_BASE`, `AI_USAGE_RULES`, `_PHASE_X_EVAL`
# have been resolved into literal text below — this migration must NOT
# reference those helpers.
# ---------------------------------------------------------------------------

# Resolved value of _SE_TUTOR_BASE + per-phase guidance + _PHASE_X_EVAL.

_AI_ERA_SE_PHASE_1_SYSTEM_PROMPT = (
    "あなたは AI 時代の SE 育成を担う AI チューターです。\n"
    "対象は初級エンジニア（プログラミング経験 1 年未満）で、業務プロジェクト"
    "（MFRS / Nichinichi Anshin / IES）を題材に学びます。\n"
    "\n"
    "【AI 活用ルール】\n"
    "1. AIに聞いた内容は必ず自分の言葉で再説明できること（コピペ禁止）\n"
    "2. AIが生成したコードは理解してから使うこと（動けばOKは禁止）\n"
    "3. プロンプトはバージョン管理すること（Gitで管理、改善履歴を残す）\n"
    "4. AIが見逃した問題を自分で探す習慣を付けること\n"
    "5. 「AIに任せた場面」と「自分で判断した場面」を毎週の作業ログに記録すること\n"
    "\n"
    "\n現在のフェーズ：Phase 1「土台づくり」（第1〜8週）。\n"
    "指導方針：\n"
    "- 用語が新しい受講者を前提に、専門語を必ず噛み砕く\n"
    "- 「答えを返す」より「次の問いを立てさせる」\n"
    "- 3〜5文程度で日本語で返答する"
    "\n【Phase 1 評価基準】\n"
    "- Gitの基本操作（clone・branch・commit・push）が一人でできる\n"
    "- HTTP・APIの仕組みを口頭で説明できる\n"
    "- SQLで基本的なSELECT・JOINが書ける\n"
    "- Dockerで開発環境を起動できる"
)

_AI_ERA_SE_PHASE_2_SYSTEM_PROMPT = (
    "あなたは AI 時代の SE 育成を担う AI チューターです。\n"
    "対象は初級エンジニア（プログラミング経験 1 年未満）で、業務プロジェクト"
    "（MFRS / Nichinichi Anshin / IES）を題材に学びます。\n"
    "\n"
    "【AI 活用ルール】\n"
    "1. AIに聞いた内容は必ず自分の言葉で再説明できること（コピペ禁止）\n"
    "2. AIが生成したコードは理解してから使うこと（動けばOKは禁止）\n"
    "3. プロンプトはバージョン管理すること（Gitで管理、改善履歴を残す）\n"
    "4. AIが見逃した問題を自分で探す習慣を付けること\n"
    "5. 「AIに任せた場面」と「自分で判断した場面」を毎週の作業ログに記録すること\n"
    "\n"
    "\n現在のフェーズ：Phase 2「実践力の習得」（第9〜20週）。\n"
    "指導方針：\n"
    "- 設計と実装の両方を手を動かして進める\n"
    "- 既存フレームワークのコードリーディングを重視する\n"
    "- 3〜5文程度で日本語で返答する"
    "\n【Phase 2 評価基準】\n"
    "- FastAPIでCRUD APIを設計・実装できる\n"
    "- 既存コード（Laravel・CakePHP）を読んで処理を説明できる\n"
    "- pytestで自動テストが書ける\n"
    "- 「AIに任せる部分」と「自分で判断する部分」を意識して説明できる"
)

_AI_ERA_SE_PHASE_3_SYSTEM_PROMPT = (
    "あなたは AI 時代の SE 育成を担う AI チューターです。\n"
    "対象は初級エンジニア（プログラミング経験 1 年未満）で、業務プロジェクト"
    "（MFRS / Nichinichi Anshin / IES）を題材に学びます。\n"
    "\n"
    "【AI 活用ルール】\n"
    "1. AIに聞いた内容は必ず自分の言葉で再説明できること（コピペ禁止）\n"
    "2. AIが生成したコードは理解してから使うこと（動けばOKは禁止）\n"
    "3. プロンプトはバージョン管理すること（Gitで管理、改善履歴を残す）\n"
    "4. AIが見逃した問題を自分で探す習慣を付けること\n"
    "5. 「AIに任せた場面」と「自分で判断した場面」を毎週の作業ログに記録すること\n"
    "\n"
    "\n現在のフェーズ：Phase 3「AI活用・協働」（第21〜36週）。\n"
    "指導方針：\n"
    "- セキュリティとAI連携の両立を意識させる\n"
    "- プロンプト改善のPDCAを習慣化させる\n"
    "- 3〜5文程度で日本語で返答する"
    "\n【Phase 3 評価基準】\n"
    "- セキュリティ脆弱性の種類と対策を説明できる\n"
    "- Claude APIを使ったAI機能を実装できる\n"
    "- プロンプトをバージョン管理して品質改善できる\n"
    "- DBバージョンアップの影響調査・検証ができる\n"
    "- CI/CDパイプラインを構築できる"
)

_AI_ERA_SE_PHASE_4_SYSTEM_PROMPT = (
    "あなたは AI 時代の SE 育成を担う AI チューターです。\n"
    "対象は初級エンジニア（プログラミング経験 1 年未満）で、業務プロジェクト"
    "（MFRS / Nichinichi Anshin / IES）を題材に学びます。\n"
    "\n"
    "【AI 活用ルール】\n"
    "1. AIに聞いた内容は必ず自分の言葉で再説明できること（コピペ禁止）\n"
    "2. AIが生成したコードは理解してから使うこと（動けばOKは禁止）\n"
    "3. プロンプトはバージョン管理すること（Gitで管理、改善履歴を残す）\n"
    "4. AIが見逃した問題を自分で探す習慣を付けること\n"
    "5. 「AIに任せた場面」と「自分で判断した場面」を毎週の作業ログに記録すること\n"
    "\n"
    "\n現在のフェーズ：Phase 4「自律・発信」（第37〜48週）。\n"
    "指導方針：\n"
    "- 卒業課題の自律推進を支援し、答えは直接教えない\n"
    "- 技術選定の根拠を言語化させる\n"
    "- 3〜5文程度で日本語で返答する"
    "\n【Phase 4 評価基準】\n"
    "- 要件定義から設計書・実装・テスト・ドキュメントまで一人で完結できる\n"
    "- 技術選定の根拠を論理的に説明できる\n"
    "- AIをどう活用し、何を自分で判断したかを明示できる\n"
    "- 技術記事として他者に価値ある情報を発信できる"
)


_AI_ERA_SE_PHASES = [
    {
        "phase_no": 1,
        "title": "土台づくり",
        "goal": "開発環境・業務の仕組み・AIとの最初の対話を体感する",
        "system_prompt": _AI_ERA_SE_PHASE_1_SYSTEM_PROMPT,
        "tasks": [
            {
                "task_no": 1,
                "title": "Git・ターミナル・VS Code 基礎",
                "description": (
                    "3プロジェクトのリポジトリをcloneしてブランチを切る。"
                    "コミット・プッシュを体験する"
                ),
                "skill_tags": ["Git/GitHub", "開発環境"],
                "deliverable": "Git操作が一人でできる",
                "week_label": "第1週",
            },
            {
                "task_no": 2,
                "title": "PHPフレームワーク比較",
                "description": (
                    "Phalcon・Laravel・Yiiが1プロジェクト内に共存する理由を調査し、"
                    "設計思想の違いを比較表にまとめる"
                ),
                "skill_tags": ["AI協調", "業務応用"],
                "deliverable": "比較レポート1枚 / AIで調査→自分の言葉で要約",
                "week_label": "第2週",
            },
            {
                "task_no": 3,
                "title": "HTTP・API・DBの仕組み",
                "description": (
                    "センサーデータ（温度・湿度・人感）がDBに届くまでの経路を"
                    "図に起こす。curlでAPIレスポンスを確認する"
                ),
                "skill_tags": ["API基礎"],
                "deliverable": "データフロー図 / 用語不明点をAIに質問",
                "week_label": "第3週",
            },
            {
                "task_no": 4,
                "title": "業務DB読解",
                "description": (
                    "IES 96テーブルから受注関連主要テーブルを特定し、"
                    "「予定注文→確定注文→案件→完了計上」のER図を手書きで作成する"
                ),
                "skill_tags": ["DB基礎"],
                "deliverable": "ER図（手書きOK） / テーブル定義の読み方をAIで確認",
                "week_label": "第4週",
            },
            {
                "task_no": 5,
                "title": "Docker・ローカル環境構築",
                "description": (
                    "3プロジェクトそれぞれのDocker Compose環境を立ち上げ、"
                    "動作確認する。エラーが出たら自力で解決する"
                ),
                "skill_tags": ["開発環境"],
                "deliverable": "3環境が起動できる / エラーログをAIに貼って解決練習",
                "week_label": "第5週",
            },
            {
                "task_no": 6,
                "title": "AWSインフラ概念",
                "description": (
                    "MFRSのAWS構成（ALB→EC2→RDS）を図に起こす。"
                    "ALB・ターゲットグループ・セキュリティグループの役割を説明できるようにする"
                ),
                "skill_tags": ["インフラ"],
                "deliverable": "AWS構成図 / 各サービスの役割をAIで補足確認",
                "week_label": "第6週",
            },
            {
                "task_no": 7,
                "title": "SQL実践 (SELECT・JOIN)",
                "description": (
                    "IESのテスト環境（ekap_test）で受注データを実際にSELECTし、"
                    "受注件数・委託先別集計などのクエリを書く"
                ),
                "skill_tags": ["DB基礎"],
                "deliverable": "SQLクエリ5本以上 / クエリの書き方をAIと一緒に考える",
                "week_label": "第7週",
            },
            {
                "task_no": 8,
                "title": "フェーズ1振り返り発表",
                "description": (
                    "学んだことを1枚のスライドにまとめて社内ミニ発表。"
                    "「AIを使った場面・使わなかった場面」を必ず含める"
                ),
                "skill_tags": ["発信"],
                "deliverable": "発表スライド1枚 / メンター1on1",
                "week_label": "第8週",
            },
        ],
    },
    {
        "phase_no": 2,
        "title": "実践力の習得",
        "goal": "小さくても動くものを設計〜実装まで作り切る体験をする",
        "system_prompt": _AI_ERA_SE_PHASE_2_SYSTEM_PROMPT,
        "tasks": [
            {
                "task_no": 1,
                "title": "LaravelのMVC構造を読む",
                "description": (
                    "日程かえるくんの予約登録処理（Controller→Model→DB）を"
                    "コードで追い、処理フロー図を作成する"
                ),
                "skill_tags": ["業務応用", "コードリーディング"],
                "deliverable": "処理フロー図",
                "week_label": "第9週",
            },
            {
                "task_no": 2,
                "title": "REST API設計",
                "description": (
                    "予約登録APIをFastAPIで設計する。エンドポイント・"
                    "リクエスト/レスポンス定義・バリデーション要件を設計書に書く"
                ),
                "skill_tags": ["API基礎", "AI協調"],
                "deliverable": "API設計書 / たたき台をAIに生成させ自分で修正",
                "week_label": "第10週",
            },
            {
                "task_no": 3,
                "title": "FastAPI実装（基本CRUD）",
                "description": (
                    "予約登録・一覧取得・更新・削除のAPIを実装しDockerで動かす。"
                    "SwaggerUIで動作確認する"
                ),
                "skill_tags": ["API基礎"],
                "deliverable": "動くAPI（Swagger確認済）",
                "week_label": "第11週",
            },
            {
                "task_no": 4,
                "title": "Pythonデータ処理",
                "description": (
                    "センサーCSVをpandasで読み込み、日別・時間帯別の温度・湿度・"
                    "在室状況を集計する。異常値（急激な変化）の検知ロジックを実装する"
                ),
                "skill_tags": ["データ処理"],
                "deliverable": "集計スクリプト＋異常検知ロジック",
                "week_label": "第12週",
            },
            {
                "task_no": 5,
                "title": "可視化ダッシュボード",
                "description": (
                    "集計データをグラフ表示するFastAPI＋Vue.jsのミニダッシュボードを"
                    "実装する。異常発生時のアラート表示も含める"
                ),
                "skill_tags": ["フロントエンド", "AI協調"],
                "deliverable": "動くダッシュボード / AIにコードレビューを依頼する練習",
                "week_label": "第13週",
            },
            {
                "task_no": 6,
                "title": "CakePHP読解",
                "description": (
                    "IESの確定注文登録処理をCakePHP 3.xコードで読み解き、"
                    "処理の流れをコメント付きで説明できるようにする"
                ),
                "skill_tags": ["コードリーディング", "業務応用"],
                "deliverable": "コード解説メモ / CakePHP記法をAIで調べながら読む",
                "week_label": "第14週",
            },
            {
                "task_no": 7,
                "title": "業務ロジック再実装",
                "description": (
                    "確定注文登録の核心ロジック（利益率計算・委託先割当）を"
                    "FastAPIで再実装する。IESのビジネスロジックを正確に再現する"
                ),
                "skill_tags": ["API基礎", "業務応用"],
                "deliverable": "再実装API（テスト付き）",
                "week_label": "第15週",
            },
            {
                "task_no": 8,
                "title": "テスト設計入門",
                "description": (
                    "実装したAPIに対してテスト仕様書を書き、pytestで自動テストを"
                    "実装する。正常系・異常系・境界値を網羅する"
                ),
                "skill_tags": ["テスト", "AI協調"],
                "deliverable": "テスト仕様書＋自動テスト / テストケース漏れをAIに指摘させる",
                "week_label": "第16週",
            },
            {
                "task_no": 9,
                "title": "ミニプロジェクト統合",
                "description": (
                    "Phase 2で作った3つの成果物（予約API・ダッシュボード・"
                    "IES再実装）を整理し、GitHubのREADMEとして説明を書く"
                ),
                "skill_tags": ["ドキュメント"],
                "deliverable": "README3本・Dockerで全部起動できる",
                "week_label": "第17〜18週",
            },
            {
                "task_no": 10,
                "title": "フェーズ2発表",
                "description": (
                    "3つの成果物を動かしながら発表。「設計で迷った点」"
                    "「AIに頼った場面と自分で判断した場面」を必ず言語化する"
                ),
                "skill_tags": ["発信"],
                "deliverable": "発表15分＋メンター評価",
                "week_label": "第19〜20週",
            },
        ],
    },
    {
        "phase_no": 3,
        "title": "AI活用・協働",
        "goal": "AIを相棒として使いこなし、生産性と品質を同時に上げる",
        "system_prompt": _AI_ERA_SE_PHASE_3_SYSTEM_PROMPT,
        "tasks": [
            {
                "task_no": 1,
                "title": "セキュリティ基礎（脆弱性の種類）",
                "description": (
                    "MFRE-add-01（SameSite属性）・MFRE-web-03（XSS対策）の"
                    "詳細設計書を読み、「なぜ危険なのか」を一般人向けに説明できるよう整理する"
                ),
                "skill_tags": ["セキュリティ", "AI協調"],
                "deliverable": "脆弱性解説ドキュメント / 「なぜ危険？」をAIと深掘り",
                "week_label": "第21〜22週",
            },
            {
                "task_no": 2,
                "title": "セキュリティ修正実装",
                "description": (
                    "MFRE-web-01（workId認可チェック）を実際に修正し、"
                    "修正前後のコードと影響範囲をドキュメント化する。"
                    "AIレビューで見逃しがないか確認する"
                ),
                "skill_tags": ["セキュリティ", "テスト"],
                "deliverable": "修正コード＋テスト仕様書 / AIが見逃した脆弱性を自力で探す",
                "week_label": "第23〜24週",
            },
            {
                "task_no": 3,
                "title": "Claude API基礎・プロンプト設計",
                "description": (
                    "センサーデータをClaude APIに渡し「今日の利用者サマリー（家族向け）」を"
                    "自動生成する。プロンプトをバージョン管理し品質を改善していく"
                ),
                "skill_tags": ["AI協調", "API基礎"],
                "deliverable": "自動生成サンプル10件 / プロンプトを仕様書として管理する習慣を付ける",
                "week_label": "第25〜26週",
            },
            {
                "task_no": 4,
                "title": "LINE Webhook連携",
                "description": (
                    "生成したサマリーをLINE Webhookで家族へ自動送信する機能を実装する。"
                    "送信失敗時のリトライ・エラーハンドリングも実装する"
                ),
                "skill_tags": ["API基礎", "インフラ"],
                "deliverable": "LINE通知の動作確認",
                "week_label": "第27〜28週",
            },
            {
                "task_no": 5,
                "title": "MySQL 8.4移行：調査フェーズ",
                "description": (
                    "MySQL 8.0→8.4の変更点を調査し、IESへの影響箇所をリストアップする。"
                    "既存のテスト仕様書・報告書を読んで理解を深める"
                ),
                "skill_tags": ["DB基礎", "AI協調"],
                "deliverable": "影響調査レポート / 変更点の技術的背景をAIで深掘り",
                "week_label": "第29〜30週",
            },
            {
                "task_no": 6,
                "title": "MySQL 8.4移行：Docker検証",
                "description": (
                    "ローカルDocker環境（mysql:8.4）でIESを動かし、テストを実行する。"
                    "FAIL項目を調査して原因と対応方針をまとめる"
                ),
                "skill_tags": ["DB基礎", "開発環境"],
                "deliverable": "検証報告書（PASS/FAIL一覧）",
                "week_label": "第31〜32週",
            },
            {
                "task_no": 7,
                "title": "CI/CD・コード品質管理",
                "description": (
                    "GitHub Actionsでテスト自動実行パイプラインを構築する。"
                    "linter（flake8/eslint）とテストカバレッジレポートも含める"
                ),
                "skill_tags": ["CI/CD", "AI協調"],
                "deliverable": "CI/CDパイプライン稼働 / YAMLの書き方をAIと一緒に作成",
                "week_label": "第33〜34週",
            },
            {
                "task_no": 8,
                "title": "フェーズ3発表",
                "description": (
                    "セキュリティ対応・AI連携・MySQL移行の3テーマを発表。"
                    "「どこをAIに任せ、どこを自分で判断したか」を具体的に示す"
                ),
                "skill_tags": ["発信"],
                "deliverable": "発表20分＋メンター評価",
                "week_label": "第35〜36週",
            },
        ],
    },
    {
        "phase_no": 4,
        "title": "自律・発信",
        "goal": "チームに貢献し、後輩を教えられるSEになる",
        "system_prompt": _AI_ERA_SE_PHASE_4_SYSTEM_PROMPT,
        "tasks": [
            {
                "task_no": 1,
                "title": "卒業課題テーマ選定・設計",
                "description": (
                    "A（MFRSサポートAIボット）・B（Nichinichi Weeklyレポート）・"
                    "C（IES案件管理AI）から1つ選択し、要件定義→設計書を作成する"
                ),
                "skill_tags": ["プロダクト設計", "AI協調"],
                "deliverable": "設計書（レビュー通過） / 設計書たたき台をAIに生成させ修正",
                "week_label": "第37〜38週",
            },
            {
                "task_no": 2,
                "title": "卒業課題：実装フェーズ",
                "description": (
                    "設計書に基づき実装を進める。週1回進捗報告（詰まった点・"
                    "AIを使った場面を必ず含める）。メンターはコードレビューのみ行い答えは教えない"
                ),
                "skill_tags": ["AI協調"],
                "deliverable": "週次進捗レポート4本",
                "week_label": "第39〜42週",
            },
            {
                "task_no": 3,
                "title": "テスト・品質確認",
                "description": (
                    "自動テスト・手動テストを実施し、テスト結果報告書を作成する。"
                    "セキュリティ・個人情報の取り扱いについても設計を見直す"
                ),
                "skill_tags": ["テスト", "セキュリティ"],
                "deliverable": "テスト報告書",
                "week_label": "第43〜44週",
            },
            {
                "task_no": 4,
                "title": "ドキュメント整備・技術発信",
                "description": (
                    "README・設計書・操作マニュアルを整備する。"
                    "社内ブログ or Zennに「学んだことと気づき」を1本書く"
                ),
                "skill_tags": ["ドキュメント", "発信"],
                "deliverable": "ドキュメント一式＋技術記事1本",
                "week_label": "第45〜46週",
            },
            {
                "task_no": 5,
                "title": "卒業発表・振り返り",
                "description": (
                    "動くプロダクトを見せながら30分発表。技術選定の根拠・"
                    "AIをどう活用したか・次に取り組みたいことを説明できること"
                ),
                "skill_tags": ["発信"],
                "deliverable": "発表30分＋全員レビュー / 1年間の学習ポートフォリオ",
                "week_label": "第47〜48週",
            },
        ],
    },
]


_SEED_PAYLOAD = [
    (AI_DRIVEN_DEV_UUID, _AI_DRIVEN_DEV_PHASES),
    (AI_ERA_SE_UUID, _AI_ERA_SE_PHASES),
]


def upgrade() -> None:
    # 1. curriculum_phases
    op.create_table(
        "curriculum_phases",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "course_id",
            sa.UUID(),
            sa.ForeignKey("courses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("phase_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("draft_title", sa.Text(), nullable=True),
        sa.Column("draft_goal", sa.Text(), nullable=True),
        sa.Column("draft_system_prompt", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "course_id", "phase_no", name="uq_curriculum_phases_course_phase_no"
        ),
    )
    op.create_index(
        "ix_curriculum_phases_course_id", "curriculum_phases", ["course_id"]
    )

    # 2. curriculum_tasks
    op.create_table(
        "curriculum_tasks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "phase_id",
            sa.UUID(),
            sa.ForeignKey("curriculum_phases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("skill_tags", JSONB(), nullable=False),
        sa.Column("deliverable", sa.Text(), nullable=True),
        sa.Column("week_label", sa.Text(), nullable=True),
        sa.Column("draft_title", sa.Text(), nullable=True),
        sa.Column("draft_description", sa.Text(), nullable=True),
        sa.Column("draft_skill_tags", JSONB(), nullable=True),
        sa.Column("draft_deliverable", sa.Text(), nullable=True),
        sa.Column("draft_week_label", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "phase_id", "task_no", name="uq_curriculum_tasks_phase_task_no"
        ),
    )
    op.create_index(
        "ix_curriculum_tasks_phase_id", "curriculum_tasks", ["phase_id"]
    )

    # 3. Seed both courses (dict literal -> rows).
    for course_id, phases in _SEED_PAYLOAD:
        for phase in phases:
            phase_id = uuid.uuid4()
            op.execute(
                sa.text(
                    "INSERT INTO curriculum_phases "
                    "(id, course_id, phase_no, title, goal, system_prompt) "
                    "VALUES (:id, :cid, :pn, :t, :g, :sp)"
                ).bindparams(
                    id=phase_id,
                    cid=course_id,
                    pn=phase["phase_no"],
                    t=phase["title"],
                    g=phase["goal"],
                    sp=phase["system_prompt"],
                )
            )
            for task in phase["tasks"]:
                op.execute(
                    sa.text(
                        "INSERT INTO curriculum_tasks "
                        "(id, phase_id, task_no, title, description, "
                        " skill_tags, deliverable, week_label) "
                        "VALUES (:id, :pid, :tn, :t, :d, "
                        "        CAST(:st AS JSONB), :delv, :wl)"
                    ).bindparams(
                        id=uuid.uuid4(),
                        pid=phase_id,
                        tn=task["task_no"],
                        t=task["title"],
                        d=task["description"],
                        st=json.dumps(task["skill_tags"], ensure_ascii=False),
                        delv=task["deliverable"],
                        wl=task["week_label"],
                    )
                )


def downgrade() -> None:
    op.drop_index("ix_curriculum_tasks_phase_id", table_name="curriculum_tasks")
    op.drop_table("curriculum_tasks")
    op.drop_index("ix_curriculum_phases_course_id", table_name="curriculum_phases")
    op.drop_table("curriculum_phases")
