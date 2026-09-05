from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    """Authority officer credentials submission."""
    email: EmailStr = Field(..., description="Official government email address")
    password: str = Field(..., min_length=6, description="Officer security password")


class TokenResponse(BaseModel):
    """JWT bearer authentication token package."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token validity duration in seconds")
    user: UserRead


class LogoutResponse(BaseModel):
    """Logout confirmation response."""
    status: str = "success"
    message: str = "Authority officer successfully logged out"


class CurrentUserResponse(BaseModel):
    """Current authenticated user response."""
    user: UserRead
