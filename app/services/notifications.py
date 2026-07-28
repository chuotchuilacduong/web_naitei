import logging

logger = logging.getLogger(__name__)


async def send_assignment_email(recipient_email: str, task_title: str) -> None:
    logger.info("Assignment email queued for %s: %s", recipient_email, task_title)
