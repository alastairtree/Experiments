"""Tests for pytest fixtures."""

from unittest.mock import MagicMock, patch

import pytest

from pytest_keycloak.config import ClientConfig, KeycloakConfig, RealmConfig, UserConfig


class TestFixtures:
    """Test cases for pytest fixtures."""

    def test_keycloak_config_fixture(self, keycloak_config):
        """Test default keycloak_config fixture."""
        assert isinstance(keycloak_config, KeycloakConfig)
        assert keycloak_config.version == "26.0.7"
        assert keycloak_config.port == 8080
        assert keycloak_config.admin_user == "admin"
        assert keycloak_config.admin_password == "admin"

        # Check realm configuration
        assert keycloak_config.realm is not None
        assert keycloak_config.realm.realm == "test-realm"
        assert len(keycloak_config.realm.users) == 2
        assert len(keycloak_config.realm.clients) == 1

        # Check users
        user1 = keycloak_config.realm.users[0]
        assert user1.username == "testuser1"
        assert user1.password == "password123"
        assert user1.email == "testuser1@example.com"

        user2 = keycloak_config.realm.users[1]
        assert user2.username == "testuser2"
        assert "admin" in user2.realm_roles

        # Check client
        client = keycloak_config.realm.clients[0]
        assert client.client_id == "test-client"

    @patch("pytest_keycloak.fixtures.KeycloakManager")
    def test_keycloak_fixture_lifecycle(self, mock_manager_class, keycloak_config):
        """Test keycloak fixture lifecycle (start and stop)."""
        # This is a unit test for the fixture logic
        # In a real scenario, use integration tests
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        # Import the fixture function
        from pytest_keycloak.fixtures import keycloak

        # Create a mock fixture function
        gen = keycloak(keycloak_config)

        # Start
        manager = next(gen)

        # Verify calls
        mock_manager.download_and_install.assert_called_once()
        mock_manager.start.assert_called_once()

        # Cleanup
        try:
            next(gen)
        except StopIteration:
            pass

        mock_manager.stop.assert_called_once()
        mock_manager.cleanup.assert_called_once()

    def test_realm_config_to_keycloak_json(self):
        """Test conversion of RealmConfig to Keycloak JSON format."""
        realm_config = RealmConfig(
            realm="test-realm",
            users=[
                UserConfig(
                    username="user1",
                    password="pass1",
                    email="user1@example.com",
                    first_name="First",
                    last_name="User",
                    realm_roles=["role1"],
                )
            ],
            clients=[
                ClientConfig(
                    client_id="client1",
                    redirect_uris=["http://localhost:3000/*"],
                )
            ],
        )

        json_data = realm_config.to_keycloak_json()

        assert json_data["realm"] == "test-realm"
        assert json_data["enabled"] is True

        # Check user conversion
        assert len(json_data["users"]) == 1
        user = json_data["users"][0]
        assert user["username"] == "user1"
        assert user["email"] == "user1@example.com"
        assert user["firstName"] == "First"
        assert user["lastName"] == "User"
        assert user["realmRoles"] == ["role1"]
        assert user["credentials"][0]["value"] == "pass1"
        assert user["credentials"][0]["temporary"] is False

        # Check client conversion
        assert len(json_data["clients"]) == 1
        client = json_data["clients"][0]
        assert client["clientId"] == "client1"
        assert client["publicClient"] is True
        assert client["directAccessGrantsEnabled"] is True
        assert "http://localhost:3000/*" in client["redirectUris"]

    def test_user_config_validation(self):
        """Test UserConfig validation."""
        # Valid config
        user = UserConfig(username="test", password="pass")
        assert user.username == "test"
        assert user.password == "pass"
        assert user.enabled is True
        assert user.realm_roles == []

        # With optional fields
        user = UserConfig(
            username="test",
            password="pass",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            enabled=False,
            realm_roles=["admin", "user"],
        )
        assert user.email == "test@example.com"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.enabled is False
        assert user.realm_roles == ["admin", "user"]

    def test_client_config_validation(self):
        """Test ClientConfig validation."""
        # Valid config with defaults
        client = ClientConfig(client_id="test-client")
        assert client.client_id == "test-client"
        assert client.enabled is True
        assert client.public_client is True
        assert client.direct_access_grants_enabled is True

        # With custom values
        client = ClientConfig(
            client_id="confidential-client",
            public_client=False,
            secret="my-secret",
            redirect_uris=["https://example.com/*"],
            web_origins=["https://example.com"],
        )
        assert client.public_client is False
        assert client.secret == "my-secret"
        assert client.redirect_uris == ["https://example.com/*"]

    def test_keycloak_config_defaults(self):
        """Test KeycloakConfig default values."""
        config = KeycloakConfig()

        assert config.version == "26.0.7"
        assert config.port == 8080
        assert config.admin_user == "admin"
        assert config.admin_password == "admin"
        assert config.install_dir is None
        assert config.realm is None
        assert config.auto_cleanup is True

    def test_keycloak_config_custom(self, tmp_path):
        """Test KeycloakConfig with custom values."""
        realm = RealmConfig(realm="custom-realm")

        config = KeycloakConfig(
            version="25.0.0",
            port=9090,
            admin_user="custom_admin",
            admin_password="custom_pass",
            install_dir=tmp_path,
            realm=realm,
            auto_cleanup=False,
        )

        assert config.version == "25.0.0"
        assert config.port == 9090
        assert config.admin_user == "custom_admin"
        assert config.admin_password == "custom_pass"
        assert config.install_dir == tmp_path
        assert config.realm.realm == "custom-realm"
        assert config.auto_cleanup is False


# Integration test example (requires actual Keycloak)
# These would be run separately with the --integration flag

pytestmark = pytest.mark.integration


@pytest.mark.skip(reason="Integration test - requires Keycloak to be running")
class TestIntegration:
    """Integration tests that require a running Keycloak instance."""

    def test_keycloak_starts_and_stops(self, keycloak):
        """Test that Keycloak starts and is accessible."""
        assert keycloak.is_running()
        assert keycloak.get_base_url()

    def test_keycloak_client_can_authenticate(self, keycloak_client):
        """Test that admin client can get a token."""
        token = keycloak_client.get_admin_token()
        assert token
        assert len(token) > 0

    def test_keycloak_user_fixture(self, keycloak_user, keycloak_client):
        """Test temporary user creation."""
        user_id = keycloak_user(username="temp", password="temp123")
        assert user_id

        # Try to get token for the user
        token_response = keycloak_client.get_user_token(
            username="temp",
            password="temp123",
            client_id="test-client",
        )
        assert "access_token" in token_response

    def test_preconfigured_users_exist(self, keycloak_client):
        """Test that pre-configured users can authenticate."""
        # Test user from default config
        token_response = keycloak_client.get_user_token(
            username="testuser1",
            password="password123",
            client_id="test-client",
        )
        assert "access_token" in token_response
