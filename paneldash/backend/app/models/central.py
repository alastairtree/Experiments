"""Central database models for users, tenants, and access control."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """User model - synced from Keycloak or managed internally."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    keycloak_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    tenant_associations: Mapped[list["UserTenant"]] = relationship(
        "UserTenant", back_populates="user", cascade="all, delete-orphan"
    )


class Tenant(Base):
    """Tenant model - represents an isolated organization/team."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    database_host: Mapped[str] = mapped_column(String(255), nullable=False)
    database_port: Mapped[int] = mapped_column(Integer, default=5432, nullable=False)
    database_user: Mapped[str] = mapped_column(String(255), nullable=False)
    database_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user_associations: Mapped[list["UserTenant"]] = relationship(
        "UserTenant", back_populates="tenant", cascade="all, delete-orphan"
    )

    @property
    def database_url(self) -> str:
        """Get the database URL for this tenant."""
        return (
            f"postgresql+asyncpg://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


class UserTenant(Base):
    """User-Tenant mapping - many-to-many relationship."""

    __tablename__ = "user_tenants"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="tenant_associations")
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="user_associations")
