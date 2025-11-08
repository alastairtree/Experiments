"""Integration tests for panel data API endpoints."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

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
    from app.services.config_loader import get_config_loader
    from app.services.query_builder import get_query_builder
    from app.services.data_aggregator import get_data_aggregator
    from app.schemas.config import TimeSeriesPanelConfig, TimeSeriesDataSource

    async def override_get_current_user() -> User:
        return panel_test_user

    # Create real time series config object
    time_series_config = TimeSeriesPanelConfig(
        title="CPU Usage",
        data_source=TimeSeriesDataSource(
            table="metrics",
            columns={"timestamp": "recorded_at", "value": "cpu_percent"}
        )
    )

    # Mock config loader
    mock_loader = MagicMock()
    mock_loader.load_panel_config.return_value = time_series_config

    def override_get_config_loader():
        return mock_loader

    # Mock query builder
    mock_qb = MagicMock()
    mock_qb.build_time_series_query.return_value = ("SELECT *", {})

    def override_get_query_builder():
        return mock_qb

    # Mock data aggregator
    mock_agg = MagicMock()
    mock_agg.should_aggregate.return_value = True
    mock_agg.get_bucket_interval.return_value = "10 minutes"

    def override_get_data_aggregator():
        return mock_agg

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader
    app.dependency_overrides[get_query_builder] = override_get_query_builder
    app.dependency_overrides[get_data_aggregator] = override_get_data_aggregator

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

    # Clean up overrides
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_config_loader, None)
    app.dependency_overrides.pop(get_query_builder, None)
    app.dependency_overrides.pop(get_data_aggregator, None)

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
    from app.services.config_loader import get_config_loader
    from app.services.query_builder import get_query_builder
    from app.schemas.config import KPIPanelConfig, KPIDataSource, KPIDisplay

    async def override_get_current_user() -> User:
        return panel_test_user

    # Create real KPI config object
    kpi_config = KPIPanelConfig(
        title="CPU KPI",
        data_source=KPIDataSource(
            table="metrics",
            columns={"value": "cpu_percent"}
        ),
        display=KPIDisplay(unit="%", decimals=1, thresholds=[])
    )

    # Mock config loader
    mock_loader = MagicMock()
    mock_loader.load_panel_config.return_value = kpi_config

    def override_get_config_loader():
        return mock_loader

    # Mock query builder
    mock_qb = MagicMock()
    mock_qb.build_kpi_query.return_value = ("SELECT AVG(value)", {})

    def override_get_query_builder():
        return mock_qb

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader
    app.dependency_overrides[get_query_builder] = override_get_query_builder

    response = await client.get(
        "/api/v1/panels/cpu_kpi/data",
        params={"tenant_id": panel_test_tenant.tenant_id},
    )

    # Clean up overrides
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_config_loader, None)
    app.dependency_overrides.pop(get_query_builder, None)

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
    from app.services.config_loader import get_config_loader
    from app.services.query_builder import get_query_builder
    from app.schemas.config import (
        HealthStatusPanelConfig,
        HealthStatusDataSource,
        HealthStatusDisplay,
        HealthStatusMapping
    )

    async def override_get_current_user() -> User:
        return panel_test_user

    # Create real health status config object
    health_config = HealthStatusPanelConfig(
        title="System Health",
        data_source=HealthStatusDataSource(
            table="health_status",
            columns={"service_name": "name", "status_value": "status"}
        ),
        display=HealthStatusDisplay(
            status_mapping={
                0: HealthStatusMapping(label="healthy", color="#10B981"),
                1: HealthStatusMapping(label="degraded", color="#F59E0B"),
            }
        )
    )

    # Mock config loader
    mock_loader = MagicMock()
    mock_loader.load_panel_config.return_value = health_config

    def override_get_config_loader():
        return mock_loader

    # Mock query builder
    mock_qb = MagicMock()
    mock_qb.build_health_status_query.return_value = ("SELECT *", {})

    def override_get_query_builder():
        return mock_qb

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader
    app.dependency_overrides[get_query_builder] = override_get_query_builder

    response = await client.get(
        "/api/v1/panels/system_health/data",
        params={"tenant_id": panel_test_tenant.tenant_id},
    )

    # Clean up overrides
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_config_loader, None)
    app.dependency_overrides.pop(get_query_builder, None)

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
    from app.services.config_loader import get_config_loader
    from app.services.query_builder import get_query_builder
    from app.schemas.config import (
        TablePanelConfig,
        TableDataSource,
        TableDisplay,
        TableColumn
    )

    async def override_get_current_user() -> User:
        return panel_test_user

    # Create real table config object
    table_config = TablePanelConfig(
        title="Error Logs",
        data_source=TableDataSource(
            table="logs",
            columns=[
                TableColumn(name="timestamp", display="Time", format="datetime"),
                TableColumn(name="message", display="Message"),
                TableColumn(name="severity", display="Severity"),
            ]
        ),
        display=TableDisplay(pagination=25, default_sort="timestamp")
    )

    # Mock config loader
    mock_loader = MagicMock()
    mock_loader.load_panel_config.return_value = table_config

    def override_get_config_loader():
        return mock_loader

    # Mock query builder
    mock_qb = MagicMock()
    mock_qb.build_table_query.return_value = ("SELECT *", {})

    def override_get_query_builder():
        return mock_qb

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader
    app.dependency_overrides[get_query_builder] = override_get_query_builder

    response = await client.get(
        "/api/v1/panels/error_logs/data",
        params={
            "tenant_id": panel_test_tenant.tenant_id,
            "sort_column": "timestamp",
            "sort_order": "desc",
            "page": 1,
        },
    )

    # Clean up overrides
    app.dependency_overrides.pop(get_current_active_user, None)
    app.dependency_overrides.pop(get_config_loader, None)
    app.dependency_overrides.pop(get_query_builder, None)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["panel_type"] == "table"
    assert "pagination" in data["data"]
    assert data["data"]["pagination"]["page_size"] == 25
