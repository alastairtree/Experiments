"""Integration tests for tenant management endpoints."""

from unittest.mock import patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.central import Tenant, User, UserTenant


@pytest.fixture
def mock_user_token() -> dict[str, object]:
    """Mock Keycloak token for regular user."""
    return {
        "sub": "user-123",
        "email": "user@example.com",
        "name": "Regular User",
        "email_verified": True,
        "realm_access": {"roles": ["user"]},
    }


@pytest.fixture
def mock_admin_token() -> dict[str, object]:
    """Mock Keycloak token for admin user."""
    return {
        "sub": "admin-456",
        "email": "admin@example.com",
        "name": "Admin User",
        "email_verified": True,
        "realm_access": {"roles": ["admin"]},
    }


@pytest.fixture
async def test_tenant(test_db_url: str) -> UUID:
    """Create a test tenant and return its ID."""
    engine = create_async_engine(test_db_url, echo=False)
    tenant_id: UUID
    try:
        async with engine.begin() as conn:
            tenant = Tenant(
                tenant_id="test-tenant",
                name="Test Tenant",
                database_name="test_tenant_db",
                database_host="localhost",
                database_port=5432,
                database_user="test_user",
                database_password="test_pass",
            )
            conn.add(tenant)
            await conn.flush()
            tenant_id = tenant.id
        return tenant_id
    finally:
        await engine.dispose()


@pytest.fixture
async def test_user_with_tenant(
    test_db_url: str, test_tenant: UUID
) -> tuple[UUID, UUID]:
    """Create a test user and assign to tenant."""
    engine = create_async_engine(test_db_url, echo=False)
    user_id: UUID
    try:
        async with engine.begin() as conn:
            user = User(
                keycloak_id="user-123",
                email="user@example.com",
                full_name="Regular User",
                is_admin=False,
            )
            conn.add(user)
            await conn.flush()
            user_id = user.id

            # Assign user to tenant
            user_tenant = UserTenant(user_id=user_id, tenant_id=test_tenant)
            conn.add(user_tenant)

        return user_id, test_tenant
    finally:
        await engine.dispose()


