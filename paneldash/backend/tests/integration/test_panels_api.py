"""Integration tests for panel data API endpoints."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.central import Tenant, User, UserTenant
from app.schemas.config import PanelType


@pytest.fixture
async def panel_test_user(db_session: AsyncSession) -> User:
    """Create a test user for panel tests."""
    import time

    unique_id = f"paneluser-{int(time.time() * 1000000)}"
    user = User(
        keycloak_id=unique_id,
        email=f"{unique_id}@example.com",
        full_name="Panel Test User",
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def panel_test_tenant(db_session: AsyncSession) -> Tenant:
    """Create a test tenant for panel tests."""
    import time

    unique_id = f"paneltenant-{int(time.time() * 1000000)}"
    tenant = Tenant(
        tenant_id=unique_id,
        name=f"Panel Test Tenant {unique_id}",
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
async def test_get_panel_data_tenant_not_found(
    client: AsyncClient, panel_test_user: User
) -> None:
    """Test getting panel data for non-existent tenant."""
    from app.auth.dependencies import get_current_active_user

    async def override_get_current_user() -> User:
        return panel_test_user

    app.dependency_overrides[get_current_active_user] = override_get_current_user

    response = await client.get(
        "/api/v1/panels/cpu_usage/data",
        params={"tenant_id": "nonexistent_tenant"},
    )

    app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_get_panel_data_no_access(
    client: AsyncClient, panel_test_user: User, panel_test_tenant: Tenant
) -> None:
    """Test getting panel data for tenant user doesn't have access to."""
    from app.auth.dependencies import get_current_active_user

    async def override_get_current_user() -> User:
        return panel_test_user

    app.dependency_overrides[get_current_active_user] = override_get_current_user

    response = await client.get(
        "/api/v1/panels/cpu_usage/data",
        params={"tenant_id": panel_test_tenant.tenant_id},
    )

    app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_get_timeseries_panel_data(
    client: AsyncClient, panel_test_user: User, panel_test_tenant: Tenant, db_session: AsyncSession
) -> None:
    """Test getting time series panel data with aggregation."""
    # Grant access
    user_tenant = UserTenant(user_id=panel_test_user.id, tenant_id=panel_test_tenant.id)
    db_session.add(user_tenant)
    await db_session.commit()

    from app.auth.dependencies import get_current_active_user

    async def override_get_current_user() -> User:
        return panel_test_user

    app.dependency_overrides[get_current_active_user] = override_get_current_user

    with patch("app.api.v1.panels.get_config_loader") as mock_get_loader:
        mock_loader = MagicMock()
        mock_config = MagicMock()
        mock_config.type = PanelType.TIMESERIES
        mock_loader.load_panel_config.return_value = mock_config
        mock_get_loader.return_value = mock_loader

        with (
            patch("app.api.v1.panels.get_query_builder") as mock_get_qb,
            patch("app.api.v1.panels.get_data_aggregator") as mock_get_agg,
        ):
            mock_qb = MagicMock()
            mock_qb.build_time_series_query.return_value = ("SELECT *", {})
            mock_get_qb.return_value = mock_qb

            mock_agg = MagicMock()
            mock_agg.should_aggregate.return_value = True
            mock_agg.get_bucket_interval.return_value = "10 minutes"
            mock_get_agg.return_value = mock_agg

            date_from = datetime.now() - timedelta(days=1)
            date_to = datetime.now()

            response = await client.get(
                "/api/v1/panels/cpu_usage/data",
                params={
                    "tenant_id": panel_test_tenant.tenant_id,
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                },
            )

    app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["panel_type"] == "timeseries"
    assert data["aggregation_info"]["applied"] is True


