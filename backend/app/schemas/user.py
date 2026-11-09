from pydantic import BaseModel, EmailStr

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: EmailStr
    display_name: str
    first_name: str | None = None
    last_name: str | None = None

class User(BaseModel):
    id: int
    username: str
    email: EmailStr
    display_name: str
    disabled: bool
    first_name: str | None = None
    last_name: str | None = None

