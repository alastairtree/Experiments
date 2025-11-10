"""Shared test configuration and fixtures."""

import pytest

from pytest_keycloak import ClientConfig, KeycloakConfig, RealmConfig, UserConfig
from pytest_keycloak.manager import KeycloakManager


@pytest.fixture(scope="session")
def shared_keycloak_install(tmp_path_factory):
    """
    Session-scoped shared Keycloak installation directory.

    This prevents re-downloading Keycloak for every test by providing
    a single shared installation that all tests can use.
    """
    install_dir = tmp_path_factory.mktemp("shared-keycloak-install")
    manager = KeycloakManager(
        version="26.0.7",
        install_dir=install_dir,
    )

    # Download and install once for the entire test session
    manager.download_and_install()

    yield install_dir

    # No cleanup needed - tmp_path_factory handles it


@pytest.fixture(scope="session")
def keycloak_config(shared_keycloak_install):
    """
    Keycloak configuration for integration tests.

    Uses automatic port selection to avoid conflicts.
    Uses shared installation directory to avoid re-downloading.
    """
    return KeycloakConfig(
        version="26.0.7",
        install_dir=shared_keycloak_install,
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
        auto_cleanup=False,  # Don't delete shared installation
    )


# Add pytest markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
