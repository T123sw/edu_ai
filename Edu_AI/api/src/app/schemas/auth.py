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
    display_name: str = ""
    email: str = ""
    phone: str = ""
    department: str = ""
    bio: str = ""
    avatar_url: str = ""
    created_at: str = ""
    password_updated_at: str = ""


class UserProfileUpdateRequest(BaseModel):
    display_name: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=160)
    phone: str = Field(default="", max_length=40)
    department: str = Field(default="", max_length=120)
    bio: str = Field(default="", max_length=600)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=100)
    new_password: str = Field(min_length=8, max_length=100)

