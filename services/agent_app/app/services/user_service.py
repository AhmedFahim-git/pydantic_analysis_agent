import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth import (
    DUMMY_HASH,
    decode_token,
    generate_token,
    hash_password,
    verify_password,
)
from app.db.schema import User
from app.models.auth_models import Token
from app.models.user_models import UserCreate


class UserService:
    def __init__(self, async_db_session: AsyncSession):
        self._async_db_session = async_db_session

    async def create_user(self, user_details: UserCreate) -> User | None:
        stmt = select(User).where(User.username == user_details.username)
        prev_user = (await self._async_db_session.scalars(stmt)).first()
        if prev_user:
            return None
        new_user = User(
            username=user_details.username,
            hashed_password=hash_password(user_details.password),
            fullname=user_details.fullname,
            email=user_details.email,
        )
        self._async_db_session.add(new_user)
        await self._async_db_session.commit()
        return new_user

    async def _get_user(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        user = (await self._async_db_session.scalars(stmt)).one_or_none()
        return user

    async def authenticate_user(self, username: str, password: str) -> User | None:
        user = await self._get_user(username)
        if not user:
            verify_password(password, DUMMY_HASH)
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def get_current_user(self, token: str) -> User | None:
        try:
            payload = decode_token(token)
            username = payload.get("sub")
            if username is None:
                return None
        except jwt.InvalidTokenError:
            return None
        assert isinstance(username, str)
        user = await self._get_user(username=username)
        return user

    async def generate_user_token(self, username: str, password: str) -> Token | None:
        user = await self.authenticate_user(username=username, password=password)
        if user:
            return generate_token(username=username)
        return None

    # async def get_human_user_from_user_id(self, user_id: int) -> User | None:
    #     stmt = select(User).where(User.user_id == user_id)
    #     user = (await self._async_db_session.scalars(stmt)).one_or_none()
    #     return user
