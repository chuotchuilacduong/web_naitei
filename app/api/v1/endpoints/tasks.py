from typing import Any

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response, status

from app.api.deps import AuthenticatedUser, DbSession
from app.db.models import TaskPriority, TaskStatus
from app.repositories.tasks import TaskRepository
from app.repositories.users import UserRepository
from app.schemas.tasks import TaskCreate, TaskPage, TaskRead, TaskUpdate
from app.services.cache import (
    cache_task_page,
    get_cached_task_page,
    invalidate_project_tasks,
    project_tasks_cache_key,
)
from app.services.notifications import send_assignment_email
from app.services.permissions import WRITE_ROLES, PermissionService

router = APIRouter(tags=["tasks"])


@router.get("/projects/{project_id}/tasks", response_model=TaskPage)
async def list_tasks(
    project_id: int,
    request: Request,
    current_user: AuthenticatedUser,
    session: DbSession,
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = None,
    assignee_id: int | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> TaskPage:
    await PermissionService(session).require_project_access(project_id, current_user)
    cache_key = project_tasks_cache_key(project_id, task_status, priority, assignee_id, page, limit)
    redis_client = getattr(request.app.state, "redis", None)
    cached = await get_cached_task_page(redis_client, cache_key)
    if cached is not None:
        return cached

    repository = TaskRepository(session)
    offset = (page - 1) * limit
    tasks = await repository.list_filtered(
        project_id,
        status=task_status,
        priority=priority,
        assignee_id=assignee_id,
        offset=offset,
        limit=limit,
    )
    total = await repository.count_filtered(
        project_id,
        status=task_status,
        priority=priority,
        assignee_id=assignee_id,
    )
    response = TaskPage(
        items=[TaskRead.model_validate(task) for task in tasks],
        page=page,
        limit=limit,
        total=total,
    )
    await cache_task_page(redis_client, cache_key, response)
    return response


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    project_id: int,
    payload: TaskCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> TaskRead:
    permissions = PermissionService(session)
    project = await permissions.require_project_access(project_id, current_user, WRITE_ROLES)
    if payload.assignee_id is not None:
        await permissions.ensure_workspace_member(project.workspace_id, payload.assignee_id)

    task = await TaskRepository(session).create(
        {
            "project_id": project_id,
            "assignee_id": payload.assignee_id,
            "title": payload.title,
            "description": payload.description,
            "status": payload.status,
            "priority": payload.priority,
            "due_date": payload.due_date,
            "created_by": current_user.id,
        }
    )
    await session.commit()
    await session.refresh(task)

    if task.assignee_id is not None:
        assignee = await UserRepository(session).get(task.assignee_id)
        if assignee is not None:
            background_tasks.add_task(send_assignment_email, assignee.email, task.title)

    await invalidate_project_tasks(getattr(request.app.state, "redis", None), project_id)
    return TaskRead.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> TaskRead:
    data: dict[str, Any] = payload.model_dump(exclude_unset=True)
    allow_assignee_status_update = set(data) <= {"status"}
    permissions = PermissionService(session)
    task = await permissions.require_task_access(
        task_id,
        current_user,
        WRITE_ROLES,
        allow_assignee=allow_assignee_status_update,
    )
    project = await permissions.get_project_or_404(task.project_id)

    new_assignee_id = data.get("assignee_id")
    if new_assignee_id is not None:
        await permissions.ensure_workspace_member(project.workspace_id, int(new_assignee_id))

    old_assignee_id = task.assignee_id
    task = await TaskRepository(session).update(task, data)
    await session.commit()
    await session.refresh(task)

    if task.assignee_id is not None and task.assignee_id != old_assignee_id:
        assignee = await UserRepository(session).get(task.assignee_id)
        if assignee is not None:
            background_tasks.add_task(send_assignment_email, assignee.email, task.title)

    await invalidate_project_tasks(getattr(request.app.state, "redis", None), task.project_id)
    return TaskRead.model_validate(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    request: Request,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> Response:
    task = await PermissionService(session).require_task_access(task_id, current_user, WRITE_ROLES)
    project_id = task.project_id
    await TaskRepository(session).delete(task)
    await session.commit()
    await invalidate_project_tasks(getattr(request.app.state, "redis", None), project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
