from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestLoggingMiddleware, configure_logging
from app.core.redis import close_redis_client, create_redis_client

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    app.state.redis = await create_redis_client(settings)
    yield
    await close_redis_client(app.state.redis)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="TaskHub task management API",
    lifespan=lifespan,
)
app.add_middleware(RequestLoggingMiddleware)
register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
