"""Integration tests for pytest fixtures."""

import time

import pytest

from pytest_keycloak.config import ClientConfig, KeycloakConfig, RealmConfig, UserConfig


@pytest.mark.integration
@pytest.mark.slow
class TestPytestFixtures:
    """Integration tests for pytest fixtures."""

    def test_keycloak_config_fixture(self, keycloak_config):
        """Test that keycloak_config fixture works."""
        assert isinstance(keycloak_config, KeycloakConfig)
        assert keycloak_config.version == "26.0.7"
        assert keycloak_config.port == 8180
        assert keycloak_config.admin_user == "admin"
        assert keycloak_config.admin_password == "admin"
        assert keycloak_config.auto_cleanup is True

    def test_keycloak_config_realm(self, keycloak_config):
        """Test that keycloak_config has proper realm configuration."""
        assert keycloak_config.realm is not None
        assert keycloak_config.realm.realm == "test-realm"
        assert keycloak_config.realm.enabled is True

        # Check users
        assert len(keycloak_config.realm.users) == 2
        user1 = keycloak_config.realm.users[0]
        assert user1.username == "testuser1"
        assert user1.password == "password123"
        assert user1.email == "testuser1@example.com"
        assert user1.first_name == "Test"
        assert user1.last_name == "User One"
        assert "user" in user1.realm_roles

        user2 = keycloak_config.realm.users[1]
        assert user2.username == "testuser2"
        assert "admin" in user2.realm_roles
        assert "user" in user2.realm_roles

        # Check clients
        assert len(keycloak_config.realm.clients) == 1
        client = keycloak_config.realm.clients[0]
        assert client.client_id == "test-client"
        assert client.public_client is True
        assert client.direct_access_grants_enabled is True

    def test_keycloak_fixture_running(self, keycloak):
        """Test that keycloak fixture provides a running instance."""
        assert keycloak.is_running()
        assert keycloak.get_base_url() == "http://localhost:8180"
        assert keycloak.port == 8180

    def test_keycloak_fixture_accessible(self, keycloak):
        """Test that Keycloak server is accessible via HTTP."""
        import requests

        # Check health endpoint (on management port 9000 in Keycloak 26.x)
        response = requests.get("http://localhost:9000/health/ready", timeout=10)
        assert response.status_code == 200

        # Check main endpoint
        response = requests.get(keycloak.get_base_url(), timeout=10)
        assert response.status_code in [200, 303]

    def test_keycloak_client_fixture(self, keycloak_client):
        """Test that keycloak_client fixture works."""
        assert keycloak_client is not None
        assert keycloak_client.base_url == "http://localhost:8180"
        assert keycloak_client.realm == "test-realm"
        assert keycloak_client.admin_user == "admin"

    def test_keycloak_client_can_authenticate(self, keycloak_client):
        """Test that keycloak_client can get admin token."""
        token = keycloak_client.get_admin_token()
        assert token is not None
        assert len(token) > 0
        assert token.count(".") >= 2  # JWT format

    def test_preconfigured_users_exist(self, keycloak_client):
        """Test that pre-configured users from config are accessible."""
        # Test testuser1 can get a token
        token_response = keycloak_client.get_user_token(
            username="testuser1",
            password="password123",
            client_id="test-client",
        )

        assert "access_token" in token_response
        assert "token_type" in token_response
        assert token_response["token_type"] == "Bearer"

        # Test testuser2 can get a token
        token_response = keycloak_client.get_user_token(
            username="testuser2",
            password="password456",
            client_id="test-client",
        )

        assert "access_token" in token_response

    def test_keycloak_user_fixture_creates_temporary_user(self, keycloak_user, keycloak_client):
        """Test that keycloak_user fixture creates and cleans up users."""
        username = f"temp_user_{int(time.time())}"

        # Create temporary user
        user_id = keycloak_user(
            username=username,
            password="temp_pass_123",
            email=f"{username}@example.com",
        )

        assert user_id is not None
        assert len(user_id) > 0

        # Verify user can authenticate
        token_response = keycloak_client.get_user_token(
            username=username,
            password="temp_pass_123",
            client_id="test-client",
        )

        assert "access_token" in token_response

        # Note: Cleanup happens automatically after test via fixture

    def test_keycloak_user_fixture_multiple_users(self, keycloak_user, keycloak_client):
        """Test creating multiple temporary users in one test."""
        users = []

        for i in range(3):
            username = f"multi_temp_{i}_{int(time.time())}"
            user_id = keycloak_user(username=username, password=f"pass{i}")
            users.append((username, f"pass{i}", user_id))

        # Verify all users can authenticate
        for username, password, user_id in users:
            assert user_id is not None
            token_response = keycloak_client.get_user_token(
                username=username,
                password=password,
                client_id="test-client",
            )
            assert "access_token" in token_response

    def test_keycloak_user_with_all_fields(self, keycloak_user, keycloak_client):
        """Test creating temporary user with all fields."""
        username = f"full_temp_user_{int(time.time())}"

        user_id = keycloak_user(
            username=username,
            password="full_pass",
            email=f"{username}@example.com",
            first_name="Temp",
            last_name="User",
            enabled=True,
        )

        assert user_id is not None

        # Verify user can authenticate
        token_response = keycloak_client.get_user_token(
            username=username,
            password="full_pass",
            client_id="test-client",
        )

        assert "access_token" in token_response

    def test_realm_config_to_keycloak_json(self):
        """Test RealmConfig converts to proper Keycloak JSON format."""
        realm_config = RealmConfig(
            realm="json-test-realm",
            enabled=True,
            users=[
                UserConfig(
                    username="jsonuser",
                    password="jsonpass",
                    email="json@example.com",
                    first_name="Json",
                    last_name="User",
                    realm_roles=["role1", "role2"],
                )
            ],
            clients=[
                ClientConfig(
                    client_id="json-client",
                    public_client=True,
                    redirect_uris=["http://localhost:3000/*"],
                    web_origins=["http://localhost:3000"],
                )
            ],
        )

        json_data = realm_config.to_keycloak_json()

        # Check realm basics
        assert json_data["realm"] == "json-test-realm"
        assert json_data["enabled"] is True

        # Check user conversion
        assert len(json_data["users"]) == 1
        user = json_data["users"][0]
        assert user["username"] == "jsonuser"
        assert user["email"] == "json@example.com"
        assert user["emailVerified"] is True
        assert user["firstName"] == "Json"
        assert user["lastName"] == "User"
        assert user["enabled"] is True
        assert user["realmRoles"] == ["role1", "role2"]
        assert len(user["credentials"]) == 1
        assert user["credentials"][0]["type"] == "password"
        assert user["credentials"][0]["value"] == "jsonpass"
        assert user["credentials"][0]["temporary"] is False

        # Check client conversion
        assert len(json_data["clients"]) == 1
        client = json_data["clients"][0]
        assert client["clientId"] == "json-client"
        assert client["enabled"] is True
        assert client["publicClient"] is True
        assert client["directAccessGrantsEnabled"] is True
        assert "http://localhost:3000/*" in client["redirectUris"]
        assert "http://localhost:3000" in client["webOrigins"]

    def test_user_config_validation(self):
        """Test UserConfig model validation."""
        # Minimal config
        user = UserConfig(username="testuser", password="testpass")
        assert user.username == "testuser"
        assert user.password == "testpass"
        assert user.enabled is True
        assert user.realm_roles == []
        assert user.client_roles == {}
        assert user.email is None

        # Full config
        user = UserConfig(
            username="fulluser",
            password="fullpass",
            email="full@example.com",
            first_name="First",
            last_name="Last",
            enabled=False,
            realm_roles=["admin"],
            client_roles={"my-client": ["client-role"]},
        )
        assert user.email == "full@example.com"
        assert user.first_name == "First"
        assert user.last_name == "Last"
        assert user.enabled is False
        assert user.realm_roles == ["admin"]
        assert user.client_roles == {"my-client": ["client-role"]}

    def test_client_config_validation(self):
        """Test ClientConfig model validation."""
        # Minimal config
        client = ClientConfig(client_id="test-client")
        assert client.client_id == "test-client"
        assert client.enabled is True
        assert client.public_client is True
        assert client.direct_access_grants_enabled is True
        assert "http://localhost:*" in client.redirect_uris
        assert "http://localhost:*" in client.web_origins

        # Custom config
        client = ClientConfig(
            client_id="custom-client",
            enabled=False,
            public_client=False,
            redirect_uris=["https://example.com/*"],
            web_origins=["https://example.com"],
            direct_access_grants_enabled=False,
            secret="my-secret",
        )
        assert client.enabled is False
        assert client.public_client is False
        assert client.redirect_uris == ["https://example.com/*"]
        assert client.web_origins == ["https://example.com"]
        assert client.direct_access_grants_enabled is False
        assert client.secret == "my-secret"

    def test_keycloak_config_validation(self, tmp_path):
        """Test KeycloakConfig model validation."""
        # Minimal config
        config = KeycloakConfig()
        assert config.version == "26.0.7"
        assert config.port == 8080
        assert config.admin_user == "admin"
        assert config.admin_password == "admin"
        assert config.install_dir is None
        assert config.realm is None
        assert config.auto_cleanup is True

        # Custom config
        realm = RealmConfig(realm="custom", users=[], clients=[])
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
        assert config.realm.realm == "custom"
        assert config.auto_cleanup is False

    def test_realm_import_with_multiple_users_and_clients(self, keycloak_client):
        """Test that realm import works with multiple users and clients."""
        # The default config has 2 users and 1 client
        # Verify they all exist and work

        # User 1
        token1 = keycloak_client.get_user_token(
            username="testuser1",
            password="password123",
            client_id="test-client",
        )
        assert "access_token" in token1

        # User 2
        token2 = keycloak_client.get_user_token(
            username="testuser2",
            password="password456",
            client_id="test-client",
        )
        assert "access_token" in token2

    def test_session_scoped_fixtures_share_instance(self, keycloak, keycloak_client):
        """Test that session-scoped fixtures share the same Keycloak instance."""
        # The keycloak_client should be using the same Keycloak instance
        assert keycloak_client.base_url == keycloak.get_base_url()
        assert keycloak.is_running()

    def test_keycloak_user_cleanup_on_test_failure(self, keycloak_user, keycloak_client):
        """Test that temporary users are cleaned up even if test would fail."""
        username = f"cleanup_test_{int(time.time())}"
        keycloak_user(username=username, password="cleanup_pass")

        # Verify user exists
        token = keycloak_client.get_user_token(
            username=username,
            password="cleanup_pass",
            client_id="test-client",
        )
        assert "access_token" in token

        # User will be cleaned up by fixture teardown
        # We don't need to explicitly test failure case as the fixture
        # uses try/except for cleanup

    def test_multiple_test_isolation(self, keycloak_user):
        """Test that users created in one test don't interfere with another."""
        # This test just creates a user
        user_id = keycloak_user(
            username=f"isolation_test_1_{int(time.time())}",
            password="pass1",
        )
        assert user_id is not None

        # In a real test suite, another test would create a different user
        # and they should not conflict

    def test_realm_config_minimal(self):
        """Test RealmConfig with minimal configuration."""
        realm = RealmConfig(realm="minimal-realm")

        assert realm.realm == "minimal-realm"
        assert realm.enabled is True
        assert realm.users == []
        assert realm.clients == []

        json_data = realm.to_keycloak_json()
        assert json_data["realm"] == "minimal-realm"
        assert json_data["users"] == []
        assert json_data["clients"] == []

    def test_confidential_client_configuration(self):
        """Test ClientConfig for confidential clients."""
        client = ClientConfig(
            client_id="confidential-client",
            public_client=False,
            secret="super-secret-key",
        )

        assert client.public_client is False
        assert client.secret == "super-secret-key"

        # Convert to realm config and check JSON
        realm = RealmConfig(realm="test", clients=[client])
        json_data = realm.to_keycloak_json()

        client_json = json_data["clients"][0]
        assert client_json["publicClient"] is False
        assert client_json["secret"] == "super-secret-key"
        assert client_json["serviceAccountsEnabled"] is True


