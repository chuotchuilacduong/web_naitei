from pydantic import BaseModel, Field


class Message(BaseModel):
    detail: str


class Pagination(BaseModel):
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
