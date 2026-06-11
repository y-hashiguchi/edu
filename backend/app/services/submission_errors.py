"""Submission domain errors."""


class SubmissionPhaseInvalidError(Exception):
    pass


class SubmissionTaskInvalidError(Exception):
    pass


class PhaseNotFoundError(SubmissionPhaseInvalidError):
    def __init__(self, phase: int) -> None:
        super().__init__(phase)
        self.phase = phase


class TaskNotFoundError(SubmissionTaskInvalidError):
    def __init__(self, phase: int, task_no: int) -> None:
        super().__init__(f"task_no {task_no} not found in phase {phase}")
        self.phase = phase
        self.task_no = task_no


class SubmissionNotFoundError(Exception):
    pass


class RegradeCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"cooldown active; retry in {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds
