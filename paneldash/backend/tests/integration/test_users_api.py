"""Integration tests for user management endpoints."""

from unittest.mock import patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.central import User


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
async def test_users(db_session: AsyncSession) -> list[UUID]:
    """Create test users with unique IDs and return their UUIDs."""
    import time

    unique_id1 = f"user-1-{int(time.time() * 1000000)}"
    unique_id2 = f"user-2-{int(time.time() * 1000000)}"

    user1 = User(
        keycloak_id=unique_id1,
        email=f"{unique_id1}@example.com",
        full_name="User One",
        is_admin=False,
    )
    user2 = User(
        keycloak_id=unique_id2,
        email=f"{unique_id2}@example.com",
        full_name="User Two",
        is_admin=False,
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user1)
    await db_session.refresh(user2)
    return [user1.id, user2.id]


class TestUserEndpoints:
    """Tests for user management endpoints."""

    @pytest.mark.asyncio
    async def test_list_users_as_admin(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_users: list[UUID],  # noqa: ARG002
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test listing all users as admin."""
        # Create admin user with unique ID from mock token
        admin_keycloak_id = str(mock_admin_token["sub"])
        admin_email = str(mock_admin_token["email"])
        admin = User(
            keycloak_id=admin_keycloak_id,
            email=admin_email,
            full_name="Admin User",
            is_admin=True,
        )
        db_session.add(admin)
        await db_session.commit()

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
            # Check for unique email patterns from fixtures
            assert any(e.startswith("user-1-") for e in emails)
            assert any(e.startswith("user-2-") for e in emails)
            assert any(e.startswith("admin-") for e in emails)

    @pytest.mark.asyncio
    async def test_list_users_as_regular_user_forbidden(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_user_token: dict[str, object],
    ) -> None:
        """Test listing users as regular user returns 403."""
        # Create regular user with unique ID from mock token
        user_keycloak_id = str(mock_user_token["sub"])
        user_email = str(mock_user_token["email"])
        user = User(
            keycloak_id=user_keycloak_id,
            email=user_email,
            full_name="Regular User",
            is_admin=False,
        )
        db_session.add(user)
        await db_session.commit()

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
        db_session: AsyncSession,
        test_users: list[UUID],
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test getting user by ID as admin."""
        user_id = test_users[0]

        # Create admin user with unique ID from mock token
        admin_keycloak_id = str(mock_admin_token["sub"])
        admin_email = str(mock_admin_token["email"])
        admin = User(
            keycloak_id=admin_keycloak_id,
            email=admin_email,
            full_name="Admin User",
            is_admin=True,
        )
        db_session.add(admin)
        await db_session.commit()

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_admin_token

            response = await client.get(
                f"/api/v1/users/{user_id}",
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == str(user_id)
            # Check email pattern from test_users fixture
            assert data["email"].startswith("user-1-")
            assert data["full_name"] == "User One"

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test getting nonexistent user returns 404."""
        # Create admin user with unique ID from mock token
        admin_keycloak_id = str(mock_admin_token["sub"])
        admin_email = str(mock_admin_token["email"])
        admin = User(
            keycloak_id=admin_keycloak_id,
            email=admin_email,
            full_name="Admin User",
            is_admin=True,
        )
        db_session.add(admin)
        await db_session.commit()

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
        db_session: AsyncSession,
        test_users: list[UUID],
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test updating user as admin."""
        user_id = test_users[0]

        # Create admin user with unique ID from mock token
        admin_keycloak_id = str(mock_admin_token["sub"])
        admin_email = str(mock_admin_token["email"])
        admin = User(
            keycloak_id=admin_keycloak_id,
            email=admin_email,
            full_name="Admin User",
            is_admin=True,
        )
        db_session.add(admin)
        await db_session.commit()

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
            # Email should be unchanged - check pattern from test_users fixture
            assert data["email"].startswith("user-1-")

    @pytest.mark.asyncio
    async def test_update_user_partial(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_users: list[UUID],
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test partial update of user."""
        user_id = test_users[1]

        # Create admin user with unique ID from mock token
        admin_keycloak_id = str(mock_admin_token["sub"])
        admin_email = str(mock_admin_token["email"])
        admin = User(
            keycloak_id=admin_keycloak_id,
            email=admin_email,
            full_name="Admin User",
            is_admin=True,
        )
        db_session.add(admin)
        await db_session.commit()

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
        db_session: AsyncSession,
        test_users: list[UUID],
        mock_admin_token: dict[str, object],
    ) -> None:
        """Test deleting user as admin."""
        user_id = test_users[0]

        # Create admin user with unique ID from mock token
        admin_keycloak_id = str(mock_admin_token["sub"])
        admin_email = str(mock_admin_token["email"])
        admin = User(
            keycloak_id=admin_keycloak_id,
            email=admin_email,
            full_name="Admin User",
            is_admin=True,
        )
        db_session.add(admin)
        await db_session.commit()

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
        db_session: AsyncSession,
        test_users: list[UUID],
        mock_user_token: dict[str, object],
    ) -> None:
        """Test deleting user as regular user returns 403."""
        user_id = test_users[0]

        # Create regular user with unique ID from mock token
        user_keycloak_id = str(mock_user_token["sub"])
        user_email = str(mock_user_token["email"])
        user = User(
            keycloak_id=user_keycloak_id,
            email=user_email,
            full_name="Regular User",
            is_admin=False,
        )
        db_session.add(user)
        await db_session.commit()

        with patch("app.auth.dependencies.keycloak_auth.verify_token") as mock_verify:
            mock_verify.return_value = mock_user_token

            response = await client.delete(
                f"/api/v1/users/{user_id}",
                headers={"Authorization": "Bearer mock-token"},
            )

            assert response.status_code == 403
