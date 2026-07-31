import logging
from urllib.parse import unquote, urlparse

from arq import Retry, create_pool
from arq.connections import RedisSettings

from app.core.config import Settings, get_settings
from app.services.notifications import send_assignment_email_once

logger = logging.getLogger(__name__)


def get_arq_redis_settings(settings: Settings | None = None) -> RedisSettings:
    settings = settings or get_settings()
    parsed = urlparse(settings.redis_url)
    database = int(parsed.path.removeprefix("/") or "0")
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=database,
        username=unquote(parsed.username) if parsed.username else None,
        password=unquote(parsed.password) if parsed.password else None,
        ssl=parsed.scheme == "rediss",
    )


async def enqueue_assignment_email(recipient_email: str, task_title: str) -> bool:
    settings = get_settings()
    if not settings.queue_enabled or not settings.redis_enabled:
        return False

    redis = None
    try:
        redis = await create_pool(get_arq_redis_settings(settings))
        job = await redis.enqueue_job(
            "send_assignment_email_job",
            recipient_email,
            task_title,
            _queue_name=settings.queue_name,
        )
    except Exception:
        logger.exception("Failed to enqueue assignment email for %s", recipient_email)
        return False
    finally:
        if redis is not None:
            await redis.close(close_connection_pool=True)

    if job is None:
        logger.info("Assignment email job already queued for %s", recipient_email)
    return job is not None


async def send_assignment_email_job(
    ctx: dict[str, object],
    recipient_email: str,
    task_title: str,
) -> None:
    settings = get_settings()
    try:
        await send_assignment_email_once(recipient_email, task_title)
    except Exception as exc:
        raw_job_try = ctx.get("job_try", 1)
        job_try = raw_job_try if isinstance(raw_job_try, int) else 1
        if job_try < settings.email_max_attempts:
            delay = settings.email_retry_delay_seconds * job_try
            logger.warning(
                "Assignment email job attempt %s/%s failed for %s; retrying in %.1fs",
                job_try,
                settings.email_max_attempts,
                recipient_email,
                delay,
            )
            raise Retry(defer=delay) from exc

        logger.exception(
            "Assignment email job failed after %s attempt(s) for %s",
            settings.email_max_attempts,
            recipient_email,
        )
        raise
