from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import AuthenticatedUser, DbSession
from app.core.security import hash_password, verify_password
from app.repositories.users import UserRepository
from app.schemas.users import ChangePasswordRequest, UserRead, UserUpdate

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
