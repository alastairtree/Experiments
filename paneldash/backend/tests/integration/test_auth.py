"""Integration tests for authentication endpoints."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.central import User


@pytest.fixture
def mock_keycloak_token() -> dict[str, object]:
    """Mock Keycloak token payload with unique ID."""
    import time

    unique_id = f"keycloak-user-{int(time.time() * 1000000)}"
    return {
        "sub": unique_id,
        "email": f"test-{unique_id}@example.com",
        "name": "Test User",
        "preferred_username": "testuser",
        "email_verified": True,
        "realm_access": {"roles": ["user"]},
    }


@pytest.fixture
def mock_admin_token() -> dict[str, object]:
    """Mock Keycloak admin token payload with unique ID."""
    import time

    unique_id = f"keycloak-admin-{int(time.time() * 1000000)}"
    return {
        "sub": unique_id,
        "email": f"admin-{unique_id}@example.com",
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
        db_session: AsyncSession,
        mock_keycloak_token: dict[str, object],
    ) -> None:
        """Test /auth/me endpoint creates new user on first login."""
        keycloak_id = str(mock_keycloak_token["sub"])
        email = str(mock_keycloak_token["email"])

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
            assert data["email"] == email
            assert data["full_name"] == "Test User"
            assert data["keycloak_id"] == keycloak_id
            assert data["is_admin"] is False
            assert data["accessible_tenant_ids"] == []

            # Verify user was created in database
            result = await db_session.execute(
                select(User).where(User.keycloak_id == keycloak_id)
            )
            user = result.scalar_one_or_none()

            assert user is not None
            assert user.email == email
            assert user.full_name == "Test User"
            assert user.is_admin is False

    @pytest.mark.asyncio
    async def test_auth_me_existing_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_keycloak_token: dict[str, object],
    ) -> None:
        """Test /auth/me endpoint with existing user."""
        keycloak_id = str(mock_keycloak_token["sub"])
        email = str(mock_keycloak_token["email"])

        # Create user in database first
        user = User(
            keycloak_id=keycloak_id,
            email=email,
            full_name="Test User",
            is_admin=False,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        user_id = user.id

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
            assert data["email"] == email

    @pytest.mark.asyncio
    async def test_auth_me_admin_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,  # noqa: ARG002
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test /auth/me endpoint creates admin user correctly."""
        admin_email = str(mock_admin_token["email"])

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_admin_token

            response = await client.get(
                "/api/v1/auth/me", headers={"Authorization": "Bearer mock-token"}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify admin flag is set
            assert data["is_admin"] is True
            assert data["email"] == admin_email

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
