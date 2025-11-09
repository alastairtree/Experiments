"""Shared test configuration and fixtures."""

import pytest

from pytest_keycloak import ClientConfig, KeycloakConfig, RealmConfig, UserConfig


@pytest.fixture(scope="session")
def keycloak_config():
    """
    Keycloak configuration for integration tests.

    Uses port 8180 to avoid conflicts with potential running Keycloak instances.
    """
    return KeycloakConfig(
        port=8180,
        version="26.0.7",
        realm=RealmConfig(
            realm="test-realm",
            enabled=True,
            users=[
                UserConfig(
                    username="testuser1",
                    password="password123",
                    email="testuser1@example.com",
                    first_name="Test",
                    last_name="User One",
                    realm_roles=["user"],
                ),
                UserConfig(
                    username="testuser2",
                    password="password456",
                    email="testuser2@example.com",
                    first_name="Admin",
                    last_name="User Two",
                    realm_roles=["admin", "user"],
                ),
            ],
            clients=[
                ClientConfig(
                    client_id="test-client",
                    public_client=True,
                    redirect_uris=["http://localhost:3000/*"],
                    web_origins=["http://localhost:3000"],
                    direct_access_grants_enabled=True,
                )
            ],
        ),
        auto_cleanup=True,
    )


# Add pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")


def pytest_runtest_teardown(item, nextitem):
    """Ensure complete cleanup between tests to avoid port conflicts."""
    import subprocess
    import time

    # Kill any lingering Java/Keycloak processes to prevent port conflicts
    try:
        subprocess.run(["pkill", "-9", "-f", "keycloak"], capture_output=True, timeout=5)
        # Small delay to ensure ports are released
        time.sleep(0.5)
    except Exception:
        pass  # Ignore errors if no processes to kill
