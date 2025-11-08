"""User schemas for API requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema with common attributes."""

    email: EmailStr
    full_name: str | None = None


class UserCreate(UserBase):
    """Schema for creating a new user."""

    keycloak_id: str
    is_admin: bool = False


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: EmailStr | None = None
    full_name: str | None = None
    is_admin: bool | None = None


class UserResponse(UserBase):
    """Schema for user responses."""

    id: UUID
    keycloak_id: str
    is_admin: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserMeResponse(UserResponse):
    """Schema for /auth/me endpoint response."""

    accessible_tenant_ids: list[UUID] = []
