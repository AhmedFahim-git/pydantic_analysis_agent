from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


@dataclass
class SessionDep:
    user_id: int
    username: str
    session_id: str


@dataclass
class SQLQueryModel:
    user_id: int
    table_names: list[str]


class ConvItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ConvList(BaseModel):
    message_list: list[ConvItem]


# class MessageItem(BaseModel):
#     message: str
