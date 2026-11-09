from datetime import timedelta, timezone
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from src.core.config import settings
from src.core.database import db
from src.schemas.security_schemas import Token
from src.schemas.user import RegisterRequest, User
from src.security import (
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
router = APIRouter(prefix="/auth", tags=["auth"])


async def authenticate_user(
    username: str, password: str, conn: asyncpg.Connection
) -> User | None:

    user_record = await conn.fetchrow(
        "SELECT * FROM users WHERE username = $1", username
    )
    if user_record is None:
        return None
    if not verify_password(password, user_record["hashed_password"]):
        return None
    return User(**dict(user_record))


async def get_current_user(
    conn: asyncpg.Connection = Depends(db.acquire), access_token: str = Cookie(None)
) -> User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Użytkownik nie jest zalogowany",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username = decode_token(access_token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Niepoprawny token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_record = await conn.fetchrow(
        "SELECT * FROM users WHERE username = $1", username
    )
    if user_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Użytkownik nie znaleziony"
        )
    return User(**dict(user_record))


@router.post("/token", status_code=status.HTTP_200_OK)
async def login_for_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    conn=Depends(db.acquire),
):
    user = await authenticate_user(form_data.username, form_data.password, conn)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Niepoprawne hasło lub login",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expire_delta=access_token_expires
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # HTTPS only in production
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return {"message": "Zalogowano pomyślnie"}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    response: Response,
    user_data: Annotated[RegisterRequest, Depends()],
    conn=Depends(db.acquire),
):
    # Check if user already exists
    existing_user = await conn.fetchrow(
        "SELECT id FROM users WHERE username = $1 OR email = $2",
        user_data.username,
        user_data.email,
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Użytkownik o podanym loginie lub emailu już istnieje",
        )
    hashed_password = get_password_hash(user_data.password)

    # Insert the new user
    user = await conn.fetchrow(
        "INSERT INTO users (username, email, display_name, hashed_password, first_name, last_name) VALUES ($1, $2, $3, $4, $5, $6) RETURNING username",
        user_data.username,
        user_data.email,
        user_data.display_name,
        hashed_password,
        user_data.first_name,
        user_data.last_name,
    )

    access_token = create_access_token(data={"sub": user["username"]})

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # HTTPS only in production
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return {"message": "Zarejestrowano pomyślnie"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Wylogowano"}
