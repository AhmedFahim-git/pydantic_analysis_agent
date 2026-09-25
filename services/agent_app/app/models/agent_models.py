from dataclasses import dataclass
from typing import Literal

from k8s_agent_sandbox.async_sandbox import AsyncSandbox
from pydantic import BaseModel


@dataclass
class SessionDep:
    user_id: int
    username: str
    session_id: str


@dataclass
class SQLQueryDep:
    user_id: int
    table_names: list[str]


@dataclass
class SandboxDep:
    # client: AsyncSandboxClient
    sandbox: AsyncSandbox
    # claim_name: str = ""


class ConvItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ConvList(BaseModel):
    message_list: list[ConvItem]


# class MessageItem(BaseModel):
#     message: str
