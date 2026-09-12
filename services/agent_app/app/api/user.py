from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth import generate_token, oauth2_scheme
from app.db.db_utils import get_async_db_session
from app.db.schema import User
from app.models.auth_models import Token
from app.models.session_models import SessionCreate
from app.models.user_models import UserCreate, UserResponse
from app.services.user_service import UserService

router = APIRouter()


def make_user_service(
    async_db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
) -> UserService:
    return UserService(async_db_session=async_db_session)


async def get_current_user(
    user_service: Annotated[UserService, Depends(make_user_service)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User | None:
    return await user_service.get_current_user(token)


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup_user(
    user_details: UserCreate,
    user_service: Annotated[UserService, Depends(make_user_service)],
) -> Token:
    user = await user_service.create_user(user_details)
    if user:
        return generate_token(user_details.username)
        # return UserResponse(
        #     username=user.username,
        #     sessions=[
        #         SessionCreate(session_id=i.session_id, session_title=i.title)
        #         for i in user.sessions
        #     ],
        #     # user_id=user.user_id,  # TODO: This should be removed
        #     token=generate_token(user.username),
        # )
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists"
        )


@router.get("/details", response_model=UserResponse)
async def get_user_details(
    user: Annotated[User | None, Depends(get_current_user)],
) -> UserResponse:
    if user:
        return UserResponse(
            sessions=[
                SessionCreate(session_id=i.session_id, session_title=i.title)
                for i in await user.awaitable_attrs.sessions
            ]
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
