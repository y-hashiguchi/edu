import pytest

from app.data.curriculum import CURRICULUM, get_phase


def test_curriculum_has_four_phases():
    assert sorted(CURRICULUM.keys()) == [1, 2, 3, 4]


def test_each_phase_has_required_fields():
    required = {"title", "goal", "duration", "skills", "tasks", "system_prompt"}
    for phase_no, phase in CURRICULUM.items():
        missing = required - set(phase.keys())
        assert not missing, f"Phase {phase_no} missing fields: {missing}"


def test_each_phase_has_at_least_three_tasks():
    for phase_no, phase in CURRICULUM.items():
        assert len(phase["tasks"]) >= 3, f"Phase {phase_no} has fewer than 3 tasks"


def test_system_prompt_mentions_phase_label():
    for phase_no, phase in CURRICULUM.items():
        assert f"Phase{phase_no}" in phase["system_prompt"]
        assert phase["title"] in phase["system_prompt"], (
            f"Phase {phase_no} system_prompt does not reference its own title"
        )


def test_get_phase_returns_data_for_valid_id():
    phase = get_phase(1)
    assert phase["title"].startswith("開発環境")


def test_get_phase_raises_for_invalid_id():
    with pytest.raises(KeyError):
        get_phase(99)
