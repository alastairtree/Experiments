"""Tests for KeycloakClient."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from pytest_keycloak.client import KeycloakClient
from pytest_keycloak.exceptions import KeycloakAPIError


class TestKeycloakClient:
    """Test cases for KeycloakClient."""

    def test_init(self):
        """Test initialization."""
        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
            realm="test-realm",
        )

        assert client.base_url == "http://localhost:8080"
        assert client.admin_user == "admin"
        assert client.admin_password == "admin"
        assert client.realm == "test-realm"
        assert client._token is None

    def test_init_strips_trailing_slash(self):
        """Test that base_url trailing slash is stripped."""
        client = KeycloakClient(
            base_url="http://localhost:8080/",
            admin_user="admin",
            admin_password="admin",
        )

        assert client.base_url == "http://localhost:8080"

    @patch("requests.post")
    def test_get_admin_token_success(self, mock_post):
        """Test successful admin token retrieval."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test-token",
            "token_type": "Bearer",
        }
        mock_post.return_value = mock_response

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
        )

        token = client.get_admin_token()

        assert token == "test-token"
        assert client._token == "test-token"
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_get_admin_token_failure(self, mock_post):
        """Test admin token retrieval failure."""
        mock_post.side_effect = Exception("Connection error")

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
        )

        with pytest.raises(KeycloakAPIError, match="Failed to get admin token"):
            client.get_admin_token()

    @patch("requests.post")
    def test_create_user_success(self, mock_post):
        """Test successful user creation."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"Location": "http://localhost:8080/admin/realms/test/users/123"}
        mock_post.return_value = mock_response

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
            realm="test-realm",
        )
        client._token = "test-token"

        user_id = client.create_user(
            username="testuser",
            password="testpass",
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )

        assert user_id == "123"

    @patch("requests.post")
    def test_create_user_already_exists(self, mock_post):
        """Test user creation when user already exists."""
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.raise_for_status.side_effect = Exception("Conflict")
        mock_post.return_value = mock_response

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
            realm="test-realm",
        )
        client._token = "test-token"

        with pytest.raises(KeycloakAPIError, match="already exists"):
            client.create_user(username="testuser", password="testpass")

    @patch("requests.post")
    @patch("requests.get")
    def test_create_user_fallback_to_query(self, mock_get, mock_post):
        """Test user creation with fallback to query for user ID."""
        mock_post_response = MagicMock()
        mock_post_response.status_code = 201
        mock_post_response.headers = {}  # No Location header
        mock_post.return_value = mock_post_response

        mock_get_response = MagicMock()
        mock_get_response.json.return_value = [{"id": "456", "username": "testuser"}]
        mock_get.return_value = mock_get_response

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
            realm="test-realm",
        )
        client._token = "test-token"

        user_id = client.create_user(username="testuser", password="testpass")

        assert user_id == "456"
        mock_get.assert_called_once()

    @patch("requests.delete")
    def test_delete_user_success(self, mock_delete):
        """Test successful user deletion."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
            realm="test-realm",
        )
        client._token = "test-token"

        client.delete_user("123")

        mock_delete.assert_called_once()

    @patch("requests.delete")
    def test_delete_user_failure(self, mock_delete):
        """Test user deletion failure."""
        mock_delete.side_effect = Exception("Network error")

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
            realm="test-realm",
        )
        client._token = "test-token"

        with pytest.raises(KeycloakAPIError, match="Failed to delete user"):
            client.delete_user("123")

    @patch("requests.post")
    def test_get_user_token_success(self, mock_post):
        """Test successful user token retrieval."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "user-token",
            "refresh_token": "refresh-token",
            "token_type": "Bearer",
            "expires_in": 300,
        }
        mock_post.return_value = mock_response

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
            realm="test-realm",
        )

        token_response = client.get_user_token(
            username="testuser",
            password="testpass",
            client_id="test-client",
        )

        assert token_response["access_token"] == "user-token"
        assert token_response["token_type"] == "Bearer"

    @patch("requests.post")
    def test_get_user_token_failure(self, mock_post):
        """Test user token retrieval failure."""
        mock_post.side_effect = Exception("Invalid credentials")

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
            realm="test-realm",
        )

        with pytest.raises(KeycloakAPIError, match="Failed to get user token"):
            client.get_user_token(
                username="testuser",
                password="wrongpass",
                client_id="test-client",
            )

    @patch("requests.post")
    def test_create_realm_success(self, mock_post):
        """Test successful realm creation."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
        )
        client._token = "test-token"

        realm_config = {"realm": "new-realm", "enabled": True}
        client.create_realm(realm_config)

        mock_post.assert_called_once()

    @patch("requests.post")
    def test_create_realm_already_exists(self, mock_post):
        """Test realm creation when realm already exists."""
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_post.return_value = mock_response

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
        )
        client._token = "test-token"

        realm_config = {"realm": "existing-realm", "enabled": True}

        with pytest.raises(KeycloakAPIError, match="already exists"):
            client.create_realm(realm_config)

    @patch("requests.delete")
    def test_delete_realm_success(self, mock_delete):
        """Test successful realm deletion."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
        )
        client._token = "test-token"

        client.delete_realm("test-realm")

        mock_delete.assert_called_once()

    @patch("requests.delete")
    def test_delete_realm_failure(self, mock_delete):
        """Test realm deletion failure."""
        mock_delete.side_effect = Exception("Network error")

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
        )
        client._token = "test-token"

        with pytest.raises(KeycloakAPIError, match="Failed to delete realm"):
            client.delete_realm("test-realm")

    @patch("requests.get")
    def test_get_user_id_by_username_success(self, mock_get):
        """Test successful user ID lookup by username."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "789", "username": "testuser"}]
        mock_get.return_value = mock_response

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
            realm="test-realm",
        )
        client._token = "test-token"

        user_id = client._get_user_id_by_username("testuser", "test-realm")

        assert user_id == "789"

    @patch("requests.get")
    def test_get_user_id_by_username_not_found(self, mock_get):
        """Test user ID lookup when user not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
            realm="test-realm",
        )
        client._token = "test-token"

        with pytest.raises(KeycloakAPIError, match="not found"):
            client._get_user_id_by_username("nonexistent", "test-realm")

    @patch("pytest_keycloak.client.KeycloakClient.get_admin_token")
    def test_get_headers_with_token(self, mock_get_token):
        """Test _get_headers when token exists."""
        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
        )
        client._token = "existing-token"

        headers = client._get_headers()

        assert headers["Authorization"] == "Bearer existing-token"
        assert headers["Content-Type"] == "application/json"
        mock_get_token.assert_not_called()

    @patch("pytest_keycloak.client.KeycloakClient.get_admin_token")
    def test_get_headers_without_token(self, mock_get_token):
        """Test _get_headers when token doesn't exist."""
        mock_get_token.return_value = "new-token"

        client = KeycloakClient(
            base_url="http://localhost:8080",
            admin_user="admin",
            admin_password="admin",
        )

        headers = client._get_headers()

        assert headers["Authorization"] == "Bearer new-token"
        mock_get_token.assert_called_once()
