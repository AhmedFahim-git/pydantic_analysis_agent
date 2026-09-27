from collections.abc import AsyncIterable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.sse import EventSourceResponse
from langfuse import get_client, observe, propagate_attributes
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

langfuse = get_client()


def make_session(
    async_db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> SessionService:
    return SessionService(async_db_session=async_db_session)


async def get_current_user(
    user_service: Annotated[UserService, Depends(make_user_service)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User | None:
    return await user_service.get_current_user(token)


@observe
async def run_with_langfuse(
    user: User, session_id: str, content: str, agent_service: AgentService
) -> ConvItem:
    with propagate_attributes(
        user_id=str(user.user_id),
        session_id=session_id,
        metadata={"username": user.username, "email": user.email},
    ):
        return await agent_service.run_model(
            content,
            deps=SessionDep(
                user_id=user.user_id, username=user.username, session_id=session_id
            ),
        )


@observe
async def stream_with_langfuse(
    user: User, session_id: str, content: str, agent_service: AgentService
) -> AsyncIterable[ConvItem]:
    with propagate_attributes(
        user_id=str(user.user_id),
        session_id=session_id,
        metadata={"username": user.username, "email": user.email},
    ):
        async for message in agent_service.stream_model(
            content,
            deps=SessionDep(
                user_id=user.user_id, username=user.username, session_id=session_id
            ),
        ):
            yield message


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
    output = await run_with_langfuse(
        user=user,
        session_id=session_id,
        content=message_input.content,
        agent_service=agent_service,
    )
    return output


@router.post("/{session_id}/stream", response_class=EventSourceResponse)
async def stream_model(
    session_id: str,
    message_input: ConvItem,
    async_db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
    user: Annotated[User | None, Depends(get_current_user)],
) -> AsyncIterable[ConvItem]:
    assert user
    assert message_input.role == "user"
    assert await SessionService(
        async_db_session=async_db_session
    ).validate_user_session(user.user_id, session_id)
    agent_service = AgentService(
        async_db_session=async_db_session, session_id=session_id
    )
    async for message in stream_with_langfuse(
        user=user,
        session_id=session_id,
        content=message_input.content,
        agent_service=agent_service,
    ):
        yield message


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
