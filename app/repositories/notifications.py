from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Notification, session)

    async def list_for_user(
        self,
        user_id: int,
        *,
        unread_only: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Notification]:
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.is_read.is_(False))
        query = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_for_user(self, user_id: int, *, unread_only: bool = False) -> int:
        query = (
            select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        )
        if unread_only:
            query = query.where(Notification.is_read.is_(False))
        result = await self.session.execute(query)
        return int(result.scalar_one())

    async def get_for_user(self, notification_id: int, user_id: int) -> Notification | None:
        result = await self.session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_all_read_for_user(self, user_id: int) -> int:
        result = await self.session.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
        notifications = result.scalars().all()
        for notification in notifications:
            notification.is_read = True
        await self.session.flush()
        return len(notifications)
