import asyncio
import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import Notification, NotificationType, Task, User

logger = logging.getLogger(__name__)


async def create_assignment_notification(
    session: AsyncSession,
    assignee: User,
    task: Task,
) -> Notification:
    notification = Notification(
        user_id=assignee.id,
        task_id=task.id,
        type=NotificationType.TASK_ASSIGNED,
        message=f'You were assigned to task "{task.title}".',
        is_read=False,
    )
    session.add(notification)
    await session.flush()
    await session.refresh(notification)
    return notification


async def send_assignment_email(recipient_email: str, task_title: str) -> None:
    settings = get_settings()
    if not settings.email_enabled or settings.smtp_host is None:
        logger.info("Assignment email queued for %s: %s", recipient_email, task_title)
        return

    await asyncio.to_thread(
        _send_assignment_email_sync,
        settings,
        settings.smtp_host,
        recipient_email,
        task_title,
    )


def _send_assignment_email_sync(
    settings: Settings,
    smtp_host: str,
    recipient_email: str,
    task_title: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = "TaskHub task assignment"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient_email
    message.set_content(f'You were assigned to task "{task_title}".')

    with smtplib.SMTP(smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
