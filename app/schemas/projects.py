from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import ProjectStatus
from app.schemas.common import optional_patch_default


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str = Field(
        default_factory=optional_patch_default,
        min_length=1,
        max_length=255,
    )
    description: str | None = None
    status: ProjectStatus = Field(default_factory=optional_patch_default)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    description: str | None
    status: ProjectStatus
    created_at: datetime
