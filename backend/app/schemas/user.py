import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict, Field


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    badge_id: str
    role: str = Field(..., description="SUPER_ADMIN, CENTRAL_ANALYST, DESIGNATED_OFFICER, FOOD_SAFETY_OFFICER, LEGAL_AUDITOR")
    jurisdiction_state: Optional[str] = None
    jurisdiction_district: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    jurisdiction_state: Optional[str] = None
    jurisdiction_district: Optional[str] = None
    is_active: Optional[bool] = None


class UserRead(UserBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
