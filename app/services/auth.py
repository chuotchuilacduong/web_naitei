from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.models import RefreshToken, User, UserRole
from app.repositories.tokens import RefreshTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    async def register(self, payload: RegisterRequest) -> User:
        existing = await self.users.get_by_email(payload.email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
            )

        user = await self.users.create(
            {
                "email": payload.email.lower(),
                "full_name": payload.full_name,
                "hashed_password": hash_password(payload.password),
                "role": UserRole.MEMBER,
                "is_active": True,
            }
        )
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def login(self, payload: LoginRequest) -> TokenPair:
        user = await self.users.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
        return await self._issue_token_pair(user)

    async def refresh(self, payload: RefreshRequest) -> TokenPair:
        token_payload = decode_token(payload.refresh_token, expected_type="refresh")
        stored_token = await self.refresh_tokens.get_active_by_jti(token_payload.jti)
        if stored_token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked"
            )

        user = await self.users.get(int(token_payload.sub))
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User is unavailable"
            )

        await self.refresh_tokens.revoke(stored_token)
        return await self._issue_token_pair(user)

    async def logout(self, refresh_token: str) -> None:
        token_payload = decode_token(refresh_token, expected_type="refresh")
        stored_token = await self.refresh_tokens.get_active_by_jti(token_payload.jti)
        if stored_token is not None:
            await self.refresh_tokens.revoke(stored_token)
            await self.session.commit()

    async def _issue_token_pair(self, user: User) -> TokenPair:
        access_token, _, _ = create_token(
            str(user.id),
            "access",
            timedelta(minutes=self.settings.access_token_expire_minutes),
        )
        refresh_token, refresh_jti, refresh_expires_at = create_token(
            str(user.id),
            "refresh",
            timedelta(days=self.settings.refresh_token_expire_days),
        )
        self.session.add(
            RefreshToken(user_id=user.id, token_jti=refresh_jti, expires_at=refresh_expires_at)
        )
        await self.session.commit()
        await self.session.refresh(user)
        return TokenPair(access_token=access_token, refresh_token=refresh_token, user=user)
