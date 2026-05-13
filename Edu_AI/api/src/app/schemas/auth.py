from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=6, max_length=100, description="Password")
    role: Optional[str] = Field(default="student", description="Role")


class LoginResponse(BaseModel):
    token: str = Field(..., description="JWT token")
    user: dict = Field(..., description="User info")


class UserInfoResponse(BaseModel):
    username: str
    role: str

