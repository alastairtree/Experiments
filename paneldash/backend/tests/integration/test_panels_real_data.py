"""Integration tests for panel data API with real database queries."""

import time
from datetime import datetime, timedelta

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.database import db_manager
from app.main import app
from app.models.central import Tenant, User, UserTenant
from app.schemas.config import (
    HealthStatusDataSource,
    HealthStatusDisplay,
    HealthStatusMapping,
    HealthStatusPanelConfig,
    KPIDataSource,
    KPIDisplay,
    KPIPanelConfig,
    TableColumn,
    TableDataSource,
    TableDisplay,
    TablePanelConfig,
    TimeSeriesDataSource,
    TimeSeriesPanelConfig,
)
from app.services.config_loader import get_config_loader


@pytest.fixture
async def test_tenant_with_db(db_session: AsyncSession, test_db_url: str) -> Tenant:
    """Create a test tenant that points to the test database.

    Note: This tenant will use the same database URL as the test database,
    since we don't want to create separate databases for each test.
    """
    unique_id = f"tenant-{int(time.time() * 1000000)}"

    # For tests, we'll create a dummy tenant record but the actual database
    # connection will be mocked or we'll use the test database itself
    # Since the test uses pgserver with Unix sockets, we need to handle this properly
    tenant = Tenant(
        tenant_id=unique_id,
        name=f"Test Tenant {unique_id}",
        database_name="test_db",
        database_host="localhost",
        database_port=5432,
        database_user="test_user",
        database_password="test_pass",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    # Monkey-patch the tenant's database_url for testing to use test_db_url
    tenant._test_db_url = test_db_url
    original_property = type(tenant).database_url

    # Override database_url property for this instance
    type(tenant).database_url = property(lambda self: getattr(self, "_test_db_url", original_property.fget(self)))

    return tenant


@pytest.fixture
async def tenant_with_timeseries_data(test_tenant_with_db: Tenant) -> Tenant:
    """Create tenant database with timeseries test data."""
    tenant = test_tenant_with_db

    async with db_manager.get_tenant_session(tenant.database_url) as session:
        # Drop table if exists
        await session.execute(text("DROP TABLE IF EXISTS metrics"))

        # Create metrics table
        await session.execute(
            text(
                """
            CREATE TABLE metrics (
                recorded_at TIMESTAMP NOT NULL,
                cpu_percent FLOAT NOT NULL,
                server_name TEXT NOT NULL
            )
            """
            )
        )

        # Insert test data - 10 records over 2 hours
        base_time = datetime(2024, 1, 1, 0, 0, 0)
        for i in range(10):
            timestamp = base_time + timedelta(minutes=i * 12)
            cpu_value = 45.0 + (i * 5.0)  # Values from 45 to 90
            await session.execute(
                text(
                    "INSERT INTO metrics (recorded_at, cpu_percent, server_name) "
                    "VALUES (:ts, :cpu, :server)"
                ),
                {"ts": timestamp, "cpu": cpu_value, "server": "server-1"},
            )

        await session.commit()

    return tenant


@pytest.fixture
async def tenant_with_kpi_data(test_tenant_with_db: Tenant) -> Tenant:
    """Create tenant database with KPI test data."""
    tenant = test_tenant_with_db

    async with db_manager.get_tenant_session(tenant.database_url) as session:
        # Drop table if exists
        await session.execute(text("DROP TABLE IF EXISTS kpi_metrics"))

        # Create metrics table
        await session.execute(
            text(
                """
            CREATE TABLE kpi_metrics (
                recorded_at TIMESTAMP NOT NULL,
                cpu_percent FLOAT NOT NULL
            )
            """
            )
        )

        # Insert test data - multiple values
        values = [45.5, 67.8, 85.3, 92.1, 78.4]
        for i, value in enumerate(values):
            timestamp = datetime(2024, 1, 1, i, 0, 0)
            await session.execute(
                text(
                    "INSERT INTO kpi_metrics (recorded_at, cpu_percent) VALUES (:ts, :cpu)"
                ),
                {"ts": timestamp, "cpu": value},
            )

        await session.commit()

    return tenant


@pytest.fixture
async def tenant_with_health_status_data(test_tenant_with_db: Tenant) -> Tenant:
    """Create tenant database with health status test data."""
    tenant = test_tenant_with_db

    async with db_manager.get_tenant_session(tenant.database_url) as session:
        # Drop table if exists
        await session.execute(text("DROP TABLE IF EXISTS health_status"))

        # Create health status table
        await session.execute(
            text(
                """
            CREATE TABLE health_status (
                name TEXT NOT NULL,
                status INTEGER NOT NULL
            )
            """
            )
        )

        # Insert test data
        services = [
            ("api", 0),  # healthy
            ("database", 0),  # healthy
            ("cache", 1),  # degraded
        ]
        for service_name, status_value in services:
            await session.execute(
                text(
                    "INSERT INTO health_status (name, status) VALUES (:name, :status)"
                ),
                {"name": service_name, "status": status_value},
            )

        await session.commit()

    return tenant


@pytest.fixture
async def tenant_with_table_data(test_tenant_with_db: Tenant) -> Tenant:
    """Create tenant database with table test data."""
    tenant = test_tenant_with_db

    async with db_manager.get_tenant_session(tenant.database_url) as session:
        # Drop table if exists
        await session.execute(text("DROP TABLE IF EXISTS logs"))

        # Create logs table
        await session.execute(
            text(
                """
            CREATE TABLE logs (
                timestamp TIMESTAMP NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL
            )
            """
            )
        )

        # Insert 30 test log records
        severities = ["INFO", "WARNING", "ERROR", "CRITICAL"]
        messages = [
            "Application started",
            "Database connection established",
            "High memory usage detected",
            "Failed to connect to external API",
        ]

        for i in range(30):
            timestamp = datetime(2024, 1, 1, 12, 0, 0) - timedelta(minutes=i * 2)
            severity = severities[i % len(severities)]
            message = f"{messages[i % len(messages)]} - Entry {i}"
            await session.execute(
                text(
                    "INSERT INTO logs (timestamp, message, severity) "
                    "VALUES (:ts, :msg, :sev)"
                ),
                {"ts": timestamp, "msg": message, "sev": severity},
            )

        await session.commit()

    return tenant


@pytest.fixture
async def test_user_with_access(
    db_session: AsyncSession, test_tenant_with_db: Tenant
) -> User:
    """Create a test user with access to the tenant."""
    unique_id = f"user-{int(time.time() * 1000000)}"
    user = User(
        keycloak_id=unique_id,
        email=f"{unique_id}@example.com",
        full_name="Test User",
        is_admin=False,
    )
    db_session.add(user)
    await db_session.flush()

    # Grant access to tenant
    user_tenant = UserTenant(user_id=user.id, tenant_id=test_tenant_with_db.id)
    db_session.add(user_tenant)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# Timeseries Tests


@pytest.mark.asyncio
async def test_timeseries_query_success(
    client: AsyncClient,
    tenant_with_timeseries_data: Tenant,
    test_user_with_access: User,
) -> None:
    """Test successful timeseries data retrieval with real database."""
    tenant = tenant_with_timeseries_data
    user = test_user_with_access

    # Mock user auth
    async def override_get_current_user() -> User:
        return user

    # Mock config loader to return timeseries config
    config = TimeSeriesPanelConfig(
        title="CPU Usage",
        data_source=TimeSeriesDataSource(
            table="metrics", columns={"timestamp": "recorded_at", "value": "cpu_percent"}
        ),
    )

    mock_loader = type("MockLoader", (), {"load_panel_config": lambda *args: config})()

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    try:
        response = await client.get(
            "/api/v1/panels/cpu_usage/data",
            params={"tenant_id": tenant.tenant_id},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert data["panel_type"] == "timeseries"
        assert "series" in data["data"]
        assert len(data["data"]["series"]) > 0

        # Verify we got real data (10 records)
        series = data["data"]["series"][0]
        assert len(series["timestamps"]) == 10
        assert len(series["values"]) == 10

        # Verify values are correct
        assert series["values"][0] == 45.0
        assert series["values"][-1] == 90.0

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_timeseries_empty_result(
    client: AsyncClient,
    tenant_with_timeseries_data: Tenant,
    test_user_with_access: User,
) -> None:
    """Test timeseries query with no matching data."""
    tenant = tenant_with_timeseries_data
    user = test_user_with_access

    # Mock user auth
    async def override_get_current_user() -> User:
        return user

    # Mock config loader
    config = TimeSeriesPanelConfig(
        title="CPU Usage",
        data_source=TimeSeriesDataSource(
            table="metrics", columns={"timestamp": "recorded_at", "value": "cpu_percent"}
        ),
    )

    mock_loader = type("MockLoader", (), {"load_panel_config": lambda *args: config})()

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    try:
        # Query for future date range
        date_from = datetime(2099, 1, 1, 0, 0, 0)
        date_to = datetime(2099, 1, 2, 0, 0, 0)

        response = await client.get(
            "/api/v1/panels/cpu_usage/data",
            params={
                "tenant_id": tenant.tenant_id,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return empty series
        assert data["data"]["series"] == []

    finally:
        app.dependency_overrides.clear()


# KPI Tests


@pytest.mark.asyncio
async def test_kpi_query_success(
    client: AsyncClient,
    tenant_with_kpi_data: Tenant,
    test_user_with_access: User,
) -> None:
    """Test successful KPI data retrieval with real database."""
    tenant = tenant_with_kpi_data
    user = test_user_with_access

    # Mock user auth
    async def override_get_current_user() -> User:
        return user

    # Mock config loader - query for latest value
    config = KPIPanelConfig(
        title="Latest CPU",
        data_source=KPIDataSource(
            table="kpi_metrics",
            columns={"value": "cpu_percent"},
            query="ORDER BY recorded_at DESC LIMIT 1",
        ),
        display=KPIDisplay(unit="%", decimals=1, thresholds=[]),
    )

    mock_loader = type("MockLoader", (), {"load_panel_config": lambda *args: config})()

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    try:
        response = await client.get(
            "/api/v1/panels/cpu_kpi/data",
            params={"tenant_id": tenant.tenant_id},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert data["panel_type"] == "kpi"
        assert "value" in data["data"]

        # Should get the latest value (78.4 is the last inserted)
        assert data["data"]["value"] == 78.4
        assert data["data"]["unit"] == "%"

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_kpi_query_no_data(
    client: AsyncClient,
    test_tenant_with_db: Tenant,
    test_user_with_access: User,
) -> None:
    """Test KPI query with empty table."""
    tenant = test_tenant_with_db
    user = test_user_with_access

    # Create empty table
    async with db_manager.get_tenant_session(tenant.database_url) as session:
        await session.execute(text("DROP TABLE IF EXISTS empty_metrics"))
        await session.execute(
            text(
                """
            CREATE TABLE empty_metrics (
                cpu_percent FLOAT NOT NULL
            )
            """
            )
        )
        await session.commit()

    # Mock user auth
    async def override_get_current_user() -> User:
        return user

    # Mock config loader
    config = KPIPanelConfig(
        title="CPU KPI",
        data_source=KPIDataSource(
            table="empty_metrics", columns={"value": "cpu_percent"}
        ),
        display=KPIDisplay(unit="%", decimals=1, thresholds=[]),
    )

    mock_loader = type("MockLoader", (), {"load_panel_config": lambda *args: config})()

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    try:
        response = await client.get(
            "/api/v1/panels/cpu_kpi/data",
            params={"tenant_id": tenant.tenant_id},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return None for value
        assert data["data"]["value"] is None
        assert data["data"]["threshold_status"] == "good"  # Default

    finally:
        app.dependency_overrides.clear()


# Health Status Tests


@pytest.mark.asyncio
async def test_health_status_query_success(
    client: AsyncClient,
    tenant_with_health_status_data: Tenant,
    test_user_with_access: User,
) -> None:
    """Test successful health status data retrieval with real database."""
    tenant = tenant_with_health_status_data
    user = test_user_with_access

    # Mock user auth
    async def override_get_current_user() -> User:
        return user

    # Mock config loader
    config = HealthStatusPanelConfig(
        title="System Health",
        data_source=HealthStatusDataSource(
            table="health_status",
            columns={"service_name": "name", "status_value": "status"},
        ),
        display=HealthStatusDisplay(
            status_mapping={
                0: HealthStatusMapping(label="healthy", color="#10B981"),
                1: HealthStatusMapping(label="degraded", color="#F59E0B"),
                2: HealthStatusMapping(label="down", color="#EF4444"),
            }
        ),
    )

    mock_loader = type("MockLoader", (), {"load_panel_config": lambda *args: config})()

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    try:
        response = await client.get(
            "/api/v1/panels/system_health/data",
            params={"tenant_id": tenant.tenant_id},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert data["panel_type"] == "health_status"
        assert "services" in data["data"]
        assert len(data["data"]["services"]) == 3

        # Verify service statuses
        services = {s["service_name"]: s for s in data["data"]["services"]}
        assert "api" in services
        assert services["api"]["status_label"] == "healthy"
        assert services["cache"]["status_label"] == "degraded"

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_status_empty_result(
    client: AsyncClient,
    test_tenant_with_db: Tenant,
    test_user_with_access: User,
) -> None:
    """Test health status query with empty table."""
    tenant = test_tenant_with_db
    user = test_user_with_access

    # Create empty health status table
    async with db_manager.get_tenant_session(tenant.database_url) as session:
        await session.execute(text("DROP TABLE IF EXISTS empty_health"))
        await session.execute(
            text(
                """
            CREATE TABLE empty_health (
                name TEXT NOT NULL,
                status INTEGER NOT NULL
            )
            """
            )
        )
        await session.commit()

    # Mock user auth
    async def override_get_current_user() -> User:
        return user

    # Mock config loader
    config = HealthStatusPanelConfig(
        title="System Health",
        data_source=HealthStatusDataSource(
            table="empty_health",
            columns={"service_name": "name", "status_value": "status"},
        ),
        display=HealthStatusDisplay(
            status_mapping={
                0: HealthStatusMapping(label="healthy", color="#10B981"),
            }
        ),
    )

    mock_loader = type("MockLoader", (), {"load_panel_config": lambda *args: config})()

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    try:
        response = await client.get(
            "/api/v1/panels/system_health/data",
            params={"tenant_id": tenant.tenant_id},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return empty services list
        assert data["data"]["services"] == []

    finally:
        app.dependency_overrides.clear()


# Table Tests


@pytest.mark.asyncio
async def test_table_query_success(
    client: AsyncClient,
    tenant_with_table_data: Tenant,
    test_user_with_access: User,
) -> None:
    """Test successful table data retrieval with pagination."""
    tenant = tenant_with_table_data
    user = test_user_with_access

    # Mock user auth
    async def override_get_current_user() -> User:
        return user

    # Mock config loader
    config = TablePanelConfig(
        title="Error Logs",
        data_source=TableDataSource(
            table="logs",
            columns=[
                TableColumn(name="timestamp", display="Time", format="datetime"),
                TableColumn(name="message", display="Message"),
                TableColumn(name="severity", display="Severity"),
            ],
        ),
        display=TableDisplay(pagination=10, default_sort="timestamp"),
    )

    mock_loader = type("MockLoader", (), {"load_panel_config": lambda *args: config})()

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    try:
        response = await client.get(
            "/api/v1/panels/error_logs/data",
            params={
                "tenant_id": tenant.tenant_id,
                "page": 1,
                "sort_column": "timestamp",
                "sort_order": "desc",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert data["panel_type"] == "table"
        assert "rows" in data["data"]
        assert "pagination" in data["data"]

        # Should get 10 rows (page size)
        assert len(data["data"]["rows"]) == 10

        # Verify pagination metadata
        pagination = data["data"]["pagination"]
        assert pagination["current_page"] == 1
        assert pagination["page_size"] == 10
        assert pagination["total_rows"] == 30
        assert pagination["total_pages"] == 3

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_table_query_second_page(
    client: AsyncClient,
    tenant_with_table_data: Tenant,
    test_user_with_access: User,
) -> None:
    """Test table data retrieval with pagination - second page."""
    tenant = tenant_with_table_data
    user = test_user_with_access

    # Mock user auth
    async def override_get_current_user() -> User:
        return user

    # Mock config loader
    config = TablePanelConfig(
        title="Error Logs",
        data_source=TableDataSource(
            table="logs",
            columns=[
                TableColumn(name="timestamp", display="Time", format="datetime"),
                TableColumn(name="message", display="Message"),
                TableColumn(name="severity", display="Severity"),
            ],
        ),
        display=TableDisplay(pagination=10, default_sort="timestamp"),
    )

    mock_loader = type("MockLoader", (), {"load_panel_config": lambda *args: config})()

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    try:
        response = await client.get(
            "/api/v1/panels/error_logs/data",
            params={
                "tenant_id": tenant.tenant_id,
                "page": 2,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should get 10 rows
        assert len(data["data"]["rows"]) == 10
        assert data["data"]["pagination"]["current_page"] == 2

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_table_query_empty_result(
    client: AsyncClient,
    test_tenant_with_db: Tenant,
    test_user_with_access: User,
) -> None:
    """Test table query with empty table."""
    tenant = test_tenant_with_db
    user = test_user_with_access

    # Create empty logs table
    async with db_manager.get_tenant_session(tenant.database_url) as session:
        await session.execute(text("DROP TABLE IF EXISTS empty_logs"))
        await session.execute(
            text(
                """
            CREATE TABLE empty_logs (
                timestamp TIMESTAMP NOT NULL,
                message TEXT NOT NULL
            )
            """
            )
        )
        await session.commit()

    # Mock user auth
    async def override_get_current_user() -> User:
        return user

    # Mock config loader
    config = TablePanelConfig(
        title="Logs",
        data_source=TableDataSource(
            table="empty_logs",
            columns=[
                TableColumn(name="timestamp", display="Time", format="datetime"),
                TableColumn(name="message", display="Message"),
            ],
        ),
        display=TableDisplay(pagination=25, default_sort="timestamp"),
    )

    mock_loader = type("MockLoader", (), {"load_panel_config": lambda *args: config})()

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    try:
        response = await client.get(
            "/api/v1/panels/logs/data",
            params={"tenant_id": tenant.tenant_id},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return empty rows
        assert data["data"]["rows"] == []
        assert data["data"]["pagination"]["total_rows"] == 0
        assert data["data"]["pagination"]["total_pages"] == 0

    finally:
        app.dependency_overrides.clear()


# Error Tests


@pytest.mark.asyncio
async def test_query_nonexistent_table(
    client: AsyncClient,
    test_tenant_with_db: Tenant,
    test_user_with_access: User,
) -> None:
    """Test query against non-existent table."""
    tenant = test_tenant_with_db
    user = test_user_with_access

    # Mock user auth
    async def override_get_current_user() -> User:
        return user

    # Mock config loader - references table that doesn't exist
    config = KPIPanelConfig(
        title="CPU KPI",
        data_source=KPIDataSource(
            table="nonexistent_table", columns={"value": "cpu_percent"}
        ),
        display=KPIDisplay(unit="%", decimals=1, thresholds=[]),
    )

    mock_loader = type("MockLoader", (), {"load_panel_config": lambda *args: config})()

    def override_get_config_loader():
        return mock_loader

    app.dependency_overrides[get_current_active_user] = override_get_current_user
    app.dependency_overrides[get_config_loader] = override_get_config_loader

    try:
        response = await client.get(
            "/api/v1/panels/cpu_kpi/data",
            params={"tenant_id": tenant.tenant_id},
        )

        # Should return 503 error
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Failed to query tenant database" in response.json()["detail"]

    finally:
        app.dependency_overrides.clear()
