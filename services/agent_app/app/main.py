from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.api import auth, chat, user
from app.auth.auth import hash_password
from app.db.db_utils import (
    dispose_engine,
    init_tables,
    make_init_data,
    make_schemas,
    wait_for_db,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await wait_for_db()
    await init_tables()
    await make_init_data(pswd_hash_func=hash_password)
    await make_schemas()
    yield
    await dispose_engine()


app = FastAPI(lifespan=lifespan)

app.include_router(user.router, prefix="/user")
app.include_router(auth.router, prefix="/auth")
app.include_router(chat.router, prefix="/chat")

uvicorn.run(app, host="0.0.0.0", port=8000)
