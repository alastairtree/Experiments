"""Integration tests for KeycloakManager."""

import time
from pathlib import Path

import pytest
import requests

from pytest_keycloak.exceptions import (
    JavaNotFoundError,
    KeycloakStartError,
    KeycloakTimeoutError,
)
from pytest_keycloak.manager import KeycloakManager


@pytest.mark.integration
@pytest.mark.slow
class TestKeycloakManagerIntegration:
    """Integration test cases for KeycloakManager."""

    def test_check_java_version(self):
        """Test that Java version check works."""
        manager = KeycloakManager()

        # This will raise if Java is not installed or wrong version
        # In CI/test environments, Java 17+ should be installed
        try:
            result = manager.check_java_version()
            assert result is True
        except JavaNotFoundError as e:
            pytest.skip(f"Java 17+ not available: {e}")

    def test_download_and_install(self, shared_keycloak_install):
        """Test downloading and installing Keycloak."""
        manager = KeycloakManager(
            version="26.0.7",
            install_dir=shared_keycloak_install,
            port=8280,
        )

        # Download and install (should already be installed from fixture)
        manager.download_and_install()

        # Verify installation
        assert manager.keycloak_dir.exists()
        assert (manager.keycloak_dir / "bin" / "kc.sh").exists()
        assert (manager.keycloak_dir / "bin" / "kc.sh").stat().st_mode & 0o111  # Executable

    def test_install_is_idempotent(self, shared_keycloak_install):
        """Test that installing twice doesn't re-download."""
        manager = KeycloakManager(
            version="26.0.7",
            install_dir=shared_keycloak_install,
            port=8281,
        )

        # First install (already done by fixture)
        manager.download_and_install()
        first_install_time = manager.keycloak_dir.stat().st_mtime

        # Wait a bit
        time.sleep(1)

        # Second install - should not re-download
        manager.download_and_install()
        second_install_time = manager.keycloak_dir.stat().st_mtime

        # Directory should not have been recreated
        assert first_install_time == second_install_time

    def test_start_and_stop_keycloak(self, shared_keycloak_install):
        """Test starting and stopping Keycloak server."""
        manager = KeycloakManager(
            version="26.0.7",
            install_dir=shared_keycloak_install,
            port=8282,
        )

        try:
            # Install
            manager.download_and_install()

            # Start
            manager.start(wait_for_ready=True, timeout=120)

            # Verify it's running
            assert manager.is_running()

            # Verify health endpoint on the management port
            response = requests.get(f"http://localhost:{manager.management_port}/health/ready", timeout=10)
            assert response.status_code == 200

            # Verify admin console is accessible
            response = requests.get(manager.get_base_url(), timeout=10)
            assert response.status_code in [200, 303]  # 303 redirect is expected

        finally:
            # Stop
            manager.stop()
            assert not manager.is_running()

    def test_start_with_realm_import(self, shared_keycloak_install):
        """Test starting Keycloak with realm configuration."""
        manager = KeycloakManager(
            version="26.0.7",
            install_dir=shared_keycloak_install,
            port=8283,
        )

        realm_config = {
            "realm": "integration-test-realm",
            "enabled": True,
            "verifyEmail": False,
            "users": [
                {
                    "username": "intuser",
                    "enabled": True,
                    "email": "intuser@example.com",
                    "emailVerified": True,
                    "firstName": "Integration",
                    "lastName": "User",
                    "credentials": [{"type": "password", "value": "intpass", "temporary": False}],
                }
            ],
            "clients": [
                {
                    "clientId": "test-integration-client",
                    "enabled": True,
                    "publicClient": True,
                    "directAccessGrantsEnabled": True,
                }
            ],
            "roles": {
                "realm": [
                    {"name": "user", "description": "User role"},
                ]
            },
        }

        try:
            # Install and start with realm config
            manager.download_and_install()
            manager.start(realm_config=realm_config, wait_for_ready=True, timeout=120)

            # Verify it's running
            assert manager.is_running()

            # Wait a bit for realm to be fully imported
            time.sleep(5)

            # Verify realm was imported by trying to get a token
            token_url = f"{manager.get_base_url()}/realms/integration-test-realm/protocol/openid-connect/token"
            token_data = {
                "grant_type": "password",
                "client_id": "test-integration-client",
                "username": "intuser",
                "password": "intpass",
            }

            response = requests.post(token_url, data=token_data, timeout=10)
            assert response.status_code == 200
            token_response = response.json()
            assert "access_token" in token_response

        finally:
            manager.stop()

    def test_get_base_url(self):
        """Test get_base_url returns correct URL."""
        manager = KeycloakManager(port=8284)
        assert manager.get_base_url() == "http://localhost:8284"

        manager = KeycloakManager(port=9090)
        assert manager.get_base_url() == "http://localhost:9090"

    def test_is_running_states(self, shared_keycloak_install):
        """Test is_running returns correct states."""
        manager = KeycloakManager(
            version="26.0.7",
            install_dir=shared_keycloak_install,
            port=8285,
        )

        # Initially not running
        assert not manager.is_running()

        try:
            # Start
            manager.download_and_install()
            manager.start(wait_for_ready=True, timeout=120)

            # Should be running
            assert manager.is_running()

        finally:
            # Stop
            manager.stop()

            # Should not be running
            assert not manager.is_running()

    def test_wait_for_ready_timeout(self, shared_keycloak_install):
        """Test that wait_for_ready times out appropriately."""
        manager = KeycloakManager(
            version="26.0.7",
            install_dir=shared_keycloak_install,
            port=8286,
        )

        manager.download_and_install()

        # Start without waiting
        manager.start(wait_for_ready=False)

        try:
            # Should timeout with very short timeout during startup
            with pytest.raises(KeycloakTimeoutError, match="did not become ready"):
                manager.wait_for_ready(timeout=1)

            # But should succeed with longer timeout
            manager.wait_for_ready(timeout=120)
            assert manager.is_running()

        finally:
            manager.stop()

    def test_start_already_running(self, shared_keycloak_install):
        """Test starting when already running."""
        manager = KeycloakManager(
            version="26.0.7",
            install_dir=shared_keycloak_install,
            port=8287,
        )

        try:
            manager.download_and_install()
            manager.start(wait_for_ready=True, timeout=120)

            # Try to start again - should not error
            manager.start(wait_for_ready=True, timeout=10)

            assert manager.is_running()

        finally:
            manager.stop()

    def test_stop_not_running(self):
        """Test stopping when not running."""
        manager = KeycloakManager(port=8288)

        # Should not raise error
        manager.stop()
        assert not manager.is_running()

    def test_start_without_install(self):
        """Test that starting without installing raises error."""
        manager = KeycloakManager(
            install_dir=Path("/nonexistent/path/that/does/not/exist"),
            port=8289,
        )

        with pytest.raises(KeycloakStartError, match="not installed"):
            manager.start()

    def test_cleanup(self, shared_keycloak_install):
        """Test cleanup stops the server."""
        manager = KeycloakManager(
            version="26.0.7",
            install_dir=shared_keycloak_install,
            port=8290,
        )

        manager.download_and_install()
        manager.start(wait_for_ready=True, timeout=120)

        assert manager.is_running()

        # Cleanup
        manager.cleanup()

        # Should be stopped
        assert not manager.is_running()

    def test_manager_context_lifecycle(self, shared_keycloak_install):
        """Test full lifecycle with multiple start/stop cycles."""
        manager = KeycloakManager(
            version="26.0.7",
            install_dir=shared_keycloak_install,
            port=8291,
        )

        manager.download_and_install()

        # First cycle
        manager.start(wait_for_ready=True, timeout=120)
        assert manager.is_running()
        manager.stop()
        assert not manager.is_running()

        # Second cycle - should work fine
        manager.start(wait_for_ready=True, timeout=120)
        assert manager.is_running()
        manager.stop()
        assert not manager.is_running()