@pytest.mark.asyncio
async def test_get_kpi_panel_data(
    client: AsyncClient, panel_test_user: User, panel_test_tenant: Tenant, db_session: AsyncSession
) -> None:
    """Test getting KPI panel data."""
    user_tenant = UserTenant(user_id=panel_test_user.id, tenant_id=panel_test_tenant.id)
    db_session.add(user_tenant)
    await db_session.commit()

    from app.auth.dependencies import get_current_active_user

    async def override_get_current_user() -> User:
        return panel_test_user

    app.dependency_overrides[get_current_active_user] = override_get_current_user

    with patch("app.api.v1.panels.get_config_loader") as mock_get_loader:
        mock_loader = MagicMock()
        mock_config = MagicMock()
        mock_config.type = PanelType.KPI
        mock_config.display = MagicMock(unit="%", decimals=1, thresholds=[])
        mock_loader.load_panel_config.return_value = mock_config
        mock_get_loader.return_value = mock_loader

        with patch("app.api.v1.panels.get_query_builder") as mock_get_qb:
            mock_qb = MagicMock()
            mock_qb.build_kpi_query.return_value = ("SELECT AVG(value)", {})
            mock_get_qb.return_value = mock_qb

            response = await client.get(
                "/api/v1/panels/cpu_kpi/data",
                params={"tenant_id": panel_test_tenant.tenant_id},
            )

    app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["panel_type"] == "kpi"
    assert "value" in data["data"]
    assert data["data"]["unit"] == "%"


@pytest.mark.asyncio
async def test_get_health_status_panel_data(
    client: AsyncClient, panel_test_user: User, panel_test_tenant: Tenant, db_session: AsyncSession
) -> None:
    """Test getting health status panel data."""
    user_tenant = UserTenant(user_id=panel_test_user.id, tenant_id=panel_test_tenant.id)
    db_session.add(user_tenant)
    await db_session.commit()

    from app.auth.dependencies import get_current_active_user

    async def override_get_current_user() -> User:
        return panel_test_user

    app.dependency_overrides[get_current_active_user] = override_get_current_user

    with patch("app.api.v1.panels.get_config_loader") as mock_get_loader:
        mock_loader = MagicMock()
        mock_config = MagicMock()
        mock_config.type = PanelType.HEALTH_STATUS
        mock_config.display = MagicMock()
        mock_config.display.status_mapping = {
            0: MagicMock(label="healthy", color="#10B981"),
            1: MagicMock(label="degraded", color="#F59E0B"),
        }
        mock_loader.load_panel_config.return_value = mock_config
        mock_get_loader.return_value = mock_loader

        with patch("app.api.v1.panels.get_query_builder") as mock_get_qb:
            mock_qb = MagicMock()
            mock_qb.build_health_status_query.return_value = ("SELECT *", {})
            mock_get_qb.return_value = mock_qb

            response = await client.get(
                "/api/v1/panels/system_health/data",
                params={"tenant_id": panel_test_tenant.tenant_id},
            )

    app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["panel_type"] == "health_status"
    assert "services" in data["data"]


@pytest.mark.asyncio
async def test_get_table_panel_data(
    client: AsyncClient, panel_test_user: User, panel_test_tenant: Tenant, db_session: AsyncSession
) -> None:
    """Test getting table panel data with pagination."""
    user_tenant = UserTenant(user_id=panel_test_user.id, tenant_id=panel_test_tenant.id)
    db_session.add(user_tenant)
    await db_session.commit()

    from app.auth.dependencies import get_current_active_user

    async def override_get_current_user() -> User:
        return panel_test_user

    app.dependency_overrides[get_current_active_user] = override_get_current_user

    with patch("app.api.v1.panels.get_config_loader") as mock_get_loader:
        mock_loader = MagicMock()
        mock_config = MagicMock()
        mock_config.type = PanelType.TABLE
        mock_config.display = MagicMock(pagination=25, default_sort="timestamp")
        mock_config.data_source = MagicMock()
        mock_config.data_source.columns = [
            MagicMock(name="timestamp", display="Time", format="datetime"),
        ]
        mock_loader.load_panel_config.return_value = mock_config
        mock_get_loader.return_value = mock_loader

        with patch("app.api.v1.panels.get_query_builder") as mock_get_qb:
            mock_qb = MagicMock()
            mock_qb.build_table_query.return_value = ("SELECT *", {})
            mock_get_qb.return_value = mock_qb

            response = await client.get(
                "/api/v1/panels/error_logs/data",
                params={
                    "tenant_id": panel_test_tenant.tenant_id,
                    "sort_column": "timestamp",
                    "sort_order": "desc",
                    "page": 1,
                },
            )

    app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["panel_type"] == "table"
    assert "pagination" in data["data"]
    assert data["data"]["pagination"]["page_size"] == 25
