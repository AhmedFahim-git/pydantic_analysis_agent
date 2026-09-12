from pydantic import BaseModel

from .session_models import SessionCreate


class UserCreate(BaseModel):
    username: str
    password: str
    fullname: str
    email: str


class UserResponse(BaseModel):
    # username: str
    # user_id: int
    # token: Token
    sessions: list[SessionCreate]
