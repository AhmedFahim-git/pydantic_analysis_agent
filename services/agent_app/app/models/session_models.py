from pydantic import BaseModel


class SessionCreate(BaseModel):
    session_id: str
    session_title: str
