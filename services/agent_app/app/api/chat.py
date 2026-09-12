from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth import oauth2_scheme
from app.db.db_utils import get_async_db_session
from app.db.schema import User
from app.models.agent_models import ConvItem, ConvList, SessionDep
from app.models.session_models import SessionCreate
from app.services.agent_service import AgentService
from app.services.session_service import SessionService
from app.services.user_service import UserService

from .user import make_user_service

router = APIRouter()


def make_session(
    async_db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> SessionService:
    return SessionService(async_db_session=async_db_session)


async def get_current_user(
    user_service: Annotated[UserService, Depends(make_user_service)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User | None:
    return await user_service.get_current_user(token)


@router.post("", response_model=SessionCreate)
async def make_chat_session(
    message_input: ConvItem,
    user: Annotated[User | None, Depends(get_current_user)],
    session_service: Annotated[SessionService, Depends(make_session)],
) -> SessionCreate:
    if user:
        assert message_input.role == "user"
        return await session_service.make_chat_session(
            user.user_id, user_message=message_input.content
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/{session_id}", response_model=ConvItem)
async def run_model(
    session_id: str,
    message_input: ConvItem,
    async_db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
    user: Annotated[User | None, Depends(get_current_user)],
) -> ConvItem:
    assert user
    assert message_input.role == "user"
    assert await SessionService(
        async_db_session=async_db_session
    ).validate_user_session(user.user_id, session_id)
    agent_service = AgentService(
        async_db_session=async_db_session, session_id=session_id
    )
    output = await agent_service.run_model(
        message_input.content,
        deps=SessionDep(
            user_id=user.user_id, username=user.username, session_id=session_id
        ),
    )
    return ConvItem(role="assistant", content=output)


@router.get("/{session_id}/all_messages", response_model=ConvList)
async def get_session_messages(
    session_id: str,
    async_db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
    user: Annotated[User | None, Depends(get_current_user)],
) -> ConvList:
    assert user
    assert await SessionService(
        async_db_session=async_db_session
    ).validate_user_session(user.user_id, session_id)
    agent_service = AgentService(
        async_db_session=async_db_session, session_id=session_id
    )
    return await agent_service.get_conversation_history()
