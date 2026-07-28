from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, UserRole, Workspace, WorkspaceMember, WorkspaceRole
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Workspace, session)

    async def list_for_user(self, user: User) -> Sequence[Workspace]:
        query = select(Workspace).order_by(Workspace.created_at.desc())
        if user.role != UserRole.ADMIN:
            query = query.join(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
        result = await self.session.execute(query)
        return result.scalars().unique().all()

    async def get_member(self, workspace_id: int, user_id: int) -> WorkspaceMember | None:
        return await self.session.get(
            WorkspaceMember, {"workspace_id": workspace_id, "user_id": user_id}
        )

    async def list_members(self, workspace_id: int) -> Sequence[WorkspaceMember]:
        result = await self.session.execute(
            select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
        )
        return result.scalars().all()

    async def add_member(
        self,
        workspace_id: int,
        user_id: int,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        member = await self.get_member(workspace_id, user_id)
        if member is None:
            member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
            self.session.add(member)
        else:
            member.role = role
        await self.session.flush()
        return member

    async def remove_member(self, member: WorkspaceMember) -> None:
        await self.session.delete(member)
        await self.session.flush()
