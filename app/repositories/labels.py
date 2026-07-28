from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Label
from app.repositories.base import BaseRepository


class LabelRepository(BaseRepository[Label]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Label, session)

    async def list_by_project(self, project_id: int) -> Sequence[Label]:
        result = await self.session.execute(
            select(Label).where(Label.project_id == project_id).order_by(Label.name.asc())
        )
        return result.scalars().all()
