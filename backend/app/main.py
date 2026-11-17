from contextlib import asynccontextmanager
from typing import Annotated

import asyncpg
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import get_current_user
from app.api.auth import router as auth_router
from app.core.database import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.disconnect()


app = FastAPI(lifespan=lifespan)

# Allow CORS for eveything for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)


@app.get("/")
async def read_root():
    return {"message": "Hello World"}


@app.get("/health")
async def health(conn: Annotated[asyncpg.Connection, Depends(db.acquire)]):
    await conn.execute("SELECT 1")
    return {"status": "ok"}


# route to test auth
@app.get("/protected/")
async def read_protected(current_user: Annotated[dict, Depends(get_current_user)]):
    return current_user
