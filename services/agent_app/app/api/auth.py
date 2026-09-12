from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.auth import generate_token
from app.db.schema import User
from app.models.auth_models import Token
from app.services.user_service import UserService

from .user import make_user_service

router = APIRouter()


# def make_human_user_service(
#     async_db_session: Annotated[AsyncSession, Depends(get_async_db_session)],
# ) -> UserService:
#     return UserService(async_db_session=async_db_session)


async def authenticate_user(
    human_user_service: Annotated[UserService, Depends(make_user_service)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> User | None:
    return await human_user_service.authenticate_user(
        form_data.username, form_data.password
    )


@router.post("/token")
async def login_for_access_token(
    user: Annotated[User | None, Depends(authenticate_user)],
) -> Token:
    if user:
        return generate_token(user.username)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
