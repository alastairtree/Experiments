"""Integration tests for dashboard configuration API endpoints."""

from unittest.mock import MagicMock

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.central import Tenant, User, UserTenant
from app.services.config_loader import ConfigNotFoundError


@pytest.fixture
async def test_user_regular(db_session: AsyncSession) -> User:
    """Create a regular (non-admin) test user."""
    import time

    unique_id = f"dashuser-{int(time.time() * 1000000)}"
    user = User(
        keycloak_id=unique_id,
        email=f"{unique_id}@example.com",
        full_name="Dashboard Test User",
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_admin(db_session: AsyncSession) -> User:
    """Create an admin test user."""
    import time

    unique_id = f"dashuser-admin-{int(time.time() * 1000000)}"
    user = User(
        keycloak_id=unique_id,
        email=f"{unique_id}@example.com",
        full_name="Dashboard Admin User",
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_tenant_dash(db_session: AsyncSession) -> Tenant:
    """Create a test tenant."""
    import time

    unique_id = f"dashtenant-{int(time.time() * 1000000)}"
    tenant = Tenant(
        tenant_id=unique_id,
        name=f"Dashboard Test Tenant {unique_id}",
        database_name=f"test_db_{unique_id}",
        database_host="localhost",
        database_port=5432,
        database_user="test_user",
        database_password="test_pass",
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.mark.asyncio
async def test_list_dashboards_success(
    client: AsyncClient, test_user_regular: User, test_tenant_dash: Tenant, db_session: AsyncSession
) -> None:
    """Test listing dashboards for an accessible tenant."""
    # Grant user access to tenant
    user_tenant = UserTenant(user_id=test_user_regular.id, tenant_id=test_tenant_dash.id)
    db_session.add(user_tenant)
    await db_session.commit()

    # Mock authentication
    from app.auth.dependencies import get_current_active_user
    from app.services.config_loader import get_config_loader

    async def override_get_current_user() -> User:
        return test_user_regular

    # Mock config loader
    mock_loader = MagicMock()
    mock_loader.list_dashboards.return_value = ["default", "monitoring", "analytics"]

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    response = await client.get(
        "/api/v1/dashboards",
        params={"tenant_id": test_tenant_dash.tenant_id},
    )

    # Clean up overrides
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_config_loader, None)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "dashboards" in data
    assert data["dashboards"] == ["default", "monitoring", "analytics"]
    mock_loader.list_dashboards.assert_called_once_with(test_tenant_dash.tenant_id)


@pytest.mark.asyncio
async def test_list_dashboards_tenant_not_found(
    client: AsyncClient, test_user_regular: User
) -> None:
    """Test listing dashboards for non-existent tenant."""
    # Mock authentication
    from app.auth.dependencies import get_current_active_user

    async def override_get_current_user() -> User:
        return test_user_regular

    app.dependency_overrides[get_current_active_user] = override_get_current_user

    response = await client.get(
        "/api/v1/dashboards",
        params={"tenant_id": "nonexistent_tenant"},
    )

    # Clean up override
    app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_dashboards_no_access(
    client: AsyncClient, test_user_regular: User, test_tenant_dash: Tenant
) -> None:
    """Test listing dashboards for tenant user doesn't have access to."""
    # Don't grant access to tenant

    # Mock authentication
    from app.auth.dependencies import get_current_active_user

    async def override_get_current_user() -> User:
        return test_user_regular

    app.dependency_overrides[get_current_active_user] = override_get_current_user

    response = await client.get(
        "/api/v1/dashboards",
        params={"tenant_id": test_tenant_dash.tenant_id},
    )

    # Clean up override
    app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "does not have access" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_dashboards_admin_access(
    client: AsyncClient, test_user_admin: User, test_tenant_dash: Tenant
) -> None:
    """Test admin can list dashboards for any tenant without explicit access."""
    # Mock authentication with admin user
    from app.auth.dependencies import get_current_active_user
    from app.services.config_loader import get_config_loader

    async def override_get_current_user() -> User:
        return test_user_admin

    # Mock config loader
    mock_loader = MagicMock()
    mock_loader.list_dashboards.return_value = ["default"]

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    response = await client.get(
        "/api/v1/dashboards",
        params={"tenant_id": test_tenant_dash.tenant_id},
    )

    # Clean up overrides
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_config_loader, None)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_get_dashboard_success(
    client: AsyncClient, test_user_regular: User, test_tenant_dash: Tenant, db_session: AsyncSession
) -> None:
    """Test getting dashboard configuration."""
    # Grant user access to tenant
    user_tenant = UserTenant(user_id=test_user_regular.id, tenant_id=test_tenant_dash.id)
    db_session.add(user_tenant)
    await db_session.commit()

    # Mock authentication
    from app.auth.dependencies import get_current_active_user
    from app.schemas.config import (
        DashboardConfig,
        DashboardConfigRoot,
        DashboardLayout,
        DashboardPanelReference,
        PanelPosition,
    )
    from app.services.config_loader import get_config_loader

    async def override_get_current_user() -> User:
        return test_user_regular

    # Create real dashboard config object
    dashboard_config = DashboardConfigRoot(
        dashboard=DashboardConfig(
            name="Default Dashboard",
            description="Main operations dashboard",
            refresh_interval=30,
            layout=DashboardLayout(columns=12),
            panels=[
                DashboardPanelReference(
                    id="cpu_usage",
                    config_file="panels/cpu.yaml",
                    position=PanelPosition(row=1, col=1, width=6, height=4)
                )
            ]
        )
    )

    # Mock config loader
    mock_loader = MagicMock()
    mock_loader.load_dashboard_config.return_value = dashboard_config

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    response = await client.get(
        "/api/v1/dashboards/default",
        params={"tenant_id": test_tenant_dash.tenant_id},
    )

    # Clean up overrides
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_config_loader, None)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "Default Dashboard"
    assert data["description"] == "Main operations dashboard"
    assert data["refresh_interval"] == 30
    assert data["layout"] == {"columns": 12}
    assert len(data["panels"]) == 1


