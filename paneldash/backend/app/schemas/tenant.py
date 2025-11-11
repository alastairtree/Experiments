"""Tenant schemas for API requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TenantBase(BaseModel):
    """Base tenant schema with common attributes."""

    tenant_id: str
    name: str


class TenantCreate(TenantBase):
    """Schema for creating a new tenant."""

    database_name: str
    database_host: str
    database_port: int = 5432
    database_user: str
    database_password: str


class TenantUpdate(BaseModel):
    """Schema for updating a tenant."""

    name: str | None = None
    is_active: bool | None = None


class TenantResponse(TenantBase):
    """Schema for tenant responses."""

    id: UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantListResponse(BaseModel):
    """Schema for listing user's accessible tenants."""

    id: UUID
    tenant_id: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}
