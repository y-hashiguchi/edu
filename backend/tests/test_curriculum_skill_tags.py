"""Sprint 5: curriculum タスクに skill_tags が付いていることを保証する。

タグ語彙のメンテと TaskItem 構造の維持を兼ねた一枚岩のテスト。タグの個別
意味は実装で説明しない（運用ドキュメント側）。"""

import pytest

from app.data.curriculum import (
    CURRICULUM,
    get_task_skill_tags,
    get_task_title,
    iter_all_phase_task_pairs,
)

EXPECTED_VOCAB = {
    "Git/GitHub", "開発環境", "API基礎", "AI協調", "テスト",
    "コードレビュー", "設計", "RAG/ベクトル検索", "LLM活用", "業務応用",
}


def test_every_task_is_task_item_with_title_and_skill_tags():
    for phase_no, phase in CURRICULUM.items():
        for i, task in enumerate(phase["tasks"]):
            assert isinstance(task, dict), f"phase {phase_no} task {i} not dict"
            assert "title" in task and isinstance(task["title"], str)
            assert "skill_tags" in task and isinstance(task["skill_tags"], list)
            assert len(task["skill_tags"]) >= 1, (
                f"phase {phase_no} task {i+1} has no skill_tags"
            )


def test_skill_tags_use_curated_vocab():
    for phase_no, phase in CURRICULUM.items():
        for i, task in enumerate(phase["tasks"]):
            for tag in task["skill_tags"]:
                assert tag in EXPECTED_VOCAB, (
                    f"phase {phase_no} task {i+1}: unknown tag {tag!r}"
                )


def test_get_task_skill_tags_returns_tags_for_valid_coordinates():
    tags = get_task_skill_tags(1, 1)
    assert isinstance(tags, list)
    assert len(tags) >= 1


def test_get_task_skill_tags_raises_for_invalid_phase():
    with pytest.raises(KeyError):
        get_task_skill_tags(99, 1)


def test_get_task_skill_tags_raises_for_invalid_task_no():
    with pytest.raises(KeyError):
        get_task_skill_tags(1, 99)


def test_get_task_title_returns_string():
    title = get_task_title(1, 1)
    assert isinstance(title, str) and len(title) > 0


def test_iter_all_phase_task_pairs_yields_all_12_tasks():
    pairs = list(iter_all_phase_task_pairs())
    assert len(pairs) == 12
    assert {p for p, _ in pairs} == {1, 2, 3, 4}
    assert all(t >= 1 for _, t in pairs)
