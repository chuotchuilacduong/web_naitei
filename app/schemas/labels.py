from pydantic import BaseModel, ConfigDict, Field


class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class LabelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class LabelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    color: str
