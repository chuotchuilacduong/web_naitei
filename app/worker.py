from typing import ClassVar

from app.core.config import get_settings
from app.services.queue import get_arq_redis_settings, send_assignment_email_job

settings = get_settings()


class WorkerSettings:
    functions: ClassVar = [send_assignment_email_job]
    redis_settings = get_arq_redis_settings(settings)
    queue_name = settings.queue_name
    job_timeout = settings.queue_job_timeout_seconds
    max_tries = settings.email_max_attempts
    health_check_key = f"{settings.queue_name}:health"
