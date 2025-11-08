"""Tenant management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AdminUser, CurrentUser
from app.database import get_central_db
from app.models.central import Tenant, User, UserTenant
from app.schemas.tenant import TenantCreate, TenantListResponse, TenantResponse

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/", response_model=list[TenantListResponse])
async def list_user_tenants(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_central_db)],
) -> list[TenantListResponse]:
    """
    List all tenants accessible to the current user.

    Returns:
        List of tenants the user has access to
    """
    # Admin users can see all tenants
    if current_user.is_admin:
        result = await db.execute(
            select(Tenant).where(Tenant.is_active == True)  # noqa: E712
        )
        tenants = result.scalars().all()
    else:
        # Regular users only see their assigned tenants
        result = await db.execute(
            select(Tenant)
            .join(UserTenant)
            .where(UserTenant.user_id == current_user.id)
            .where(Tenant.is_active == True)  # noqa: E712
        )
        tenants = result.scalars().all()

    return [
        TenantListResponse(
            id=tenant.id,
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            is_active=tenant.is_active,
        )
        for tenant in tenants
    ]


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_central_db)],
) -> TenantResponse:
    """
    Get tenant details by ID.

    Args:
        tenant_id: Tenant UUID

    Returns:
        Tenant information

    Raises:
        HTTPException: If tenant not found or user doesn't have access
    """
    # Get the tenant
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    # Check if user has access (admin or assigned to tenant)
    if not current_user.is_admin:
        result = await db.execute(
            select(UserTenant).where(
                UserTenant.user_id == current_user.id,
                UserTenant.tenant_id == tenant_id,
            )
        )
        user_tenant = result.scalar_one_or_none()

        if not user_tenant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this tenant is forbidden",
            )

    return TenantResponse(
        id=tenant.id,
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
    )


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_data: TenantCreate,
    admin_user: AdminUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_central_db)],
) -> TenantResponse:
    """
    Create a new tenant (admin only).

    Args:
        tenant_data: Tenant creation data
        admin_user: Current admin user
        db: Database session

    Returns:
        Created tenant

    Raises:
        HTTPException: If tenant_id already exists
    """
    # Check if tenant_id already exists
    result = await db.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_data.tenant_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant with tenant_id '{tenant_data.tenant_id}' already exists",
        )

    # Create new tenant
    tenant = Tenant(
        tenant_id=tenant_data.tenant_id,
        name=tenant_data.name,
        database_name=tenant_data.database_name,
        database_host=tenant_data.database_host,
        database_port=tenant_data.database_port,
        database_user=tenant_data.database_user,
        database_password=tenant_data.database_password,
    )

    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    return TenantResponse(
        id=tenant.id,
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
    )


@router.post("/{tenant_id}/users/{user_id}", status_code=status.HTTP_201_CREATED)
async def assign_user_to_tenant(
    tenant_id: UUID,
    user_id: UUID,
    admin_user: AdminUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_central_db)],
) -> dict[str, str]:
    """
    Assign a user to a tenant (admin only).

    Args:
        tenant_id: Tenant UUID
        user_id: User UUID
        admin_user: Current admin user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If tenant or user not found, or already assigned
    """
    # Verify tenant exists
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )

    # Verify user exists
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check if already assigned
    result = await db.execute(
        select(UserTenant).where(
            UserTenant.user_id == user_id, UserTenant.tenant_id == tenant_id
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already assigned to this tenant",
        )

    # Create assignment
    user_tenant = UserTenant(user_id=user_id, tenant_id=tenant_id)
    db.add(user_tenant)
    await db.commit()

    return {"message": f"User {user_id} assigned to tenant {tenant_id}"}


@router.delete("/{tenant_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_tenant(
    tenant_id: UUID,
    user_id: UUID,
    admin_user: AdminUser,  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_central_db)],
) -> None:
    """
    Remove a user from a tenant (admin only).

    Args:
        tenant_id: Tenant UUID
        user_id: User UUID
        admin_user: Current admin user
        db: Database session

    Raises:
        HTTPException: If assignment not found
    """
    result = await db.execute(
        select(UserTenant).where(
            UserTenant.user_id == user_id, UserTenant.tenant_id == tenant_id
        )
    )
    user_tenant = result.scalar_one_or_none()

    if not user_tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not assigned to this tenant",
        )

    await db.delete(user_tenant)
    await db.commit()
