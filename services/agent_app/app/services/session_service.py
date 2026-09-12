from pydantic_ai._uuid import uuid7
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.agents import title_agent
from app.db.schema import Session, User
from app.models.session_models import SessionCreate


class SessionService:
    def __init__(self, async_db_session: AsyncSession):
        self._async_db_session = async_db_session

    async def make_chat_session(self, user_id: int, user_message: str) -> SessionCreate:
        session_title = (await title_agent.run(user_message)).output
        session = Session(session_id=str(uuid7()), user_id=user_id, title=session_title)
        self._async_db_session.add(session)
        await self._async_db_session.commit()
        return SessionCreate(session_id=session.session_id, session_title=session_title)

    async def get_user_from_session_id(self, session_id: str) -> User | None:
        stmt = select(Session).where(Session.session_id == session_id)
        session = (await self._async_db_session.scalars(stmt)).one_or_none()
        user = session.user if session else None
        return user

    async def validate_user_session(self, user_id: int, session_id: str) -> bool:
        stmt = select(Session).where(
            Session.user_id == user_id, Session.session_id == session_id
        )
        session = (await self._async_db_session.scalars(stmt)).one_or_none()
        return session is not None
