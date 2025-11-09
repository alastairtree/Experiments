"""Integration tests for KeycloakClient."""

import time

import pytest

from pytest_keycloak.client import KeycloakClient
from pytest_keycloak.exceptions import KeycloakAPIError
from pytest_keycloak.manager import KeycloakManager


@pytest.fixture(scope="module")
def test_keycloak(tmp_path_factory):
    """Module-scoped Keycloak instance for client tests."""
    tmp_path = tmp_path_factory.mktemp("keycloak-client-tests")
    print(f"Using temporary path for Keycloak: {tmp_path}")
    manager = KeycloakManager(
        version="26.0.7",
        install_dir=tmp_path / "keycloak",
        port=8380,
        admin_user="admin",
        admin_password="admin",
    )

    # Install and start
    manager.download_and_install()
    manager.start(wait_for_ready=True, timeout=120)

    yield manager

    # Cleanup
    manager.stop()


@pytest.fixture(scope="module")
def admin_client(test_keycloak):
    """Module-scoped admin client."""
    return KeycloakClient(
        base_url=test_keycloak.get_base_url(),
        admin_user="admin",
        admin_password="admin",
        realm="master",
    )


@pytest.mark.integration
@pytest.mark.slow
class TestKeycloakClientIntegration:
    """Integration test cases for KeycloakClient."""

    def test_client_initialization(self, test_keycloak):
        """Test client can be initialized."""
        client = KeycloakClient(
            base_url=test_keycloak.get_base_url(),
            admin_user="admin",
            admin_password="admin",
            realm="master",
        )

        assert client.base_url == test_keycloak.get_base_url()
        assert client.admin_user == "admin"
        assert client.realm == "master"
        assert client._token is None

    def test_get_admin_token(self, admin_client):
        """Test getting admin access token."""
        token = admin_client.get_admin_token()

        assert token is not None
        assert len(token) > 0
        assert admin_client._token == token

        # Token should be a valid JWT-like string
        assert token.count(".") >= 2  # JWT has at least 2 dots

    def test_get_admin_token_invalid_credentials(self, test_keycloak):
        """Test getting admin token with invalid credentials."""
        client = KeycloakClient(
            base_url=test_keycloak.get_base_url(),
            admin_user="admin",
            admin_password="wrong_password",
            realm="master",
        )

        with pytest.raises(KeycloakAPIError, match="Failed to get admin token"):
            client.get_admin_token()

    def test_create_and_delete_user(self, admin_client):
        """Test creating and deleting a user."""
        # Create user
        user_id = admin_client.create_user(
            username=f"testuser_{int(time.time())}",
            password="testpass123",
            email="testuser@example.com",
            first_name="Test",
            last_name="User",
            enabled=True,
        )

        assert user_id is not None
        assert len(user_id) > 0

        # Delete user
        admin_client.delete_user(user_id)

        # Verify user is deleted by trying to delete again (should fail)
        with pytest.raises(KeycloakAPIError):
            admin_client.delete_user(user_id)

    def test_create_user_duplicate(self, admin_client):
        """Test creating a user with duplicate username."""
        username = f"duplicate_user_{int(time.time())}"

        # Create first user
        user_id = admin_client.create_user(username=username, password="pass123")

        try:
            # Try to create duplicate - should fail
            with pytest.raises(KeycloakAPIError, match="already exists"):
                admin_client.create_user(username=username, password="pass456")

        finally:
            # Cleanup
            admin_client.delete_user(user_id)

    def test_create_user_minimal(self, admin_client):
        """Test creating user with minimal information."""
        username = f"minimal_user_{int(time.time())}"

        user_id = admin_client.create_user(username=username, password="password")

        try:
            assert user_id is not None
        finally:
            admin_client.delete_user(user_id)

    def test_create_user_with_all_fields(self, admin_client):
        """Test creating user with all optional fields."""
        username = f"full_user_{int(time.time())}"

        user_id = admin_client.create_user(
            username=username,
            password="password123",
            email=f"{username}@example.com",
            first_name="FirstName",
            last_name="LastName",
            enabled=True,
        )

        try:
            assert user_id is not None
        finally:
            admin_client.delete_user(user_id)

    def test_get_user_token(self, admin_client):
        """Test getting user token with password grant."""
        username = f"token_user_{int(time.time())}"

        # Create user
        user_id = admin_client.create_user(username=username, password="userpass123")

        try:
            # Get token
            token_response = admin_client.get_user_token(
                username=username,
                password="userpass123",
                client_id="admin-cli",  # Use built-in client
            )

            assert "access_token" in token_response
            assert "token_type" in token_response
            assert token_response["token_type"] == "Bearer"
            assert "expires_in" in token_response

        finally:
            admin_client.delete_user(user_id)

    def test_get_user_token_invalid_credentials(self, admin_client):
        """Test getting user token with wrong password."""
        username = f"invalid_token_user_{int(time.time())}"

        # Create user
        user_id = admin_client.create_user(username=username, password="correctpass")

        try:
            # Try to get token with wrong password
            with pytest.raises(KeycloakAPIError, match="Failed to get user token"):
                admin_client.get_user_token(
                    username=username,
                    password="wrongpass",
                    client_id="admin-cli",
                )

        finally:
            admin_client.delete_user(user_id)

    def test_create_and_delete_realm(self, admin_client):
        """Test creating and deleting a realm."""
        realm_name = f"test_realm_{int(time.time())}"

        realm_config = {
            "realm": realm_name,
            "enabled": True,
            "displayName": "Test Realm",
        }

        # Create realm
        admin_client.create_realm(realm_config)

        try:
            # Verify realm exists by creating a client for it
            realm_client = KeycloakClient(
                base_url=admin_client.base_url,
                admin_user="admin",
                admin_password="admin",
                realm=realm_name,
            )

            # Should be able to get admin token
            token = realm_client.get_admin_token()
            assert token is not None

        finally:
            # Delete realm
            admin_client.delete_realm(realm_name)

    def test_create_realm_duplicate(self, admin_client):
        """Test creating a realm that already exists."""
        realm_name = f"duplicate_realm_{int(time.time())}"

        realm_config = {"realm": realm_name, "enabled": True}

        # Create first realm
        admin_client.create_realm(realm_config)

        try:
            # Try to create duplicate
            with pytest.raises(KeycloakAPIError, match="already exists"):
                admin_client.create_realm(realm_config)

        finally:
            admin_client.delete_realm(realm_name)

    def test_delete_nonexistent_realm(self, admin_client):
        """Test deleting a realm that doesn't exist."""
        with pytest.raises(KeycloakAPIError, match="Failed to delete realm"):
            admin_client.delete_realm("nonexistent_realm_12345")

    def test_delete_nonexistent_user(self, admin_client):
        """Test deleting a user that doesn't exist."""
        with pytest.raises(KeycloakAPIError):
            admin_client.delete_user("nonexistent-user-id-12345")

    def test_user_operations_in_custom_realm(self, admin_client):
        """Test user operations in a custom realm."""
        realm_name = f"custom_realm_{int(time.time())}"

        # Create realm
        realm_config = {
            "realm": realm_name,
            "enabled": True,
        }
        admin_client.create_realm(realm_config)

        try:
            # Create user in custom realm
            username = f"custom_realm_user_{int(time.time())}"
            user_id = admin_client.create_user(
                username=username,
                password="password123",
                realm=realm_name,
            )

            # Delete user
            admin_client.delete_user(user_id, realm=realm_name)

        finally:
            # Cleanup realm
            admin_client.delete_realm(realm_name)

    def test_multiple_users_in_realm(self, admin_client):
        """Test creating multiple users in a realm."""
        realm_name = f"multi_user_realm_{int(time.time())}"

        # Create realm
        admin_client.create_realm({"realm": realm_name, "enabled": True})

        user_ids = []
        try:
            # Create multiple users
            for i in range(3):
                username = f"user_{i}_{int(time.time())}"
                user_id = admin_client.create_user(
                    username=username,
                    password=f"pass{i}",
                    realm=realm_name,
                )
                user_ids.append(user_id)

            assert len(user_ids) == 3

        finally:
            # Cleanup users
            for user_id in user_ids:
                try:
                    admin_client.delete_user(user_id, realm=realm_name)
                except Exception:
                    pass

            # Cleanup realm
            admin_client.delete_realm(realm_name)

    def test_get_user_id_by_username(self, admin_client):
        """Test _get_user_id_by_username helper method."""
        username = f"lookup_user_{int(time.time())}"

        # Create user
        user_id = admin_client.create_user(username=username, password="pass123")

        try:
            # Look up user ID
            found_id = admin_client._get_user_id_by_username(username, "master")
            assert found_id == user_id

        finally:
            admin_client.delete_user(user_id)

    def test_get_user_id_by_username_not_found(self, admin_client):
        """Test _get_user_id_by_username when user doesn't exist."""
        with pytest.raises(KeycloakAPIError, match="not found"):
            admin_client._get_user_id_by_username("nonexistent_user_xyz", "master")

    def test_get_headers_auto_refreshes_token(self, test_keycloak):
        """Test that _get_headers automatically gets token if needed."""
        client = KeycloakClient(
            base_url=test_keycloak.get_base_url(),
            admin_user="admin",
            admin_password="admin",
            realm="master",
        )

        # Token should be None initially
        assert client._token is None

        # Getting headers should auto-fetch token
        headers = client._get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert client._token is not None

    def test_create_user_in_different_realm(self, admin_client):
        """Test creating users in different realms."""
        realm1 = f"realm1_{int(time.time())}"
        realm2 = f"realm2_{int(time.time())}"

        # Create realms
        admin_client.create_realm({"realm": realm1, "enabled": True})
        admin_client.create_realm({"realm": realm2, "enabled": True})

        user1_id = None
        user2_id = None

        try:
            # Create user in realm1
            user1_id = admin_client.create_user(
                username=f"user1_{int(time.time())}",
                password="pass1",
                realm=realm1,
            )

            # Create user in realm2
            user2_id = admin_client.create_user(
                username=f"user2_{int(time.time())}",
                password="pass2",
                realm=realm2,
            )

            assert user1_id is not None
            assert user2_id is not None

        finally:
            # Cleanup
            if user1_id:
                try:
                    admin_client.delete_user(user1_id, realm=realm1)
                except Exception:
                    pass

            if user2_id:
                try:
                    admin_client.delete_user(user2_id, realm=realm2)
                except Exception:
                    pass

            admin_client.delete_realm(realm1)
            admin_client.delete_realm(realm2)
