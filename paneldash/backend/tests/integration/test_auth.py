"""Integration tests for authentication endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.central import User, UserTenant


@pytest.fixture
def mock_keycloak_token() -> dict[str, object]:
    """Mock Keycloak token payload."""
    return {
        "sub": "keycloak-user-123",
        "email": "test@example.com",
        "name": "Test User",
        "preferred_username": "testuser",
        "email_verified": True,
        "realm_access": {"roles": ["user"]},
    }


@pytest.fixture
def mock_admin_token() -> dict[str, object]:
    """Mock Keycloak admin token payload."""
    return {
        "sub": "keycloak-admin-456",
        "email": "admin@example.com",
        "name": "Admin User",
        "preferred_username": "adminuser",
        "email_verified": True,
        "realm_access": {"roles": ["admin"]},
    }


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_auth_me_creates_new_user(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        mock_keycloak_token: dict[str, object],
    ) -> None:
        """Test /auth/me endpoint creates new user on first login."""
        from sqlalchemy.ext.asyncio import create_async_engine

        # Mock the Keycloak token verification
        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_keycloak_token

            # Call the endpoint with mock bearer token
            response = await client.get(
                "/api/v1/auth/me", headers={"Authorization": "Bearer mock-token"}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response contains user info
            assert data["email"] == "test@example.com"
            assert data["full_name"] == "Test User"
            assert data["keycloak_id"] == "keycloak-user-123"
            assert data["is_admin"] is False
            assert data["accessible_tenant_ids"] == []

            # Verify user was created in database
            engine = create_async_engine(test_db_url, echo=False)
            try:
                async with engine.begin() as conn:
                    from sqlalchemy import select

                    result = await conn.execute(
                        select(User).where(User.keycloak_id == "keycloak-user-123")
                    )
                    user = result.scalar_one_or_none()

                    assert user is not None
                    assert user.email == "test@example.com"
                    assert user.full_name == "Test User"
                    assert user.is_admin is False
            finally:
                await engine.dispose()

    @pytest.mark.asyncio
    async def test_auth_me_existing_user(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        mock_keycloak_token: dict[str, object],
    ) -> None:
        """Test /auth/me endpoint with existing user."""
        from sqlalchemy.ext.asyncio import create_async_engine

        # Create user in database first
        engine = create_async_engine(test_db_url, echo=False)
        user_id: UUID
        try:
            async with engine.begin() as conn:
                user = User(
                    keycloak_id="keycloak-user-123",
                    email="test@example.com",
                    full_name="Test User",
                    is_admin=False,
                )
                conn.add(user)
                await conn.flush()
                user_id = user.id
        finally:
            await engine.dispose()

        # Mock the Keycloak token verification
        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_keycloak_token

            # Call the endpoint
            response = await client.get(
                "/api/v1/auth/me", headers={"Authorization": "Bearer mock-token"}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify it returns the existing user
            assert data["id"] == str(user_id)
            assert data["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_auth_me_admin_user(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test /auth/me endpoint creates admin user correctly."""
        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_admin_token

            response = await client.get(
                "/api/v1/auth/me", headers={"Authorization": "Bearer mock-token"}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify admin flag is set
            assert data["is_admin"] is True
            assert data["email"] == "admin@example.com"

    @pytest.mark.asyncio
    async def test_auth_me_without_token(self, client: AsyncClient) -> None:
        """Test /auth/me endpoint without authentication token."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_auth_me_invalid_token(self, client: AsyncClient) -> None:
        """Test /auth/me endpoint with invalid token."""
        from jose import JWTError

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.side_effect = JWTError("Invalid token")

            response = await client.get(
                "/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"}
            )

            assert response.status_code == 401
            assert "Invalid authentication credentials" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_logout(
        self,
        client: AsyncClient,
        mock_keycloak_token: dict[str, object],
    ) -> None:
        """Test logout endpoint."""
        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_keycloak_token

            response = await client.post(
                "/api/v1/auth/logout", headers={"Authorization": "Bearer mock-token"}
            )

            assert response.status_code == 200
            assert response.json() == {"message": "Successfully logged out"}
