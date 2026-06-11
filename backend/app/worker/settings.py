"""arq worker settings — run via `arq app.worker.settings.WorkerSettings`."""

from arq.connections import RedisSettings

from app.config import settings
from app.worker.grading_job import run_grading_job


class WorkerSettings:
    functions = [run_grading_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300
