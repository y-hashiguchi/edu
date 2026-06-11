"""Phase/task validation shared by submission write paths."""

from app.data.courses import get_course
from app.services.submission_errors import PhaseNotFoundError, TaskNotFoundError


def validate_phase_and_task(course_slug: str, phase: int, task_no: int) -> str:
    try:
        phase_def = next(
            p for p in get_course(course_slug).phases if p.phase == phase
        )
    except StopIteration:
        raise PhaseNotFoundError(phase) from None
    if task_no < 1 or task_no > len(phase_def.tasks):
        raise TaskNotFoundError(phase, task_no)
    return phase_def.tasks[task_no - 1].title
