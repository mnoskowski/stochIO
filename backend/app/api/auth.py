from datetime import timedelta
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from app.core.config import settings
from app.core.database import db
from app.core.security import (
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.schemas.user import RegisterRequest, User, LoginRequest

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
            detail="User not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username = decode_token(access_token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bad token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_record = await conn.fetchrow(
        "SELECT * FROM users WHERE username = $1", username
    )
    if user_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return User(**dict(user_record))


@router.post("/login", status_code=status.HTTP_200_OK)
async def login_for_token(
    response: Response,
    form_data: LoginRequest,
    conn=Depends(db.acquire),
):
    user = await authenticate_user(form_data.username, form_data.password, conn)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong username or password",
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
    return {"message": "Logged in successfully"}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    response: Response,
    user_data: RegisterRequest,
    conn=Depends(db.acquire),
):

    hashed_password = get_password_hash(user_data.password)

    # Insert the new user
    try:
        user = await conn.fetchrow(
            "INSERT INTO users (username, email, display_name, hashed_password, first_name, last_name) VALUES ($1, $2, $3, $4, $5, $6) RETURNING username",
            user_data.username,
            user_data.email,
            user_data.display_name,
            hashed_password,
            user_data.first_name,
            user_data.last_name,
        )
    except asyncpg.UniqueViolationError as e:
        msg = e.as_dict().get("constraint_name")
        if msg == "users_username_key":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Username already taken")
        if msg == "users_email_key":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Email already registered")

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resource already exists",
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
    return {"message": "Successfully registered"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=User)
async def read_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
@router.get("/me/cookie")
async def get_cookie(access_cookie: str = Cookie(None)):
    pass