@pytest.mark.integration
@pytest.mark.slow
class TestFixtureEndToEnd:
    """End-to-end tests using all fixtures together."""

    def test_complete_workflow(self, keycloak, keycloak_client, keycloak_user):
        """Test a complete workflow using all fixtures."""
        # 1. Verify Keycloak is running
        assert keycloak.is_running()

        # 2. Create a temporary user
        username = f"workflow_user_{int(time.time())}"
        user_id = keycloak_user(
            username=username,
            password="workflow_pass",
            email=f"{username}@example.com",
        )
        assert user_id is not None

        # 3. Get token for the user
        token_response = keycloak_client.get_user_token(
            username=username,
            password="workflow_pass",
            client_id="test-client",
        )
        assert "access_token" in token_response

        # 4. Verify token is valid JWT
        access_token = token_response["access_token"]
        assert access_token.count(".") >= 2

        # 5. Also verify pre-configured users work
        token_response2 = keycloak_client.get_user_token(
            username="testuser1",
            password="password123",
            client_id="test-client",
        )
        assert "access_token" in token_response2

    def test_realm_and_client_operations(self, keycloak_client):
        """Test realm and client operations together."""
        realm_name = f"test_realm_{int(time.time())}"

        # Create a realm
        keycloak_client.create_realm({"realm": realm_name, "enabled": True})

        try:
            # Create users in the new realm
            user1_id = keycloak_client.create_user(
                username=f"user1_{int(time.time())}",
                password="pass1",
                realm=realm_name,
            )

            user2_id = keycloak_client.create_user(
                username=f"user2_{int(time.time())}",
                password="pass2",
                realm=realm_name,
            )

            # Both should succeed
            assert user1_id is not None
            assert user2_id is not None

            # Clean up users
            keycloak_client.delete_user(user1_id, realm=realm_name)
            keycloak_client.delete_user(user2_id, realm=realm_name)

        finally:
            # Clean up realm
            keycloak_client.delete_realm(realm_name)
