"""ai-driven-dev course definition (Sprint 7 — moved from curriculum.py).

The content is the literal Sprint 0 curriculum used in Sprint 4-6.
Migrating it to the frozen-dataclass shape is purely structural — no
text changes. The 4-phase shape is preserved; downstream consumers
must access via the registry, not by importing CURRICULUM."""

import uuid

from app.data.courses.types import CourseData, PhaseData, TaskItem

AI_DRIVEN_DEV_COURSE = CourseData(
    id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
    slug="ai-driven-dev",
    title="AI駆動型開発 補足カリキュラム",
    description="既存 Java/Python 経験者向けの AI 駆動型開発習得カリキュラム",
    sort_order=0,
    phases=(
        PhaseData(
            phase=1,
            title="開発環境の近代化",
            goal="AIツールを使いこなすための「土台」を固める",
            tasks=(
                TaskItem(
                    task_no=1,
                    title="Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成",
                    description="Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成",
                    skill_tags=("Git/GitHub",),
                ),
                TaskItem(
                    task_no=2,
                    title="VSCode拡張（GitLens・REST Client・GitHub Copilot）の導入と動作確認",
                    description=(
                        "VSCode拡張（GitLens・REST Client・GitHub Copilot）の"
                        "導入と動作確認"
                    ),
                    skill_tags=("開発環境",),
                ),
                TaskItem(
                    task_no=3,
                    title="curlでREST APIを叩き、JSONレスポンス構造をまとめる",
                    description="curlでREST APIを叩き、JSONレスポンス構造をまとめる",
                    skill_tags=("API基礎",),
                ),
            ),
            system_prompt=(
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
        ),
        PhaseData(
            phase=2,
            title="AIツール活用マスター",
            goal="「AIと一緒にコードを書く」体験を積む",
            tasks=(
                TaskItem(
                    task_no=1,
                    title="Cursor IDEで顧客管理API（CRUD）をゼロから作成。AIとのやり取りログを記録",
                    description=(
                        "Cursor IDEで顧客管理API（CRUD）をゼロから作成。"
                        "AIとのやり取りログを記録"
                    ),
                    skill_tags=("AI協調", "API基礎"),
                ),
                TaskItem(
                    task_no=2,
                    title="同機能をGitHub Copilotでも実装し、2つのAIの違いをまとめる",
                    description="同機能をGitHub Copilotでも実装し、2つのAIの違いをまとめる",
                    skill_tags=("AI協調", "開発環境"),
                ),
                TaskItem(
                    task_no=3,
                    title="ClaudeにコードレビューさせてPDCA",
                    description="ClaudeにコードレビューさせてPDCA",
                    skill_tags=("AI協調", "コードレビュー"),
                ),
            ),
            system_prompt=(
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
        ),
        PhaseData(
            phase=3,
            title="AI協調型開発ワークフロー",
            goal="実際の開発タスクにAIを組み込む",
            tasks=(
                TaskItem(
                    task_no=1,
                    title="Phase2で作ったAPIをAIにレビューさせ、セキュリティ・パフォーマンス・可読性の観点で整理",
                    description="Phase2で作ったAPIをAIにレビューさせ、セキュリティ・パフォーマンス・可読性の観点で整理",
                    skill_tags=("コードレビュー", "AI協調"),
                ),
                TaskItem(
                    task_no=2,
                    title="仕様書（箇条書き）からテストコードを自動生成し、不足ケースを3つ指摘",
                    description="仕様書（箇条書き）からテストコードを自動生成し、不足ケースを3つ指摘",
                    skill_tags=("テスト", "AI協調"),
                ),
                TaskItem(
                    task_no=3,
                    title="AIとペアで新機能（検索機能など）を実装。会話ログも提出",
                    description="AIとペアで新機能（検索機能など）を実装。会話ログも提出",
                    skill_tags=("AI協調", "設計"),
                ),
            ),
            system_prompt=(
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
        ),
        PhaseData(
            phase=4,
            title="AIアプリ開発実践",
            goal="「AIを使う」から「AIを組み込む」へ",
            tasks=(
                TaskItem(
                    task_no=1,
                    title="Claude APIでチャットボット作成（会話履歴保持・システムプロンプト設定）",
                    description=(
                        "Claude APIでチャットボット作成"
                        "（会話履歴保持・システムプロンプト設定）"
                    ),
                    skill_tags=("LLM活用",),
                ),
                TaskItem(
                    task_no=2,
                    title="RAGデモ作成（Python + ChromaDB + Claude API）",
                    description="RAGデモ作成（Python + ChromaDB + Claude API）",
                    skill_tags=("RAG/ベクトル検索", "LLM活用"),
                ),
                TaskItem(
                    task_no=3,
                    title="業務課題を解決するAIツールの企画書作成（課題・解決策・技術構成・効果試算）",
                    description="業務課題を解決するAIツールの企画書作成（課題・解決策・技術構成・効果試算）",
                    skill_tags=("業務応用", "設計"),
                ),
            ),
            system_prompt=(
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
        ),
    ),
)
