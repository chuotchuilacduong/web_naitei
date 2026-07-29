from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import AdminUser, AuthenticatedUser, DbSession
from app.core.security import hash_password, verify_password
from app.repositories.users import UserRepository
from app.schemas.users import ChangePasswordRequest, UserAdminUpdate, UserPage, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_profile(current_user: AuthenticatedUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead)
async def update_profile(
    payload: UserUpdate,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> UserRead:
    data = payload.model_dump(exclude_unset=True)
    user = await UserRepository(session).update(current_user, data)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: AuthenticatedUser,
    session: DbSession,
) -> Response:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
        )
    current_user.hashed_password = hash_password(payload.new_password)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=UserPage)
async def list_users(
    _: AdminUser,
    session: DbSession,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> UserPage:
    repository = UserRepository(session)
    offset = (page - 1) * limit
    users = await repository.list_all(offset=offset, limit=limit)
    total = await repository.count_all()
    return UserPage(
        items=[UserRead.model_validate(user) for user in users],
        page=page,
        limit=limit,
        total=total,
    )


@router.patch("/{user_id}", response_model=UserRead)
async def update_user_as_admin(
    user_id: int,
    payload: UserAdminUpdate,
    admin_user: AdminUser,
    session: DbSession,
) -> UserRead:
    repository = UserRepository(session)
    user = await repository.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    data = payload.model_dump(exclude_unset=True)
    if user.id == admin_user.id and data.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot deactivate their own account",
        )

    user = await repository.update(user, data)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)
