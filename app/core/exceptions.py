from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError


class AppError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        return await unhandled_error_handler(_, exc)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def integrity_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, IntegrityError):
        return await unhandled_error_handler(_, exc)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Resource conflict or duplicate value"},
    )


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)


ASGIHandler = Callable[[Request], Awaitable[Response]]
