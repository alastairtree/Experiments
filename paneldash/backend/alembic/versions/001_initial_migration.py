"""Initial migration: create users, tenants, user_tenants tables

Revision ID: 001
Revises:
Create Date: 2025-01-08 06:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("keycloak_id", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("keycloak_id", name=op.f("uq_users_keycloak_id")),
    )
    op.create_index(op.f("ix_email"), "users", ["email"], unique=False)

    # Create tenants table
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("database_name", sa.String(length=255), nullable=False),
        sa.Column("database_host", sa.String(length=255), nullable=False),
        sa.Column("database_port", sa.Integer(), nullable=False, server_default=sa.text("5432")),
        sa.Column("database_user", sa.String(length=255), nullable=False),
        sa.Column("database_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("tenant_id", name=op.f("uq_tenants_tenant_id")),
    )
    op.create_index(op.f("ix_tenant_id"), "tenants", ["tenant_id"], unique=False)

    # Create user_tenants mapping table
    op.create_table(
        "user_tenants",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_user_tenants_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_tenants_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "tenant_id", name=op.f("pk_user_tenants")),
    )
    op.create_index(
        op.f("ix_user_tenants_user_id"), "user_tenants", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_user_tenants_tenant_id"), "user_tenants", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index(op.f("ix_user_tenants_tenant_id"), table_name="user_tenants")
    op.drop_index(op.f("ix_user_tenants_user_id"), table_name="user_tenants")
    op.drop_table("user_tenants")
    op.drop_index(op.f("ix_tenant_id"), table_name="tenants")
    op.drop_table("tenants")
    op.drop_index(op.f("ix_email"), table_name="users")
    op.drop_table("users")
