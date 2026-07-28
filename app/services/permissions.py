from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Comment,
    Label,
    Project,
    Task,
    User,
    UserRole,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)
from app.repositories.workspaces import WorkspaceRepository

WRITE_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.EDITOR}
OWNER_ROLES = {WorkspaceRole.OWNER}


class PermissionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workspaces = WorkspaceRepository(session)

    async def get_workspace_or_404(self, workspace_id: int) -> Workspace:
        workspace = await self.session.get(Workspace, workspace_id)
        if workspace is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        return workspace

    async def get_project_or_404(self, project_id: int) -> Project:
        project = await self.session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    async def get_task_or_404(self, task_id: int) -> Task:
        task = await self.session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task

    async def get_label_or_404(self, label_id: int) -> Label:
        label = await self.session.get(Label, label_id)
        if label is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
        return label

    async def get_comment_or_404(self, comment_id: int) -> Comment:
        comment = await self.session.get(Comment, comment_id)
        if comment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
        return comment

    async def require_workspace_access(
        self,
        workspace_id: int,
        user: User,
        allowed_roles: Iterable[WorkspaceRole] | None = None,
    ) -> WorkspaceMember | None:
        await self.get_workspace_or_404(workspace_id)
        if user.role == UserRole.ADMIN:
            return None

        member = await self.workspaces.get_member(workspace_id, user.id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Workspace access denied"
            )

        if allowed_roles is not None and member.role not in set(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient workspace role"
            )
        return member

    async def require_project_access(
        self,
        project_id: int,
        user: User,
        allowed_roles: Iterable[WorkspaceRole] | None = None,
    ) -> Project:
        project = await self.get_project_or_404(project_id)
        await self.require_workspace_access(project.workspace_id, user, allowed_roles)
        return project

    async def require_task_access(
        self,
        task_id: int,
        user: User,
        allowed_roles: Iterable[WorkspaceRole] | None = None,
        *,
        allow_assignee: bool = False,
    ) -> Task:
        task = await self.get_task_or_404(task_id)
        project = await self.get_project_or_404(task.project_id)
        if allow_assignee and task.assignee_id == user.id:
            return task
        await self.require_workspace_access(project.workspace_id, user, allowed_roles)
        return task

    async def require_label_access(
        self,
        label_id: int,
        user: User,
        allowed_roles: Iterable[WorkspaceRole] | None = None,
    ) -> Label:
        label = await self.get_label_or_404(label_id)
        await self.require_project_access(label.project_id, user, allowed_roles)
        return label

    async def ensure_workspace_member(self, workspace_id: int, user_id: int) -> None:
        user = await self.session.get(User, user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        member = await self.workspaces.get_member(workspace_id, user_id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assignee must be a workspace member",
            )

    async def require_comment_delete(self, comment: Comment, user: User) -> None:
        if user.role == UserRole.ADMIN or comment.author_id == user.id:
            return
        task = await self.get_task_or_404(comment.task_id)
        project = await self.get_project_or_404(task.project_id)
        await self.require_workspace_access(project.workspace_id, user, WRITE_ROLES)
