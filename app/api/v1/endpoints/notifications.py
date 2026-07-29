from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AuthenticatedUser, DbSession
from app.repositories.notifications import NotificationRepository
from app.schemas.common import Message
from app.schemas.notifications import NotificationPage, NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/me", response_model=NotificationPage)
async def list_my_notifications(
    current_user: AuthenticatedUser,
    session: DbSession,
    unread_only: bool = False,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> NotificationPage:
    repository = NotificationRepository(session)
    offset = (page - 1) * limit
    notifications = await repository.list_for_user(
        current_user.id,
        unread_only=unread_only,
        offset=offset,
        limit=limit,
    )
    total = await repository.count_for_user(current_user.id, unread_only=unread_only)
    return NotificationPage(
        items=[NotificationRead.model_validate(notification) for notification in notifications],
        page=page,
        limit=limit,
        total=total,
    )


@router.patch("/me/read-all", response_model=Message)
async def mark_all_notifications_read(
    current_user: AuthenticatedUser,
    session: DbSession,
) -> Message:
    count = await NotificationRepository(session).mark_all_read_for_user(current_user.id)
    await session.commit()
    return Message(detail=f"Marked {count} notification(s) as read")


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> NotificationRead:
    repository = NotificationRepository(session)
    notification = await repository.get_for_user(notification_id, current_user.id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification = await repository.update(notification, {"is_read": True})
    await session.commit()
    await session.refresh(notification)
    return NotificationRead.model_validate(notification)
