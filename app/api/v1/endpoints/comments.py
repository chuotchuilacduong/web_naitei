from fastapi import APIRouter, Response, status

from app.api.deps import AuthenticatedUser, DbSession
from app.repositories.comments import CommentRepository
from app.schemas.comments import CommentCreate, CommentRead
from app.services.permissions import WRITE_ROLES, PermissionService

router = APIRouter(tags=["comments"])


@router.get("/tasks/{task_id}/comments", response_model=list[CommentRead])
async def list_comments(
    task_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> list[CommentRead]:
    await PermissionService(session).require_task_access(task_id, current_user)
    comments = await CommentRepository(session).list_by_task(task_id)
    return [CommentRead.model_validate(comment) for comment in comments]


@router.post(
    "/tasks/{task_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    task_id: int,
    payload: CommentCreate,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> CommentRead:
    await PermissionService(session).require_task_access(
        task_id,
        current_user,
        WRITE_ROLES,
        allow_assignee=True,
    )
    comment = await CommentRepository(session).create(
        {"task_id": task_id, "author_id": current_user.id, "content": payload.content}
    )
    await session.commit()
    await session.refresh(comment)
    return CommentRead.model_validate(comment)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> Response:
    permissions = PermissionService(session)
    comment = await permissions.get_comment_or_404(comment_id)
    await permissions.require_comment_delete(comment, current_user)
    await CommentRepository(session).delete(comment)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
