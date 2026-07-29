from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import TaskPriority, TaskStatus
from app.schemas.common import Pagination, optional_patch_default


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    assignee_id: int | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: str = Field(
        default_factory=optional_patch_default,
        min_length=1,
        max_length=255,
    )
    description: str | None = None
    assignee_id: int | None = None
    status: TaskStatus = Field(default_factory=optional_patch_default)
    priority: TaskPriority = Field(default_factory=optional_patch_default)
    due_date: date | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    assignee_id: int | None
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    created_by: int
    created_at: datetime


class TaskPage(Pagination):
    items: list[TaskRead]
