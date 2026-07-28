from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Task, TaskPriority, TaskStatus
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Task, session)

    def _filtered_query(
        self,
        project_id: int,
        status: TaskStatus | None,
        priority: TaskPriority | None,
        assignee_id: int | None,
    ) -> Select[tuple[Task]]:
        query = select(Task).where(Task.project_id == project_id)
        if status is not None:
            query = query.where(Task.status == status)
        if priority is not None:
            query = query.where(Task.priority == priority)
        if assignee_id is not None:
            query = query.where(Task.assignee_id == assignee_id)
        return query

    async def list_filtered(
        self,
        project_id: int,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: int | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Task]:
        query = self._filtered_query(project_id, status, priority, assignee_id)
        query = query.order_by(Task.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_filtered(
        self,
        project_id: int,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        assignee_id: int | None = None,
    ) -> int:
        query = self._filtered_query(project_id, status, priority, assignee_id).subquery()
        result = await self.session.execute(select(func.count()).select_from(query))
        return int(result.scalar_one())
