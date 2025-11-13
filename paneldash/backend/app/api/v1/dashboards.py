"""API endpoints for dashboard configuration retrieval."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.database import get_central_db
from app.models.central import Tenant, UserTenant
from app.schemas.config import DashboardPanelReference
from app.services.config_loader import (
    ConfigLoader,
    ConfigNotFoundError,
    get_config_loader,
)

router = APIRouter()


class DashboardResponse(BaseModel):
    """Dashboard configuration response."""

    name: str
    description: str | None
    refresh_interval: int
    layout: dict[str, int] | None
    panels: list[DashboardPanelReference]


class DashboardListResponse(BaseModel):
    """Response for listing dashboards."""

    dashboards: list[str]


@router.get("", response_model=DashboardListResponse)
async def list_dashboards(
    tenant_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_central_db)],
    config_loader: ConfigLoader = Depends(get_config_loader),
) -> DashboardListResponse:
    """List all available dashboards for a tenant.

    Args:
        tenant_id: Tenant identifier (string, e.g., "tenant_alpha")
        current_user: Authenticated user
        db: Database session
        config_loader: Configuration loader service

    Returns:
        List of dashboard names

    Raises:
        HTTPException: 403 if user doesn't have access to tenant
        HTTPException: 404 if tenant not found
    """
    # Get tenant by tenant_id string
    result = await db.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id, Tenant.is_active == True)  # noqa: E712
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=404,
            detail=f"Tenant {tenant_id} not found",
        )

    # Check if user has access (admin or assigned to tenant)
    if not current_user.is_admin:
        access_result = await db.execute(
            select(UserTenant).where(
                UserTenant.user_id == current_user.id,
                UserTenant.tenant_id == tenant.id,
            )
        )
        user_tenant = access_result.scalar_one_or_none()

        if not user_tenant:
            raise HTTPException(
                status_code=403,
                detail=f"User does not have access to tenant {tenant_id}",
            )

    dashboards = config_loader.list_dashboards(tenant_id)

    return DashboardListResponse(dashboards=dashboards)


@router.get("/{dashboard_name}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_name: str,
    tenant_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_central_db)],
    config_loader: ConfigLoader = Depends(get_config_loader),
) -> DashboardResponse:
    """Get dashboard configuration for a tenant.

    Args:
        tenant_id: Tenant identifier (string, e.g., "tenant_alpha")
        dashboard_name: Name of the dashboard (default: "default")
        current_user: Authenticated user
        db: Database session
        config_loader: Configuration loader service

    Returns:
        Dashboard configuration with panel metadata

    Raises:
        HTTPException: 403 if user doesn't have access to tenant
        HTTPException: 404 if dashboard not found or tenant not found
    """
    # Get tenant by tenant_id string
    result = await db.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id, Tenant.is_active == True)  # noqa: E712
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=404,
            detail=f"Tenant {tenant_id} not found",
        )

    # Check if user has access (admin or assigned to tenant)
    if not current_user.is_admin:
        access_result = await db.execute(
            select(UserTenant).where(
                UserTenant.user_id == current_user.id,
                UserTenant.tenant_id == tenant.id,
            )
        )
        user_tenant = access_result.scalar_one_or_none()

        if not user_tenant:
            raise HTTPException(
                status_code=403,
                detail=f"User does not have access to tenant {tenant_id}",
            )

    try:
        dashboard_config, panels = config_loader.load_dashboard_with_panels(tenant_id, dashboard_name)
        for panel in dashboard_config.dashboard.panels:
            panel.type = panels[panel.id].type
    except ConfigNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    # Convert layout to dict if present
    layout_dict = None
    if dashboard_config.dashboard.layout:
        layout_dict = {"columns": dashboard_config.dashboard.layout.columns}

    return DashboardResponse(
        name=dashboard_config.dashboard.name,
        description=dashboard_config.dashboard.description,
        refresh_interval=dashboard_config.dashboard.refresh_interval,
        layout=layout_dict,
        panels=dashboard_config.dashboard.panels,
    )
