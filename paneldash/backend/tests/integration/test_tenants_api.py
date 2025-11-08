"""Integration tests for tenant management endpoints."""

from unittest.mock import patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.central import Tenant, User, UserTenant


@pytest.fixture
def mock_user_token() -> dict[str, object]:
    """Mock Keycloak token for regular user with unique ID."""
    import time

    unique_id = f"user-{int(time.time() * 1000000)}"
    return {
        "sub": unique_id,
        "email": f"{unique_id}@example.com",
        "name": "Regular User",
        "email_verified": True,
        "realm_access": {"roles": ["user"]},
    }


@pytest.fixture
def mock_admin_token() -> dict[str, object]:
    """Mock Keycloak token for admin user with unique ID."""
    import time

    unique_id = f"admin-{int(time.time() * 1000000)}"
    return {
        "sub": unique_id,
        "email": f"{unique_id}@example.com",
        "name": "Admin User",
        "email_verified": True,
        "realm_access": {"roles": ["admin"]},
    }


@pytest.fixture
async def test_tenant(db_session: AsyncSession) -> UUID:
    """Create a test tenant with unique ID and return its UUID."""
    import time

    unique_id = f"tenant-{int(time.time() * 1000000)}"
    tenant = Tenant(
        tenant_id=unique_id,
        name=f"Test Tenant {unique_id}",
        database_name=f"test_db_{unique_id}",
        database_host="localhost",
        database_port=5432,
        database_user="test_user",
        database_password="test_pass",
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant.id


@pytest.fixture
async def test_user_with_tenant(
    db_session: AsyncSession, test_tenant: UUID, mock_user_token: dict[str, object]
) -> tuple[UUID, UUID]:
    """Create a test user and assign to tenant."""
    keycloak_id = str(mock_user_token["sub"])
    email = str(mock_user_token["email"])

    user = User(
        keycloak_id=keycloak_id,
        email=email,
        full_name="Regular User",
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id

    # Assign user to tenant
    user_tenant = UserTenant(user_id=user_id, tenant_id=test_tenant)
    db_session.add(user_tenant)
    await db_session.commit()

    return user_id, test_tenant


class TestTenantEndpoints:
    """Tests for tenant management endpoints."""

    @pytest.mark.asyncio
    async def test_list_tenants_as_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user_with_tenant: tuple[UUID, UUID],
        mock_user_token: dict[str, object],
    ) -> None:
        """Test listing tenants as regular user shows only assigned tenants."""
        user_id, tenant_id = test_user_with_tenant

        # Get the tenant from DB to check its tenant_id
        from sqlalchemy import select as sql_select

        result = await db_session.execute(sql_select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one()

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_user_token

            response = await client.get(
                "/api/v1/tenants/", headers={"Authorization": "Bearer mock-token"}
            )

            assert response.status_code == 200
            data = response.json()

            # User should see only their assigned tenant
            assert len(data) == 1
            assert data[0]["tenant_id"] == tenant.tenant_id
            assert data[0]["name"] == tenant.name
            assert data[0]["is_active"] is True

    @pytest.mark.asyncio
    async def test_list_tenants_as_admin(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: UUID,  # noqa: ARG002
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test listing tenants as admin shows all tenants."""
        # Create admin user
        admin = User(
            keycloak_id="admin-456",
            email="admin@example.com",
            full_name="Admin User",
            is_admin=True,
        )
        db_session.add(admin)
        await db_session.commit()

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
        db_session: AsyncSession,  # noqa: ARG002
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
        db_session: AsyncSession,
        test_tenant: UUID,
        mock_user_token: dict[str, object],
    ) -> None:
        """Test getting tenant details as unassigned user returns 403."""
        # Create user without tenant assignment
        user = User(
            keycloak_id="user-123",
            email="user@example.com",
            full_name="Regular User",
            is_admin=False,
        )
        db_session.add(user)
        await db_session.commit()

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
        db_session: AsyncSession,
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test creating tenant as admin."""
        # Create admin user
        admin = User(
            keycloak_id="admin-456",
            email="admin@example.com",
            full_name="Admin User",
            is_admin=True,
        )
        db_session.add(admin)
        await db_session.commit()

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
        db_session: AsyncSession,
        mock_user_token: dict[str, object],
    ) -> None:
        """Test creating tenant as regular user returns 403."""
        # Create regular user
        user = User(
            keycloak_id="user-123",
            email="user@example.com",
            full_name="Regular User",
            is_admin=False,
        )
        db_session.add(user)
        await db_session.commit()

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
        db_session: AsyncSession,
        test_tenant: UUID,
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test assigning user to tenant as admin."""
        # Create admin and regular user
        admin = User(
            keycloak_id="admin-456",
            email="admin@example.com",
            full_name="Admin User",
            is_admin=True,
        )
        db_session.add(admin)

        user = User(
            keycloak_id="user-789",
            email="newuser@example.com",
            full_name="New User",
            is_admin=False,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        user_id = user.id

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
        db_session: AsyncSession,
        test_user_with_tenant: tuple[UUID, UUID],
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test removing user from tenant as admin."""
        user_id, tenant_id = test_user_with_tenant

        # Create admin user
        admin = User(
            keycloak_id="admin-456",
            email="admin@example.com",
            full_name="Admin User",
            is_admin=True,
        )
        db_session.add(admin)
        await db_session.commit()

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_admin_token

            response = await client.delete(
                f"/api/v1/tenants/{tenant_id}/users/{user_id}",
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 204
