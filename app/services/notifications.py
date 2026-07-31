import asyncio
import html
import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import Notification, NotificationType, Task, User

logger = logging.getLogger(__name__)
ASSIGNMENT_EMAIL_SUBJECT = "TaskHub task assignment"


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


def build_assignment_email(
    settings: Settings,
    recipient_email: str,
    task_title: str,
) -> EmailMessage:
    safe_task_title = html.escape(task_title, quote=True)
    message = EmailMessage()
    message["Subject"] = ASSIGNMENT_EMAIL_SUBJECT
    message["From"] = settings.smtp_from_email
    message["To"] = recipient_email
    message.set_content(
        "\n".join(
            [
                "Hello,",
                "",
                f'You were assigned to task "{task_title}".',
                "",
                "Open TaskHub to review the task details, update status, or leave a comment.",
            ]
        )
    )
    message.add_alternative(
        "\n".join(
            [
                "<!doctype html>",
                "<html>",
                "<body>",
                "<h1>TaskHub assignment</h1>",
                f"<p>You were assigned to task <strong>{safe_task_title}</strong>.</p>",
                "<p>Open TaskHub to review task details, update status, or leave a comment.</p>",
                "</body>",
                "</html>",
            ]
        ),
        subtype="html",
    )
    return message


async def send_assignment_email_once(recipient_email: str, task_title: str) -> None:
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


async def send_assignment_email_with_retry(recipient_email: str, task_title: str) -> None:
    settings = get_settings()
    for attempt in range(1, settings.email_max_attempts + 1):
        try:
            await send_assignment_email_once(recipient_email, task_title)
            return
        except Exception:
            if attempt >= settings.email_max_attempts:
                logger.exception(
                    "Assignment email failed after %s attempt(s) for %s",
                    settings.email_max_attempts,
                    recipient_email,
                )
                raise
            delay = settings.email_retry_delay_seconds * attempt
            logger.warning(
                "Assignment email attempt %s/%s failed for %s; retrying in %.1fs",
                attempt,
                settings.email_max_attempts,
                recipient_email,
                delay,
            )
            await asyncio.sleep(delay)


def _send_assignment_email_sync(
    settings: Settings,
    smtp_host: str,
    recipient_email: str,
    task_title: str,
) -> None:
    message = build_assignment_email(settings, recipient_email, task_title)
    with smtplib.SMTP(smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


send_assignment_email = send_assignment_email_with_retry
