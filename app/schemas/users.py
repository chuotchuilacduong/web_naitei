from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models import UserRole
from app.schemas.common import Pagination, optional_patch_default


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str = Field(
        default_factory=optional_patch_default,
        min_length=1,
        max_length=255,
    )


class UserAdminUpdate(UserUpdate):
    role: UserRole = Field(default_factory=optional_patch_default)
    is_active: bool = Field(default_factory=optional_patch_default)


class UserPage(Pagination):
    items: list[UserRead]


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
