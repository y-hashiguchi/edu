"""4フェーズのカリキュラム定義（Sprint 0 single source of truth）。

Immutability contract:
- The top-level CURRICULUM mapping is wrapped in MappingProxyType, so
  ``CURRICULUM[5] = ...`` raises TypeError.
- Inner PhaseData dicts and the lists they contain (skills, tasks) are
  NOT wrapped. Callers MUST treat them as read-only. Mutation will
  silently corrupt curriculum state for the rest of the process.
- A deep-immutable refactor (frozen dataclass + tuple fields) is
  deferred to a future sprint to avoid breaking dict-style access
  used by API handlers (Task 7, Task 8).
"""

from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import TypedDict


class TaskItem(TypedDict):
    title: str
    skill_tags: list[str]


class PhaseData(TypedDict):
    title: str
    goal: str
    duration: str
    skills: list[str]
    tasks: list[TaskItem]
    system_prompt: str


CURRICULUM: Mapping[int, PhaseData] = MappingProxyType({
    1: {
        "title": "開発環境の近代化",
        "goal": "AIツールを使いこなすための「土台」を固める",
        "duration": "2〜3週間",
        "skills": [
            "Git / GitHub",
            "VSCode拡張機能",
            "ターミナル操作",
            "REST API基礎",
        ],
        "tasks": [
            {"title": "Gitでブランチを切り、PythonスクリプトをプッシュしてPRを作成", "skill_tags": ["Git/GitHub"]},
            {"title": "VSCode拡張（GitLens・REST Client・GitHub Copilot）の導入と動作確認", "skill_tags": ["開発環境"]},
            {"title": "curlでREST APIを叩き、JSONレスポンス構造をまとめる", "skill_tags": ["API基礎"]},
        ],
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
    },
    2: {
        "title": "AIツール活用マスター",
        "goal": "「AIと一緒にコードを書く」体験を積む",
        "duration": "3〜4週間",
        "skills": [
            "プロンプトエンジニアリング",
            "Cursor IDE",
            "GitHub Copilot",
            "Claude活用",
        ],
        "tasks": [
            {"title": "Cursor IDEで顧客管理API（CRUD）をゼロから作成。AIとのやり取りログを記録", "skill_tags": ["AI協調", "API基礎"]},
            {"title": "同機能をGitHub Copilotでも実装し、2つのAIの違いをまとめる", "skill_tags": ["AI協調", "開発環境"]},
            {"title": "ClaudeにコードレビューさせてPDCA", "skill_tags": ["AI協調", "コードレビュー"]},
        ],
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
    },
    3: {
        "title": "AI協調型開発ワークフロー",
        "goal": "実際の開発タスクにAIを組み込む",
        "duration": "AI補助コーディング期間",
        "skills": [
            "AIペアプログラミング",
            "AIによるコードレビュー",
            "テスト自動生成",
            "仕様書からのコード生成",
        ],
        "tasks": [
            {"title": "Phase2で作ったAPIをAIにレビューさせ、セキュリティ・パフォーマンス・可読性の観点で整理", "skill_tags": ["コードレビュー", "AI協調"]},
            {"title": "仕様書（箇条書き）からテストコードを自動生成し、不足ケースを3つ指摘", "skill_tags": ["テスト", "AI協調"]},
            {"title": "AIとペアで新機能（検索機能など）を実装。会話ログも提出", "skill_tags": ["AI協調", "設計"]},
        ],
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
    },
    4: {
        "title": "AIアプリ開発実践",
        "goal": "「AIを使う」から「AIを組み込む」へ",
        "duration": "4〜6週間",
        "skills": [
            "API連携（Claude / OpenAI）",
            "RAG基礎",
            "PythonでAIツール作成",
            "プロダクト設計",
        ],
        "tasks": [
            {"title": "Claude APIでチャットボット作成（会話履歴保持・システムプロンプト設定）", "skill_tags": ["LLM活用"]},
            {"title": "RAGデモ作成（Python + ChromaDB + Claude API）", "skill_tags": ["RAG/ベクトル検索", "LLM活用"]},
            {"title": "業務課題を解決するAIツールの企画書作成（課題・解決策・技術構成・効果試算）", "skill_tags": ["業務応用", "設計"]},
        ],
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
    },
})


def get_phase(phase_no: int) -> PhaseData:
    """Return phase data for phase_no.

    Raises:
        KeyError: with a descriptive message including valid phase numbers
            if phase_no is not in CURRICULUM.
    """
    try:
        return CURRICULUM[phase_no]
    except KeyError:
        valid = sorted(CURRICULUM.keys())
        raise KeyError(
            f"Phase {phase_no} not found. Valid phases: {valid}"
        ) from None


def get_task_title(phase_no: int, task_no: int) -> str:
    """Return the human-readable title for (phase, task_no).

    task_no is 1-indexed (matches `submissions.task_no`). KeyError on
    out-of-range coordinates so callers see a uniform failure mode.
    """
    tasks = get_phase(phase_no)["tasks"]
    if task_no < 1 or task_no > len(tasks):
        raise KeyError(
            f"task_no {task_no} out of range for phase {phase_no} "
            f"(1..{len(tasks)})"
        )
    return tasks[task_no - 1]["title"]


def get_task_skill_tags(phase_no: int, task_no: int) -> list[str]:
    """Return the skill tags for (phase, task_no). Same indexing rules
    as get_task_title."""
    tasks = get_phase(phase_no)["tasks"]
    if task_no < 1 or task_no > len(tasks):
        raise KeyError(
            f"task_no {task_no} out of range for phase {phase_no} "
            f"(1..{len(tasks)})"
        )
    return list(tasks[task_no - 1]["skill_tags"])  # defensive copy


def iter_all_phase_task_pairs() -> Iterator[tuple[int, int]]:
    """Yield every (phase, task_no) coordinate in stable phase-then-
    task_no order. Used by the recommendation service to enumerate the
    universe of curriculum tasks for the "unsubmitted" filter."""
    for phase_no in sorted(CURRICULUM.keys()):
        for i in range(len(CURRICULUM[phase_no]["tasks"])):
            yield phase_no, i + 1
