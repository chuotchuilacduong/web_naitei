import json

from redis.asyncio import Redis

from app.core import redis as redis_helpers
from app.core.config import get_settings
from app.db.models import TaskPriority, TaskStatus
from app.schemas.tasks import TaskPage


def project_tasks_cache_key(
    project_id: int,
    status: TaskStatus | None,
    priority: TaskPriority | None,
    assignee_id: int | None,
    page: int,
    limit: int,
) -> str:
    return (
        f"project:{project_id}:tasks:"
        f"status={status or 'ANY'}:"
        f"priority={priority or 'ANY'}:"
        f"assignee={assignee_id or 'ANY'}:"
        f"page={page}:limit={limit}"
    )


async def get_cached_task_page(client: Redis | None, key: str) -> TaskPage | None:
    raw = await redis_helpers.get_json(client, key)
    if raw is None:
        return None
    return TaskPage.model_validate(json.loads(raw))


async def cache_task_page(client: Redis | None, key: str, page: TaskPage) -> None:
    settings = get_settings()
    await redis_helpers.set_json(
        client,
        key,
        page.model_dump_json(),
        settings.cache_ttl_seconds,
    )


async def invalidate_project_tasks(client: Redis | None, project_id: int) -> None:
    await redis_helpers.delete_pattern(client, f"project:{project_id}:tasks:*")
