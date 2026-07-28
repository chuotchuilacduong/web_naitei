from fastapi import APIRouter, Response, status

from app.api.deps import AuthenticatedUser, DbSession
from app.db.models import ProjectStatus
from app.repositories.projects import ProjectRepository
from app.schemas.projects import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.permissions import WRITE_ROLES, PermissionService

router = APIRouter(tags=["projects"])


@router.get("/workspaces/{workspace_id}/projects", response_model=list[ProjectRead])
async def list_projects(
    workspace_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> list[ProjectRead]:
    await PermissionService(session).require_workspace_access(workspace_id, current_user)
    projects = await ProjectRepository(session).list_by_workspace(workspace_id)
    return [ProjectRead.model_validate(project) for project in projects]


@router.post(
    "/workspaces/{workspace_id}/projects",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    workspace_id: int,
    payload: ProjectCreate,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> ProjectRead:
    await PermissionService(session).require_workspace_access(
        workspace_id, current_user, WRITE_ROLES
    )
    project = await ProjectRepository(session).create(
        {
            "workspace_id": workspace_id,
            "name": payload.name,
            "description": payload.description,
            "status": ProjectStatus.ACTIVE,
        }
    )
    await session.commit()
    await session.refresh(project)
    return ProjectRead.model_validate(project)


@router.get("/projects/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> ProjectRead:
    project = await PermissionService(session).require_project_access(project_id, current_user)
    return ProjectRead.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> ProjectRead:
    permissions = PermissionService(session)
    project = await permissions.require_project_access(project_id, current_user, WRITE_ROLES)
    project = await ProjectRepository(session).update(
        project, payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    await session.refresh(project)
    return ProjectRead.model_validate(project)


@router.post("/projects/{project_id}/archive", response_model=ProjectRead)
async def archive_project(
    project_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> ProjectRead:
    permissions = PermissionService(session)
    project = await permissions.require_project_access(project_id, current_user, WRITE_ROLES)
    project = await ProjectRepository(session).update(project, {"status": ProjectStatus.ARCHIVED})
    await session.commit()
    await session.refresh(project)
    return ProjectRead.model_validate(project)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> Response:
    permissions = PermissionService(session)
    project = await permissions.require_project_access(project_id, current_user, WRITE_ROLES)
    await ProjectRepository(session).delete(project)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