class TestTenantEndpoints:
    """Tests for tenant management endpoints."""

    @pytest.mark.asyncio
    async def test_list_tenants_as_user(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_user_with_tenant: tuple[UUID, UUID],
        mock_user_token: dict[str, object],
    ) -> None:
        """Test listing tenants as regular user shows only assigned tenants."""
        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_user_token

            response = await client.get(
                "/api/v1/tenants/", headers={"Authorization": "Bearer mock-token"}
            )

            assert response.status_code == 200
            data = response.json()

            # User should see only their assigned tenant
            assert len(data) == 1
            assert data[0]["tenant_id"] == "test-tenant"
            assert data[0]["name"] == "Test Tenant"
            assert data[0]["is_active"] is True

    @pytest.mark.asyncio
    async def test_list_tenants_as_admin(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        test_tenant: UUID,  # noqa: ARG002
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test listing tenants as admin shows all tenants."""
        # Create admin user
        engine = create_async_engine(test_db_url, echo=False)
        try:
            async with engine.begin() as conn:
                admin = User(
                    keycloak_id="admin-456",
                    email="admin@example.com",
                    full_name="Admin User",
                    is_admin=True,
                )
                conn.add(admin)
        finally:
            await engine.dispose()

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_admin_token

            response = await client.get(
                "/api/v1/tenants/", headers={"Authorization": "Bearer mock-token"}
            )

            assert response.status_code == 200
            data = response.json()

            # Admin should see all active tenants
            assert len(data) >= 1
            assert any(t["tenant_id"] == "test-tenant" for t in data)

    @pytest.mark.asyncio
    async def test_get_tenant_as_assigned_user(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_user_with_tenant: tuple[UUID, UUID],
        mock_user_token: dict[str, object],
    ) -> None:
        """Test getting tenant details as assigned user."""
        _, tenant_id = test_user_with_tenant

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_user_token

            response = await client.get(
                f"/api/v1/tenants/{tenant_id}",
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["tenant_id"] == "test-tenant"
            assert data["name"] == "Test Tenant"

    @pytest.mark.asyncio
    async def test_get_tenant_as_unassigned_user(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        test_tenant: UUID,
        mock_user_token: dict[str, object],
    ) -> None:
        """Test getting tenant details as unassigned user returns 403."""
        # Create user without tenant assignment
        engine = create_async_engine(test_db_url, echo=False)
        try:
            async with engine.begin() as conn:
                user = User(
                    keycloak_id="user-123",
                    email="user@example.com",
                    full_name="Regular User",
                    is_admin=False,
                )
                conn.add(user)
        finally:
            await engine.dispose()

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_user_token

            response = await client.get(
                f"/api/v1/tenants/{test_tenant}",
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 403
            assert "forbidden" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_tenant_as_admin(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test creating tenant as admin."""
        # Create admin user
        engine = create_async_engine(test_db_url, echo=False)
        try:
            async with engine.begin() as conn:
                admin = User(
                    keycloak_id="admin-456",
                    email="admin@example.com",
                    full_name="Admin User",
                    is_admin=True,
                )
                conn.add(admin)
        finally:
            await engine.dispose()

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_admin_token

            tenant_data = {
                "tenant_id": "new-tenant",
                "name": "New Tenant",
                "database_name": "new_tenant_db",
                "database_host": "localhost",
                "database_port": 5432,
                "database_user": "new_user",
                "database_password": "new_pass",
            }

            response = await client.post(
                "/api/v1/tenants/",
                json=tenant_data,
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 201
            data = response.json()

            assert data["tenant_id"] == "new-tenant"
            assert data["name"] == "New Tenant"
            assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_create_tenant_as_user_forbidden(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        mock_user_token: dict[str, object],
    ) -> None:
        """Test creating tenant as regular user returns 403."""
        # Create regular user
        engine = create_async_engine(test_db_url, echo=False)
        try:
            async with engine.begin() as conn:
                user = User(
                    keycloak_id="user-123",
                    email="user@example.com",
                    full_name="Regular User",
                    is_admin=False,
                )
                conn.add(user)
        finally:
            await engine.dispose()

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_user_token

            tenant_data = {
                "tenant_id": "forbidden-tenant",
                "name": "Forbidden Tenant",
                "database_name": "forbidden_db",
                "database_host": "localhost",
                "database_port": 5432,
                "database_user": "user",
                "database_password": "pass",
            }

            response = await client.post(
                "/api/v1/tenants/",
                json=tenant_data,
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_assign_user_to_tenant(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        test_tenant: UUID,
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test assigning user to tenant as admin."""
        # Create admin and regular user
        engine = create_async_engine(test_db_url, echo=False)
        user_id: UUID
        try:
            async with engine.begin() as conn:
                admin = User(
                    keycloak_id="admin-456",
                    email="admin@example.com",
                    full_name="Admin User",
                    is_admin=True,
                )
                conn.add(admin)

                user = User(
                    keycloak_id="user-789",
                    email="newuser@example.com",
                    full_name="New User",
                    is_admin=False,
                )
                conn.add(user)
                await conn.flush()
                user_id = user.id
        finally:
            await engine.dispose()

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_admin_token

            response = await client.post(
                f"/api/v1/tenants/{test_tenant}/users/{user_id}",
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 201
            assert "assigned" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_remove_user_from_tenant(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_user_with_tenant: tuple[UUID, UUID],
        test_db_url: str,
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test removing user from tenant as admin."""
        user_id, tenant_id = test_user_with_tenant

        # Create admin user
        engine = create_async_engine(test_db_url, echo=False)
        try:
            async with engine.begin() as conn:
                admin = User(
                    keycloak_id="admin-456",
                    email="admin@example.com",
                    full_name="Admin User",
                    is_admin=True,
                )
                conn.add(admin)
        finally:
            await engine.dispose()

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_admin_token

            response = await client.delete(
                f"/api/v1/tenants/{tenant_id}/users/{user_id}",
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 204
