from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import NotificationType
from app.schemas.common import Pagination


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    task_id: int | None
    type: NotificationType
    message: str
    is_read: bool
    created_at: datetime


class NotificationPage(Pagination):
    items: list[NotificationRead]