@pytest.mark.asyncio
async def test_get_dashboard_not_found(
    client: AsyncClient, test_user_regular: User, test_tenant_dash: Tenant, db_session: AsyncSession
) -> None:
    """Test getting non-existent dashboard."""
    # Grant user access to tenant
    user_tenant = UserTenant(user_id=test_user_regular.id, tenant_id=test_tenant_dash.id)
    db_session.add(user_tenant)
    await db_session.commit()

    # Mock authentication
    from app.auth.dependencies import get_current_active_user
    from app.services.config_loader import get_config_loader

    async def override_get_current_user() -> User:
        return test_user_regular

    # Mock config loader to raise ConfigNotFoundError
    mock_loader = MagicMock()
    mock_loader.load_dashboard_config.side_effect = ConfigNotFoundError(
        "Dashboard not found"
    )

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    response = await client.get(
        "/api/v1/dashboards/nonexistent",
        params={"tenant_id": test_tenant_dash.tenant_id},
    )

    # Clean up overrides
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_config_loader, None)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_get_dashboard_no_layout(
    client: AsyncClient, test_user_regular: User, test_tenant_dash: Tenant, db_session: AsyncSession
) -> None:
    """Test getting dashboard with no layout specified."""
    # Grant user access to tenant
    user_tenant = UserTenant(user_id=test_user_regular.id, tenant_id=test_tenant_dash.id)
    db_session.add(user_tenant)
    await db_session.commit()

    # Mock authentication
    from app.auth.dependencies import get_current_active_user
    from app.schemas.config import DashboardConfig, DashboardConfigRoot
    from app.services.config_loader import get_config_loader

    async def override_get_current_user() -> User:
        return test_user_regular

    # Create real dashboard config without layout
    dashboard_config = DashboardConfigRoot(
        dashboard=DashboardConfig(
            name="Simple Dashboard",
            description=None,
            refresh_interval=60,
            layout=None,  # No layout
            panels=[]
        )
    )

    # Mock config loader
    mock_loader = MagicMock()
    mock_loader.load_dashboard_config.return_value = dashboard_config

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    response = await client.get(
        "/api/v1/dashboards/simple",
        params={"tenant_id": test_tenant_dash.tenant_id},
    )

    # Clean up overrides
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_config_loader, None)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["layout"] is None
    assert data["description"] is None
