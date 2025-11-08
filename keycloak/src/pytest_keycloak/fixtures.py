"""Pytest fixtures for Keycloak testing."""

import logging
from typing import Callable, Generator

import pytest

from .client import KeycloakClient
from .config import ClientConfig, KeycloakConfig, RealmConfig, UserConfig
from .manager import KeycloakManager

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def keycloak_config() -> KeycloakConfig:
    """
    Override this fixture in your conftest.py to customize configuration.

    Example:
        @pytest.fixture(scope="session")
        def keycloak_config():
            return KeycloakConfig(
                port=8081,
                realm=RealmConfig(
                    realm="test-realm",
                    users=[
                        UserConfig(username="testuser", password="testpass")
                    ]
                )
            )

    Returns:
        KeycloakConfig with default test configuration
    """
    return KeycloakConfig(
        realm=RealmConfig(
            realm="test-realm",
            users=[
                UserConfig(
                    username="testuser1",
                    password="password123",
                    email="testuser1@example.com",
                ),
                UserConfig(
                    username="testuser2",
                    password="password456",
                    email="testuser2@example.com",
                    realm_roles=["admin"],
                ),
            ],
            clients=[ClientConfig(client_id="test-client")],
        )
    )


@pytest.fixture(scope="session")
def keycloak(keycloak_config: KeycloakConfig) -> Generator[KeycloakManager, None, None]:
    """
    Session-scoped fixture that provides a running Keycloak instance.

    Usage:
        def test_authentication(keycloak):
            base_url = keycloak.get_base_url()
            # Use base_url to configure your app

    Args:
        keycloak_config: Configuration for Keycloak instance

    Yields:
        KeycloakManager instance with running server
    """
    manager = KeycloakManager(
        version=keycloak_config.version,
        install_dir=keycloak_config.install_dir,
        port=keycloak_config.port,
        admin_user=keycloak_config.admin_user,
        admin_password=keycloak_config.admin_password,
    )

    # Download and install if needed
    logger.info("Downloading and installing Keycloak if needed...")
    manager.download_and_install()

    # Start with realm config if provided
    realm_json = None
    if keycloak_config.realm:
        realm_json = keycloak_config.realm.to_keycloak_json()
        logger.info(f"Starting Keycloak with realm: {keycloak_config.realm.realm}")

    manager.start(realm_config=realm_json, wait_for_ready=True)

    yield manager

    # Cleanup
    logger.info("Stopping Keycloak...")
    manager.stop()

    if keycloak_config.auto_cleanup:
        manager.cleanup()


@pytest.fixture(scope="session")
def keycloak_client(
    keycloak: KeycloakManager,
    keycloak_config: KeycloakConfig,
) -> KeycloakClient:
    """
    Session-scoped fixture providing a KeycloakClient for API interactions.

    Usage:
        def test_user_creation(keycloak_client):
            user_id = keycloak_client.create_user("newuser", "newpass")
            # Test with the new user

    Args:
        keycloak: Running Keycloak instance
        keycloak_config: Configuration for Keycloak

    Returns:
        KeycloakClient configured for the running instance
    """
    realm = keycloak_config.realm.realm if keycloak_config.realm else "master"
    return KeycloakClient(
        base_url=keycloak.get_base_url(),
        admin_user=keycloak_config.admin_user,
        admin_password=keycloak_config.admin_password,
        realm=realm,
    )


@pytest.fixture
def keycloak_user(keycloak_client: KeycloakClient) -> Generator[Callable[..., str], None, None]:
    """
    Function fixture for creating temporary users during tests.

    Creates users that are automatically cleaned up after the test.

    Usage:
        def test_something(keycloak_user):
            user_id = keycloak_user(username="temp", password="temp123")
            # User is automatically deleted after test

    Args:
        keycloak_client: Client for API calls

    Yields:
        Callable that creates users and returns user IDs
    """
    created_users = []

    def _create_user(username: str, password: str, **kwargs: str) -> str:
        """
        Create a temporary user.

        Args:
            username: Username
            password: Password
            **kwargs: Additional user attributes

        Returns:
            User ID
        """
        user_id = keycloak_client.create_user(username, password, **kwargs)
        created_users.append(user_id)
        return user_id

    yield _create_user

    # Cleanup
    for user_id in created_users:
        try:
            keycloak_client.delete_user(user_id)
            logger.debug(f"Cleaned up temporary user: {user_id}")
        except Exception as e:
            logger.warning(f"Failed to clean up user {user_id}: {e}")
