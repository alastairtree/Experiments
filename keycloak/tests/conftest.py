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
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
