from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_db
from app.repositories.users import UserRepository

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: DbSession,
) -> User:
    token_payload = decode_token(token, expected_type="access")
    user = await UserRepository(session).get(int(token_payload.sub))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is unavailable",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


AuthenticatedUser = Annotated[User, Depends(get_current_user)]
