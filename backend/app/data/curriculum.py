"""Backward-compatible shim (Sprint 7).

Sprint 0 had a single CURRICULUM TypedDict mapping. Sprint 7 replaced
it with the courses registry. Existing consumers that import CURRICULUM
/ get_phase / get_task_title / get_task_skill_tags / iter_all_phase_task_pairs
keep working — all four functions delegate to the ai-driven-dev course
via the registry.

NEW CODE: import from `app.data.courses` directly, pass a course slug.

The new `PhaseData` dataclass in `app.data.courses.types` does not carry
the legacy `duration` / `skills` fields (they were only used by the
Sprint 0 curriculum API). The mappings below are retained verbatim so
that `/api/curriculum/phases` and the embedding seed script continue to
produce the original Sprint 0 output.
"""

from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import TypedDict

from app.data.courses import (
    DEFAULT_COURSE_SLUG,
    get_course,
)


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


# Legacy Sprint 0 metadata, preserved verbatim. The new course-registry
# dataclass shape (Sprint 7) does not model these two fields because
# they are AI-driven-dev specific, so we re-attach them here so the
# legacy CURRICULUM mapping is byte-identical to the Sprint 0 version.
_LEGACY_DURATION: dict[int, str] = {
    1: "2〜3週間",
    2: "3〜4週間",
    3: "AI補助コーディング期間",
    4: "4〜6週間",
}

_LEGACY_SKILLS: dict[int, list[str]] = {
    1: [
        "Git / GitHub",
        "VSCode拡張機能",
        "ターミナル操作",
        "REST API基礎",
    ],
    2: [
        "プロンプトエンジニアリング",
        "Cursor IDE",
        "GitHub Copilot",
        "Claude活用",
    ],
    3: [
        "AIペアプログラミング",
        "AIによるコードレビュー",
        "テスト自動生成",
        "仕様書からのコード生成",
    ],
    4: [
        "API連携（Claude / OpenAI）",
        "RAG基礎",
        "PythonでAIツール作成",
        "プロダクト設計",
    ],
}


def _build_legacy_curriculum() -> Mapping[int, PhaseData]:
    course = get_course(DEFAULT_COURSE_SLUG)
    out: dict[int, PhaseData] = {}
    for p in course.phases:
        out[p.phase] = PhaseData(
            title=p.title,
            goal=p.goal,
            duration=_LEGACY_DURATION.get(p.phase, ""),
            skills=list(_LEGACY_SKILLS.get(p.phase, [])),
            tasks=[
                TaskItem(title=t.title, skill_tags=list(t.skill_tags))
                for t in p.tasks
            ],
            system_prompt=p.system_prompt,
        )
    return MappingProxyType(out)


CURRICULUM: Mapping[int, PhaseData] = _build_legacy_curriculum()


def get_phase(phase_no: int) -> PhaseData:
    try:
        return CURRICULUM[phase_no]
    except KeyError:
        valid = sorted(CURRICULUM.keys())
        raise KeyError(
            f"Phase {phase_no} not found. Valid phases: {valid}"
        ) from None


def get_task_title(phase_no: int, task_no: int) -> str:
    tasks = get_phase(phase_no)["tasks"]
    if task_no < 1 or task_no > len(tasks):
        raise KeyError(
            f"task_no {task_no} out of range for phase {phase_no} "
            f"(1..{len(tasks)})"
        )
    return tasks[task_no - 1]["title"]


def get_task_skill_tags(phase_no: int, task_no: int) -> list[str]:
    tasks = get_phase(phase_no)["tasks"]
    if task_no < 1 or task_no > len(tasks):
        raise KeyError(
            f"task_no {task_no} out of range for phase {phase_no} "
            f"(1..{len(tasks)})"
        )
    return list(tasks[task_no - 1]["skill_tags"])


def iter_all_phase_task_pairs() -> Iterator[tuple[int, int]]:
    for phase_no in sorted(CURRICULUM.keys()):
        for i in range(len(CURRICULUM[phase_no]["tasks"])):
            yield phase_no, i + 1
