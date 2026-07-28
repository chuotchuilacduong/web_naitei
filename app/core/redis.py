import logging
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings

logger = logging.getLogger(__name__)


async def create_redis_client(settings: Settings) -> Redis | None:
    if not settings.redis_enabled:
        return None

    client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:  # pragma: no cover - depends on external Redis.
        logger.warning("Redis unavailable; cache disabled: %s", exc)
        await client.aclose()
        return None
    return client


async def close_redis_client(client: Redis | None) -> None:
    if client is not None:
        await client.aclose()


async def get_json(client: Redis | None, key: str) -> str | None:
    if client is None:
        return None
    value: Any = await client.get(key)
    return value if isinstance(value, str) else None


async def set_json(client: Redis | None, key: str, value: str, ttl_seconds: int) -> None:
    if client is not None:
        await client.set(key, value, ex=ttl_seconds)


async def delete_pattern(client: Redis | None, pattern: str) -> None:
    if client is None:
        return

    keys = [key async for key in client.scan_iter(match=pattern)]
    if keys:
        await client.delete(*keys)
