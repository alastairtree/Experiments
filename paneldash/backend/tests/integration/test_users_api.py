"""Integration tests for user management endpoints."""

from unittest.mock import patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.central import User


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
async def test_users(test_db_url: str) -> list[UUID]:
    """Create test users and return their IDs."""
    engine = create_async_engine(test_db_url, echo=False)
    user_ids: list[UUID] = []
    try:
        async with engine.begin() as conn:
            user1 = User(
                keycloak_id="user-1",
                email="user1@example.com",
                full_name="User One",
                is_admin=False,
            )
            user2 = User(
                keycloak_id="user-2",
                email="user2@example.com",
                full_name="User Two",
                is_admin=False,
            )
            conn.add(user1)
            conn.add(user2)
            await conn.flush()
            user_ids = [user1.id, user2.id]
        return user_ids
    finally:
        await engine.dispose()


class TestUserEndpoints:
    """Tests for user management endpoints."""

    @pytest.mark.asyncio
    async def test_list_users_as_admin(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        test_users: list[UUID],  # noqa: ARG002
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test listing all users as admin."""
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
                "/api/v1/users/", headers={"Authorization": "Bearer mock-token"}
            )

            assert response.status_code == 200
            data = response.json()

            # Should see at least the test users and admin
            assert len(data) >= 3
            emails = [u["email"] for u in data]
            assert "user1@example.com" in emails
            assert "user2@example.com" in emails
            assert "admin@example.com" in emails

    @pytest.mark.asyncio
    async def test_list_users_as_regular_user_forbidden(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        mock_user_token: dict[str, object],
    ) -> None:
        """Test listing users as regular user returns 403."""
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

            response = await client.get(
                "/api/v1/users/", headers={"Authorization": "Bearer mock-token"}
            )

            assert response.status_code == 403
            assert "permissions" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_user_by_id(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        test_users: list[UUID],
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test getting user by ID as admin."""
        user_id = test_users[0]

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
                f"/api/v1/users/{user_id}",
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == str(user_id)
            assert data["email"] == "user1@example.com"
            assert data["full_name"] == "User One"

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test getting nonexistent user returns 404."""
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

            # Use a random UUID that doesn't exist
            fake_id = "00000000-0000-0000-0000-000000000000"
            response = await client.get(
                f"/api/v1/users/{fake_id}",
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_user(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        test_users: list[UUID],
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test updating user as admin."""
        user_id = test_users[0]

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

            update_data = {
                "full_name": "Updated User Name",
                "is_admin": True,
            }

            response = await client.patch(
                f"/api/v1/users/{user_id}",
                json=update_data,
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["full_name"] == "Updated User Name"
            assert data["is_admin"] is True
            assert data["email"] == "user1@example.com"  # Unchanged

    @pytest.mark.asyncio
    async def test_update_user_partial(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        test_users: list[UUID],
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test partial update of user."""
        user_id = test_users[1]

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

            # Only update email
            update_data = {"email": "newemail@example.com"}

            response = await client.patch(
                f"/api/v1/users/{user_id}",
                json=update_data,
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["email"] == "newemail@example.com"
            assert data["full_name"] == "User Two"  # Unchanged
            assert data["is_admin"] is False  # Unchanged

    @pytest.mark.asyncio
    async def test_delete_user(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        test_users: list[UUID],
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test deleting user as admin."""
        user_id = test_users[0]

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
                f"/api/v1/users/{user_id}",
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 204

            # Verify user was deleted
            response2 = await client.get(
                f"/api/v1/users/{user_id}",
                headers={"Authorization": "Bearer mock-token"},
            )
            assert response2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_user_as_regular_user_forbidden(
        self,
        client: AsyncClient,
        test_db: None,  # noqa: ARG002
        test_db_url: str,
        test_users: list[UUID],
        mock_user_token: dict[str, object],
    ) -> None:
        """Test deleting user as regular user returns 403."""
        user_id = test_users[0]

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

            response = await client.delete(
                f"/api/v1/users/{user_id}",
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 403
