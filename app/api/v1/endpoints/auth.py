from fastapi import APIRouter, Response, status

from app.api.deps import DbSession
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.users import UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Email already registered"}},
)
async def register(payload: RegisterRequest, session: DbSession) -> UserRead:
    user = await AuthService(session).register(payload)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=TokenPair,
    responses={401: {"description": "Incorrect email or password"}},
)
async def login(payload: LoginRequest, session: DbSession) -> TokenPair:
    return await AuthService(session).login(payload)


@router.post(
    "/refresh",
    response_model=TokenPair,
    responses={401: {"description": "Invalid or revoked refresh token"}},
)
async def refresh(payload: RefreshRequest, session: DbSession) -> TokenPair:
    return await AuthService(session).refresh(payload)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"description": "Invalid refresh token"}},
)
async def logout(payload: LogoutRequest, session: DbSession) -> Response:
    await AuthService(session).logout(payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
