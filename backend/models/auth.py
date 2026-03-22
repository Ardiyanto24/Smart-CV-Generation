from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MessageResponse(BaseModel):
    message: str