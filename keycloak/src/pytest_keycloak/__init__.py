"""pytest-keycloak-fixture: Pytest fixture for running local Keycloak server in tests."""

from .client import KeycloakClient
from .config import ClientConfig, KeycloakConfig, RealmConfig, UserConfig
from .exceptions import (
    JavaNotFoundError,
    KeycloakAPIError,
    KeycloakDownloadError,
    KeycloakError,
    KeycloakStartError,
    KeycloakTimeoutError,
)
from .manager import KeycloakManager

__version__ = "0.1.0"

__all__ = [
    # Main classes
    "KeycloakManager",
    "KeycloakClient",
    # Configuration
    "KeycloakConfig",
    "RealmConfig",
    "UserConfig",
    "ClientConfig",
    # Exceptions
    "KeycloakError",
    "KeycloakDownloadError",
    "JavaNotFoundError",
    "KeycloakStartError",
    "KeycloakTimeoutError",
    "KeycloakAPIError",
]
