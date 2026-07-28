from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import AuthenticatedUser, DbSession
from app.db.models import WorkspaceRole
from app.repositories.users import UserRepository
from app.repositories.workspaces import WorkspaceRepository
from app.schemas.workspaces import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberRead,
    WorkspaceRead,
    WorkspaceUpdate,
)
from app.services.permissions import OWNER_ROLES, PermissionService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceRead])
async def list_workspaces(
    current_user: AuthenticatedUser, session: DbSession
) -> list[WorkspaceRead]:
    workspaces = await WorkspaceRepository(session).list_for_user(current_user)
    return [WorkspaceRead.model_validate(workspace) for workspace in workspaces]


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> WorkspaceRead:
    repository = WorkspaceRepository(session)
    workspace = await repository.create({"name": payload.name, "owner_id": current_user.id})
    await repository.add_member(workspace.id, current_user.id, WorkspaceRole.OWNER)
    await session.commit()
    await session.refresh(workspace)
    return WorkspaceRead.model_validate(workspace)


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace(
    workspace_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> WorkspaceRead:
    permissions = PermissionService(session)
    workspace = await permissions.get_workspace_or_404(workspace_id)
    await permissions.require_workspace_access(workspace_id, current_user)
    return WorkspaceRead.model_validate(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
async def update_workspace(
    workspace_id: int,
    payload: WorkspaceUpdate,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> WorkspaceRead:
    permissions = PermissionService(session)
    workspace = await permissions.get_workspace_or_404(workspace_id)
    await permissions.require_workspace_access(workspace_id, current_user, OWNER_ROLES)
    workspace = await WorkspaceRepository(session).update(
        workspace,
        payload.model_dump(exclude_unset=True),
    )
    await session.commit()
    await session.refresh(workspace)
    return WorkspaceRead.model_validate(workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> Response:
    permissions = PermissionService(session)
    workspace = await permissions.get_workspace_or_404(workspace_id)
    await permissions.require_workspace_access(workspace_id, current_user, OWNER_ROLES)
    await WorkspaceRepository(session).delete(workspace)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberRead])
async def list_members(
    workspace_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> list[WorkspaceMemberRead]:
    permissions = PermissionService(session)
    await permissions.require_workspace_access(workspace_id, current_user)
    members = await WorkspaceRepository(session).list_members(workspace_id)
    return [WorkspaceMemberRead.model_validate(member) for member in members]


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    workspace_id: int,
    payload: WorkspaceMemberCreate,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> WorkspaceMemberRead:
    if payload.role == WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot invite OWNER role"
        )

    permissions = PermissionService(session)
    await permissions.require_workspace_access(workspace_id, current_user, OWNER_ROLES)

    invited_user = await UserRepository(session).get(payload.user_id)
    if invited_user is None or not invited_user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    member = await WorkspaceRepository(session).add_member(
        workspace_id, payload.user_id, payload.role
    )
    await session.commit()
    return WorkspaceMemberRead.model_validate(member)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: int,
    user_id: int,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> Response:
    permissions = PermissionService(session)
    workspace = await permissions.get_workspace_or_404(workspace_id)
    await permissions.require_workspace_access(workspace_id, current_user, OWNER_ROLES)

    if user_id == workspace.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove workspace owner"
        )

    member = await WorkspaceRepository(session).get_member(workspace_id, user_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    await WorkspaceRepository(session).remove_member(member)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
