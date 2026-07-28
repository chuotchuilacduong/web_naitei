from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import delete, insert, select

from app.api.deps import AuthenticatedUser, DbSession
from app.db.models import task_labels
from app.repositories.labels import LabelRepository
from app.schemas.common import Message
from app.schemas.labels import LabelCreate, LabelRead, LabelUpdate
from app.services.cache import invalidate_project_tasks
from app.services.permissions import WRITE_ROLES, PermissionService

router = APIRouter(tags=["labels"])


@router.get("/projects/{project_id}/labels", response_model=list[LabelRead])
async def list_labels(
    project_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> list[LabelRead]:
    await PermissionService(session).require_project_access(project_id, current_user)
    labels = await LabelRepository(session).list_by_project(project_id)
    return [LabelRead.model_validate(label) for label in labels]


@router.post(
    "/projects/{project_id}/labels",
    response_model=LabelRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_label(
    project_id: int,
    payload: LabelCreate,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> LabelRead:
    await PermissionService(session).require_project_access(project_id, current_user, WRITE_ROLES)
    label = await LabelRepository(session).create(
        {"project_id": project_id, "name": payload.name, "color": payload.color}
    )
    await session.commit()
    await session.refresh(label)
    return LabelRead.model_validate(label)


@router.patch("/labels/{label_id}", response_model=LabelRead)
async def update_label(
    label_id: int,
    payload: LabelUpdate,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> LabelRead:
    label = await PermissionService(session).require_label_access(
        label_id, current_user, WRITE_ROLES
    )
    label = await LabelRepository(session).update(label, payload.model_dump(exclude_unset=True))
    await session.commit()
    await session.refresh(label)
    return LabelRead.model_validate(label)


@router.delete("/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_label(
    label_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> Response:
    label = await PermissionService(session).require_label_access(
        label_id, current_user, WRITE_ROLES
    )
    await LabelRepository(session).delete(label)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tasks/{task_id}/labels/{label_id}", response_model=Message)
async def attach_label(
    task_id: int,
    label_id: int,
    request: Request,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> Message:
    permissions = PermissionService(session)
    task = await permissions.require_task_access(task_id, current_user, WRITE_ROLES)
    label = await permissions.require_label_access(label_id, current_user, WRITE_ROLES)
    if label.project_id != task.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label must belong to the same project as task",
        )

    existing = await session.execute(
        select(task_labels).where(
            task_labels.c.task_id == task_id,
            task_labels.c.label_id == label_id,
        )
    )
    if existing.first() is None:
        await session.execute(insert(task_labels).values(task_id=task_id, label_id=label_id))
        await session.commit()
        await invalidate_project_tasks(getattr(request.app.state, "redis", None), task.project_id)
    return Message(detail="Label attached")


@router.delete("/tasks/{task_id}/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_label(
    task_id: int,
    label_id: int,
    request: Request,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> Response:
    permissions = PermissionService(session)
    task = await permissions.require_task_access(task_id, current_user, WRITE_ROLES)
    label = await permissions.require_label_access(label_id, current_user, WRITE_ROLES)
    if label.project_id != task.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label must belong to the same project as task",
        )

    await session.execute(
        delete(task_labels).where(
            task_labels.c.task_id == task_id,
            task_labels.c.label_id == label_id,
        )
    )
    await session.commit()
    await invalidate_project_tasks(getattr(request.app.state, "redis", None), task.project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
