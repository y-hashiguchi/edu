"""arq worker settings — run via `arq app.worker.settings.WorkerSettings`."""

from arq.connections import RedisSettings
from arq.cron import cron

from app.config import settings
from app.worker.grading_job import run_grading_job
from app.worker.scheduled_broadcast_job import run_scheduled_broadcast_cron


def _scheduled_broadcast_cron_jobs() -> list:
    if not settings.scheduled_broadcast_cron_enabled:
        return []
    return [cron(run_scheduled_broadcast_cron, minute=set(range(60)))]


class WorkerSettings:
    functions = [run_grading_job]
    cron_jobs = _scheduled_broadcast_cron_jobs()
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300
