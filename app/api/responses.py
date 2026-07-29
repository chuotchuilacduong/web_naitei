from typing import Any

from app.schemas.common import Message

COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": Message, "description": "Bad request"},
    401: {"model": Message, "description": "Missing, invalid, or expired bearer token"},
    403: {
        "model": Message,
        "description": "Authenticated user is not allowed to perform this action",
    },
    404: {"model": Message, "description": "Resource not found"},
    409: {"model": Message, "description": "Resource conflict or duplicate value"},
    422: {"description": "Validation error"},
}
